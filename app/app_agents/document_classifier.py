"""
Document classification agent using Gemini LLM
"""

import json
import re
from typing import Any

from app.models.document import DocumentType
from app.utils.gemini_client import generate_content_safe
from app.utils.market_data import get_yahoo_company_info

# Constants
CLASSIFICATION_TEMPERATURE = 0.0
REFLECTION_TEMPERATURE = 0.0
DOCUMENT_TEXT_LIMIT = 10000
REFLECTION_TEXT_LIMIT = 10000

# Document type mapping
DOCUMENT_TYPE_MAP = {
    "earnings_announcement": DocumentType.EARNINGS_ANNOUNCEMENT,
    "quarterly_filing": DocumentType.QUARTERLY_FILING,
    "annual_filing": DocumentType.ANNUAL_FILING,
    "press_release": DocumentType.PRESS_RELEASE,
    "analyst_report": DocumentType.ANALYST_REPORT,
    "news_article": DocumentType.NEWS_ARTICLE,
    "transcript": DocumentType.TRANSCRIPT,
    "other": DocumentType.OTHER,
}

# Reflection configuration
TIME_PERIOD_REQUIREMENTS = (
    'Must be in format "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", or "FY 2024". '
    "Quarter must be Q1, Q2, Q3, or Q4 (uppercase). Year must be 4 number digits. "
    "There must be exactly one space between quarter/FY and year."
)
TIME_PERIOD_EXAMPLES = '["Q3 2024", "FY 2023", "Q1 2025"]'

TICKER_REQUIREMENTS = "Must be uppercase, 1-5 alphabetic characters. Look for symbols near exchange names (NASDAQ, NYSE)."
TICKER_EXAMPLES = '["AAPL", "MSFT", "KO", "CSCO", "BKNG"]'

DOCUMENT_DATE_REQUIREMENTS = (
    "Identify the date the document was published or released. This is usually on the first page. "
    "Must be in YYYY-MM-DD format."
)
DOCUMENT_DATE_EXAMPLES = '["2024-03-25", "2023-11-15"]'

PERIOD_END_DATE_REQUIREMENTS = (
    "Identify the date the financial period ended (e.g., quarter end or fiscal year end). "
    "CRITICAL: The period_end_date is usually 15-60 days BEFORE the document_date. "
    "Must be in YYYY-MM-DD format."
)
PERIOD_END_DATE_EXAMPLES = '["2024-03-31", "2023-12-31"]'


def _get_ticker_context(text: str) -> str:
    """Gather context around exchange names to help identify the ticker."""
    contexts = []
    # Use case-insensitive search for popular exchanges
    for exchange in ["NASDAQ", "NYSE"]:
        # Find all occurrences of the exchange name
        for m in re.finditer(re.escape(exchange), text, re.IGNORECASE):
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            snippet = text[start:end].strip().replace("\n", " ").replace("  ", " ")
            contexts.append(snippet)

    if not contexts:
        return ""

    # Unique and joined snippets
    unique_contexts = list(dict.fromkeys(contexts))
    ticker_context = "\n... ".join(
        unique_contexts[:10]
    )  # Limit to top 10 to keep prompt size reasonable
    return ticker_context


def _get_date_context(text: str) -> str:
    """Gather context around date-like strings to help identify document and period dates."""
    # Pattern for various date formats: March 31, 2024, 03/31/2024, 2024-03-31, etc.
    date_patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+)\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+)\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",
    ]

    pattern = "|".join(date_patterns)
    contexts = []

    for m in re.finditer(pattern, text, re.IGNORECASE):
        start = max(0, m.start() - 250)
        end = min(len(text), m.end() + 250)
        snippet = text[start:end].strip().replace("\n", " ").replace("  ", " ")
        contexts.append(snippet)

    if not contexts:
        return ""

    # Unique and joined snippets
    unique_contexts = list(dict.fromkeys(contexts))
    return "\n... ".join(unique_contexts[:15])  # Limit to keep prompt size reasonable


def _clean_json_response(response_text: str) -> str:
    """
    Remove markdown code blocks from LLM response if present.

    Args:
        response_text: Raw response from LLM

    Returns:
        Cleaned JSON string
    """
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return response_text


def _build_reflection_prompt(reflection_items: list[dict[str, str]], text: str) -> str:
    """
    Build the reflection prompt for validating extracted fields.

    Args:
        reflection_items: List of fields to reflect on
        text: Original document text for context

    Returns:
        Formatted reflection prompt
    """
    prompt = f"""You are reviewing extracted information to ensure it meets format requirements.

Original document text (first {REFLECTION_TEXT_LIMIT} chars):
{text[:REFLECTION_TEXT_LIMIT]}

Please review the following extracted fields and correct them if needed:

"""

    for item in reflection_items:
        prompt += f"""
Field: {item["field"]}
Current Value: "{item["current_value"]}"
Requirements: {item["requirements"]}
Valid Examples: {item["examples"]}
"""
        if item.get("context"):
            prompt += f"Specific Context Found: ... {item['context']} ...\n"

        prompt += "\n"

    prompt += """
Return a JSON object with corrected values. Only include fields that need correction.
If a field is already in the correct format, do NOT include it in the response.
If a field cannot be corrected to meet requirements, set it to null.

Example response format:
{
    "time_period": "Q3 2024"
}

Return only valid JSON, no additional text."""

    return prompt


def _get_reflection_items(result: dict[str, Any], text: str) -> list[dict[str, str]]:
    """
    Build list of fields that need reflection/validation.

    Args:
        result: Initial extraction result
        text: Original document text for context gathering

    Returns:
        List of reflection item configurations
    """
    reflection_items = []

    # Reflect on time_period if it exists
    if result.get("time_period"):
        reflection_items.append(
            {
                "field": "time_period",
                "current_value": result["time_period"],
                "requirements": TIME_PERIOD_REQUIREMENTS,
                "examples": TIME_PERIOD_EXAMPLES,
            }
        )

    # Reflect on ticker - always reflect if it might be missing or to verify
    ticker_val = result.get("ticker", "null")
    if not ticker_val or ticker_val == "null":
        # Even if null, we want to look for it specifically via reflection context
        reflection_items.append(
            {
                "field": "ticker",
                "current_value": "null",
                "requirements": TICKER_REQUIREMENTS,
                "examples": TICKER_EXAMPLES,
                "context": _get_ticker_context(text),
            }
        )
    else:
        # Verify existing ticker
        reflection_items.append(
            {
                "field": "ticker",
                "current_value": ticker_val,
                "requirements": TICKER_REQUIREMENTS,
                "examples": TICKER_EXAMPLES,
                "context": _get_ticker_context(text),
            }
        )

    # Reflect on document_date
    doc_date_val = result.get("document_date")
    reflection_items.append(
        {
            "field": "document_date",
            "current_value": doc_date_val if doc_date_val else "null",
            "requirements": DOCUMENT_DATE_REQUIREMENTS,
            "examples": DOCUMENT_DATE_EXAMPLES,
            "context": _get_date_context(text),
        }
    )

    # Reflect on period_end_date
    period_date_val = result.get("period_end_date")
    reflection_items.append(
        {
            "field": "period_end_date",
            "current_value": period_date_val if period_date_val else "null",
            "requirements": PERIOD_END_DATE_REQUIREMENTS,
            "examples": PERIOD_END_DATE_EXAMPLES,
            "context": _get_date_context(text),
        }
    )

    return reflection_items


def _reflect_on_extraction(result: dict[str, str | None], text: str) -> dict[str, str | None]:
    """
    Reflection step to validate and correct extracted fields.
    Makes an LLM call to review specific fields and ensure they meet format requirements.

    This function is designed to be extensible - add new reflection items via
    _get_reflection_items() as needed.

    Args:
        result: The initial extraction result dictionary
        text: Original document text for context

    Returns:
        Updated result dictionary with corrected fields
    """

    reflection_items = _get_reflection_items(result, text)

    # If no reflection items, return original result
    if not reflection_items:
        return result

    # Build and execute reflection prompt
    reflection_prompt = _build_reflection_prompt(reflection_items, text)

    try:
        response_text = generate_content_safe(reflection_prompt, temperature=REFLECTION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        corrections = json.loads(response_text)

        # Apply corrections to result
        for field, corrected_value in corrections.items():
            if field in result:
                result[field]
                result[field] = corrected_value

        return result

    except (json.JSONDecodeError, Exception):
        # If reflection fails, return original result
        # Log the error but don't fail the entire classification
        return result


def _extract_document_date(text: str, filename: str) -> str | None:
    """
    Extract document_date using dedicated LLM call with focused context.

    Args:
        text: Document text (first few pages)
        filename: PDF filename for additional context

    Returns:
        Document date in YYYY-MM-DD format or None
    """
    date_context = _get_date_context(text)
    first_1000 = text[:1000]

    prompt = f"""Extract the document publication/release date from this financial document.

CONTEXT:
Filename: {filename}
First 1000 characters: {first_1000}

Date context (250 chars around each date found):
{date_context}

REQUIREMENTS:
- The document_date is likely the most recent date mentioned in the document
- UNLESS the date refers to an event that has not occurred
- Must be in YYYY-MM-DD format
- Return null unless you have high confidence

Return ONLY a JSON object:
{{"document_date": "YYYY-MM-DD" or null}}
"""

    try:
        response_text = generate_content_safe(prompt, temperature=CLASSIFICATION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        result = json.loads(response_text)
        return result.get("document_date")
    except Exception:
        return None


def _extract_time_period(text: str, filename: str) -> str | None:
    """
    Extract time_period using dedicated LLM call with focused context.

    Args:
        text: Document text (first few pages)
        filename: PDF filename for additional context

    Returns:
        Time period in "Qx YYYY" or "FY YYYY" format or None
    """
    date_context = _get_date_context(text)
    first_1000 = text[:1000]

    prompt = f"""Extract the financial reporting period from this document.

CONTEXT:
Filename: {filename}
First 1000 characters: {first_1000}

Date context (250 chars around each date found):
{date_context}

REQUIREMENTS:
- Must be in format "Q1 YYYY", "Q2 YYYY", "Q3 YYYY", "Q4 YYYY", or "FY YYYY"
- Key words such as "six months", "nine months", "twelve months", "annual" are important hints
- Do not assume calendar year and fiscal year are the same
- Return null unless you have high confidence

EXAMPLES: "Q3 2024", "FY 2023", "Q1 2025"

Return ONLY a JSON object:
{{"time_period": "Qx YYYY" or "FY YYYY" or null}}
"""

    try:
        response_text = generate_content_safe(prompt, temperature=CLASSIFICATION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        result = json.loads(response_text)
        return result.get("time_period")
    except Exception:
        return None


def _extract_period_end_date(text: str, filename: str) -> str | None:
    """
    Extract period_end_date using dedicated LLM call with focused context.

    Args:
        text: Document text (first few pages)
        filename: PDF filename for additional context

    Returns:
        Period end date in YYYY-MM-DD format or None
    """
    date_context = _get_date_context(text)
    first_1000 = text[:1000]

    prompt = f"""Extract the financial period end date from this document.

CONTEXT:
Filename: {filename}
First 1000 characters: {first_1000}

Date context (250 chars around each date found):
{date_context}

REQUIREMENTS:
- Must be in YYYY-MM-DD format
- Often found in the first paragraph with "quarter ending" or "fiscal year ending" or "months ending"
- Often found in the column header of financial statement tables (use the most recent date)
- Return null unless you have high confidence

EXAMPLES: "2024-03-31", "2023-12-31"

Return ONLY a JSON object:
{{"period_end_date": "YYYY-MM-DD" or null}}
"""

    try:
        response_text = generate_content_safe(prompt, temperature=CLASSIFICATION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        result = json.loads(response_text)
        return result.get("period_end_date")
    except Exception:
        return None


def _reflect_on_dates(
    document_date: str | None,
    time_period: str | None,
    period_end_date: str | None,
    text: str,
    filename: str,
) -> dict[str, str | None]:
    """
    Reflection step to validate and correct the three date fields together.

    Args:
        document_date: Extracted document date
        time_period: Extracted time period
        period_end_date: Extracted period end date
        text: Original document text
        filename: PDF filename

    Returns:
        Dictionary with validated/corrected date fields
    """
    date_context = _get_date_context(text)
    first_1000 = text[:1000]

    prompt = f"""Review and validate these extracted date fields from a financial document.

CONTEXT:
Filename: {filename}
First 1000 characters: {first_1000}

Date context (250 chars around each date found):
{date_context}

EXTRACTED VALUES:
- document_date: {document_date or "null"}
- time_period: {time_period or "null"}
- period_end_date: {period_end_date or "null"}

VALIDATION RULES:
1. document_date and period_end_date cannot be the same
2. period_end_date is usually 15-60 days BEFORE document_date
3. time_period must match format "Q1 YYYY", "Q2 YYYY", "Q3 YYYY", "Q4 YYYY", or "FY YYYY"
4. For FY or Q4, look for keywords like "twelve months" in income statement or "fiscal year ending"
5. All dates must be in YYYY-MM-DD format

Return ONLY a JSON object with corrected values. Only include fields that need correction.
If all fields are correct, return an empty object {{}}.
If a field cannot be corrected, set it to null.

Example response:
{{"time_period": "Q3 2024", "period_end_date": "2024-09-30"}}
"""

    try:
        response_text = generate_content_safe(prompt, temperature=REFLECTION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        corrections = json.loads(response_text)

        # Apply corrections
        result = {
            "document_date": corrections.get("document_date", document_date),
            "time_period": corrections.get("time_period", time_period),
            "period_end_date": corrections.get("period_end_date", period_end_date),
        }
        return result

    except Exception:
        # Return original values if reflection fails
        return {
            "document_date": document_date,
            "time_period": time_period,
            "period_end_date": period_end_date,
        }


def _build_classification_prompt(text: str) -> str:
    """
    Build the main classification prompt.

    Args:
        text: Document text to classify

    Returns:
        Formatted classification prompt
    """
    return f"""Analyze the following document text and extract key information.
Return a JSON object with the following structure:
{{
    "document_type": one of ["earnings_announcement", "quarterly_filing", "annual_filing", "press_release", "analyst_report", "news_article", "transcript", "other"],
    "time_period": the time period MUST BE in a format "Q3 2024", "FY 2023", or null if not EXPLICITLY found in the document text,
    "period_end_date": the period end date in YYYY-MM-DD format (e.g., "2024-03-31" for Q1 2024, "2024-09-30" for Q3 2024), or null if not EXPLICITLY found in the document text,
    "document_date": the date the document was published/released in YYYY-MM-DD format, or null if not EXPLICITLY found,
    "company_name": the company name or null if not EXPLICITLY found in the document text,
    "ticker": the stock ticker symbol or null if not EXPLICITLY found in the document text,
    "confidence": one of ["high", "medium", "low"] based on how confident you are in the classification
}}

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract information that is EXPLICITLY shown in the document text below
- DO NOT invent, infer, or assume company names, tickers, time periods, or dates
- If information is not visible in the document text, use null
- DO NOT use external knowledge to fill in missing information
- DO NOT include leading or trailing whitespace in "ticker" or "company_name"
- For period_end_date, look for explicit date mentions like "For the quarter ended March 31, 2024" or "Three months ended September 30, 2024"
- For document_date, look in the first few lines of the document, commonly coinciding with a location (e.g., New York, Beijing) and the company name
- Period_end_date cannot be the same date as the announcement or document date. Period_end_date is likely 15 to 60 days before the announcement date (document_date).

IMPORTANT:
document_type classification rules:
- "earnings_announcement": Use ONLY for press releases or announcements that specifically report quarterly or annual earnings results, financial performance metrics (revenue, profit, EPS), and earnings guidance. These typically include phrases like "earnings", "revenue", "net income", "EPS", "quarterly results", "annual results", or financial performance data.
- "press_release": Use for all OTHER press releases that are NOT earnings announcements. Examples include: product launches, partnerships, executive appointments, regulatory updates, strategic initiatives, mergers/acquisitions, legal matters, or any other company news that is not primarily about earnings/financial results.
- "quarterly_filing": Official SEC quarterly filings (10-Q forms)
- "annual_filing": Official SEC annual filings (10-K forms)
- "analyst_report": Reports from financial analysts or research firms
- "news_article": Third-party news articles about the company
- "other": Any document that doesn't fit the above categories
When in doubt between "earnings_announcement" and "press_release", choose "earnings_announcement" if the document primarily focuses on financial results, earnings, revenue, or quarterly/annual performance metrics.

Document text (first few pages):
{text[:DOCUMENT_TEXT_LIMIT]}

Return only valid JSON, no additional text."""


def _apply_time_period_corrections(doc_type: str | DocumentType, time_period: str) -> str:
    """
    Apply document-type-specific time period corrections.

    Args:
        doc_type: Document type (string or enum)
        time_period: Current time period value

    Returns:
        Corrected time period
    """
    # Convert enum to string if needed
    if isinstance(doc_type, DocumentType):
        doc_type_str = doc_type.value
    else:
        doc_type_str = doc_type

    # Rule 1: Earnings Announcement FY -> Q4
    if doc_type_str == "earnings_announcement":
        match = re.match(r"^FY\s*(\d{4})$", time_period, re.IGNORECASE)
        if match:
            year = match.group(1)
            return f"Q4 {year}"

    # Rule 2: Annual Filing Q4 -> FY
    elif doc_type_str == "annual_filing":
        match = re.match(r"^Q4\s*(\d{4})$", time_period, re.IGNORECASE)
        if match:
            year = match.group(1)
            return f"FY {year}"

    return time_period


def _map_document_type_to_enum(doc_type_str: str) -> DocumentType | None:
    """
    Map document type string to DocumentType enum.

    Args:
        doc_type_str: Document type as string

    Returns:
        DocumentType enum value or None if mapping fails
    """
    try:
        return DOCUMENT_TYPE_MAP.get(doc_type_str, DocumentType.OTHER)
    except Exception:
        return None


def _enrich_identity_with_knowledge(result: dict, text: str) -> dict:
    """
    Final double-check of company identity using LLM knowledge.
    Unlike previous steps, this step ALLOWS the LLM to use its own knowledge
    to normalize company names and verify stock tickers.

    Args:
        result: Current extraction result
        text: Document text snippet

    Returns:
        Updated result with normalized company name and ticker
    """
    company_name = result.get("company_name")
    ticker = result.get("ticker")

    # If both are missing, we definitely need help
    # If both are present, we want to normalize/verify

    prompt = f"""
I have extracted the following identity information from a financial document:
- Extracted Company Name: {company_name or "null"}
- Extracted Ticker: {ticker or "null"}

The document text snippet is:
---
{text[:5000]}
---

YOUR TASK:
Using your internal knowledge and the context of the document text, provide the STANDARDIZED company name and the correct PRIMARY stock ticker (e.g., AAPL for Apple Inc).

RULES:
1. You MAY use your external knowledge to correct or normalize these fields.
2. If the company is public, provide its official full name and its primary trading ticker.
3. If the extracted ticker and company name seem to belong to the same entity, ensure they are correct.
4. If they seem to conflict, prioritize the one that matches the document context best.
5. Do not hallucinate a new company unrelated to the extracted company name or extracted ticker.
6. Return ONLY a JSON object with "company_name" and "ticker" keys.

Response Format:
{{
    "company_name": "Official Company Name",
    "ticker": "TICKER"
}}
"""
    try:
        response_text = generate_content_safe(prompt, temperature=0.0)
        response_text = _clean_json_response(response_text)
        enrichment = json.loads(response_text)

        if enrichment.get("company_name"):
            result.get("company_name")
            result["company_name"] = enrichment["company_name"].strip()
        if enrichment.get("ticker"):
            result.get("ticker")
            result["ticker"] = enrichment["ticker"].strip().upper()

    except Exception:
        pass

    return result


def _validate_company_name_with_llm(
    extracted_name: str | None,
    yahoo_name: str,
    text: str,
) -> bool:
    """
    Use an LLM call to determine whether the extracted company name and the
    Yahoo Finance shortName refer to the same entity.

    Args:
        extracted_name: Company name extracted from the document
        yahoo_name: shortName returned by Yahoo Finance
        text: Document text snippet for additional context

    Returns:
        True if the names refer to the same company, False otherwise
    """
    prompt = f"""You are validating company identity extracted from a financial document.

Extracted company name (from document): "{extracted_name or "null"}"
Yahoo Finance company name (for the extracted ticker): "{yahoo_name}"

Document text snippet (first 2000 chars):
---
{text[:2000]}
---

Do these two names refer to the SAME company?
Consider common abbreviations (e.g. "Apple" vs "Apple Inc."), subsidiaries, or alternate trading names.

Return ONLY a JSON object:
{{"same_company": true or false, "reason": "brief explanation"}}

Return only valid JSON, no additional text."""

    try:
        response_text = generate_content_safe(prompt, temperature=0.0)
        response_text = _clean_json_response(response_text)
        data = json.loads(response_text)
        result = bool(data.get("same_company", False))
        return result
    except Exception:
        # If validation itself fails, assume mismatch so we fall back to enrichment
        return False


def _create_empty_result() -> dict[str, str | None]:
    """
    Create an empty classification result with all fields set to None.

    Returns:
        Dictionary with None values for all fields
    """
    return {
        "document_type": None,
        "time_period": None,
        "period_end_date": None,
        "document_date": None,
        "company_name": None,
        "ticker": None,
        "confidence": "low",
    }


def classify_document(text: str, filename: str = "") -> dict[str, str | None]:
    """
    Classify a document using Gemini LLM to determine:
    - Document type (earnings announcement, filing, etc.)
    - Time period (Q3 2024, FY 2023, etc.)
    - Company name and ticker symbol

    Args:
        text: Extracted text from the first few pages of the document
        filename: PDF filename for additional context in date extraction

    Returns:
        Dictionary with:
        - document_type: DocumentType enum value or None
        - time_period: String like "Q3 2024" or "FY 2023" or None
        - document_date: Date string YYYY-MM-DD or None
        - period_end_date: Date string YYYY-MM-DD or None
        - company_name: Company name or None
        - ticker: Ticker symbol or None
        - confidence: Confidence level (high/medium/low) or None
    """
    try:
        # Step 1: Base Classification (Document Type & Company Identity)
        # Use existing prompt but focus on identity/type rather than dates
        prompt = _build_classification_prompt(text)
        response_text = generate_content_safe(prompt, temperature=CLASSIFICATION_TEMPERATURE)
        response_text = _clean_json_response(response_text)
        base_result = json.loads(response_text)

        # Step 2: Conditional Ticker Reflection
        # Only run reflection if ticker was not found in Step 1
        if not base_result.get("ticker"):
            base_result = _reflect_on_extraction(base_result, text)
        else:
            pass

        # Step 3: Granular Date Extraction Pipeline
        document_date = _extract_document_date(text, filename)
        time_period = _extract_time_period(text, filename)
        period_end_date = _extract_period_end_date(text, filename)

        # Step 4: Validate dates together with cross-field reflection
        validated_dates = _reflect_on_dates(
            document_date, time_period, period_end_date, text, filename
        )

        # Step 5: Merge base classification with validated dates
        result = base_result.copy()
        result.update(validated_dates)

        # Step 6: Identity Resolution via Yahoo Finance + conditional LLM enrichment
        ticker_after_reflection = result.get("ticker")
        extracted_company_name = result.get("company_name")  # Save as fallback

        if ticker_after_reflection:
            # We have a ticker — validate via Yahoo Finance
            yahoo_name = get_yahoo_company_info(ticker_after_reflection)

            if yahoo_name:
                # Ask LLM if the extracted name matches Yahoo's name
                names_match = _validate_company_name_with_llm(
                    extracted_company_name, yahoo_name, text
                )

                if names_match:
                    # Step 5 (plan): Yahoo validation passed — use Yahoo shortName as final name
                    result["company_name"] = yahoo_name
                else:
                    # Mismatch — fall back to LLM enrichment to resolve the conflict
                    result = _enrich_identity_with_knowledge(result, text)
                    # After enrichment, attempt to get Yahoo shortName again with the (possibly corrected) ticker
                    enriched_ticker = result.get("ticker")
                    if enriched_ticker:
                        final_yahoo_name = get_yahoo_company_info(enriched_ticker)
                        if final_yahoo_name:
                            result["company_name"] = final_yahoo_name
                        else:
                            pass
                    # If no ticker after enrichment, keep whatever enrichment returned
            else:
                # Yahoo Finance failed — fall back to LLM enrichment
                result = _enrich_identity_with_knowledge(result, text)
        else:
            # No ticker at all — go straight to LLM enrichment
            result = _enrich_identity_with_knowledge(result, text)

        # Final safety net: if company_name is still None, restore the originally extracted name
        if not result.get("company_name") and extracted_company_name:
            result["company_name"] = extracted_company_name

        # Always normalize the ticker — strip whitespace and uppercase regardless of which branch was taken
        if result.get("ticker"):
            result["ticker"] = result["ticker"].strip().upper()

        # Step 7: Apply post-processing rules (FY <-> Q4 conversion)
        doc_type = result.get("document_type")
        time_period_final = result.get("time_period")

        if doc_type and time_period_final:
            result["time_period"] = _apply_time_period_corrections(doc_type, time_period_final)

        # Step 8: Map document_type string to DocumentType enum
        if result.get("document_type"):
            result["document_type"] = _map_document_type_to_enum(result["document_type"])

        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, return empty result
        return _create_empty_result()
    except Exception as e:
        raise Exception(f"Error classifying document: {str(e)}")

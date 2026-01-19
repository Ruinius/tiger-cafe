"""
Document classification agent using Gemini LLM
"""

import json
import re
from typing import Any

from app.models.document import DocumentType
from app.utils.gemini_client import generate_content_safe

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


def _get_reflection_items(result: dict[str, Any]) -> list[dict[str, str]]:
    """
    Build list of fields that need reflection/validation.

    Args:
        result: Initial extraction result

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

    # Add more reflection items here as needed
    # Example:
    # if result.get("ticker"):
    #     reflection_items.append({
    #         "field": "ticker",
    #         "current_value": result["ticker"],
    #         "requirements": "Must be uppercase, 1-5 characters",
    #         "examples": '["AAPL", "MSFT", "GOOGL"]',
    #     })

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
    reflection_items = _get_reflection_items(result)

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
                result[field] = corrected_value

        return result

    except (json.JSONDecodeError, Exception) as e:
        # If reflection fails, return original result
        # Log the error but don't fail the entire classification
        print(f"Warning: Reflection step failed: {str(e)}")
        return result


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
Period_end_date cannot be the same date as the announcement or document date. Period_end_date is likely 15 to 60 days before the announcement date.

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
        "company_name": None,
        "ticker": None,
        "confidence": "low",
    }


def classify_document(text: str) -> dict[str, str | None]:
    """
    Classify a document using Gemini LLM to determine:
    - Document type (earnings announcement, filing, etc.)
    - Time period (Q3 2024, FY 2023, etc.)
    - Company name and ticker symbol

    Args:
        text: Extracted text from the first few pages of the document

    Returns:
        Dictionary with:
        - document_type: DocumentType enum value or None
        - time_period: String like "Q3 2024" or "FY 2023" or None
        - company_name: Company name or None
        - ticker: Ticker symbol or None
        - confidence: Confidence level (high/medium/low) or None
    """
    try:
        # Step 1: Build and execute classification prompt
        prompt = _build_classification_prompt(text)
        response_text = generate_content_safe(prompt, temperature=CLASSIFICATION_TEMPERATURE)

        # Step 2: Parse JSON response
        response_text = _clean_json_response(response_text)
        result = json.loads(response_text)

        # Step 3: Reflection step - validate and correct extracted fields
        result = _reflect_on_extraction(result, text)

        # Step 4: Apply post-processing rules
        doc_type = result.get("document_type")
        time_period = result.get("time_period")

        if doc_type and time_period:
            result["time_period"] = _apply_time_period_corrections(doc_type, time_period)

        # Step 5: Map document_type string to DocumentType enum
        if result.get("document_type"):
            result["document_type"] = _map_document_type_to_enum(result["document_type"])

        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, return empty result
        return _create_empty_result()
    except Exception as e:
        raise Exception(f"Error classifying document: {str(e)}")

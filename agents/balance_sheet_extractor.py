"""
Balance sheet extraction agent using Gemini LLM and embeddings
"""

import json
import re

from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.pdf_extractor import extract_text_from_pdf


def find_balance_sheet_section(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: str | None = None,
    chunk_rank: int = 0,
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embedding to locate the consolidated balance sheet section.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Tuple of (extracted_text, start_page, log_info) or (None, None, None) if not found
    """
    try:
        # Determine ignore fractions based on document type
        # Convert document_type to string if it's an enum
        doc_type_str = (
            document_type.value
            if hasattr(document_type, "value")
            else str(document_type)
            if document_type
            else None
        )

        if doc_type_str == "earnings_announcement":
            ignore_front_fraction = 0.3
            ignore_back_fraction = 0.1
        elif doc_type_str == "annual_filing":
            ignore_front_fraction = 0.5
            ignore_back_fraction = 0.2
        elif doc_type_str == "quarterly_filing":
            ignore_front_fraction = 0.0
            ignore_back_fraction = 0.5
        else:
            # Default: ignore 10% from both edges
            ignore_front_fraction = 0.1
            ignore_back_fraction = 0.1

        # Initial query texts for finding the balance sheet section
        query_texts = [
            "consolidated balance sheet",
            "balance sheet",
            "total assets",
            "total liabilities",
        ]

        # Re-ranking query terms: normalized balance sheet line items
        def normalize_term(term: str) -> str:
            import re

            # Lowercase, remove special characters except spaces, normalize whitespace
            normalized = term.lower()
            normalized = re.sub(r"[()]", "", normalized)  # Remove parentheses
            normalized = normalized.replace(",", "")  # Remove commas
            normalized = re.sub(r"\s+", " ", normalized)  # Normalize whitespace
            return normalized.strip()

        rerank_query_texts = [
            "Cash",
            "Accounts Receivable",
            "Inventory",
            "Other Assets",
            "Property",
            "Goodwill",
            "Intangible",
            "Other Liabilities",
            "Payable",
            "Debt",
            # "consolidated balance sheet",
            # "balance sheet",
            # "total assets",
            # "total liabilities",
        ]
        rerank_query_texts = [normalize_term(term) for term in rerank_query_texts]

        result = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_size=None,
            score_threshold=0.3,
            pages_before=1,  # Include 1 page before the best chunk
            pages_after=1,  # Include 1 page after the best chunk
            rerank_top_k=5,
            rerank_query_texts=rerank_query_texts,
            ignore_front_fraction=ignore_front_fraction,
            ignore_back_fraction=ignore_back_fraction,
            chunk_rank=chunk_rank,
        )
        # Handle both old (2-tuple) and new (3-tuple) return formats for backward compatibility
        if len(result) == 2:
            return result[0], result[1], None
        return result

    except Exception as e:
        print(f"Error finding balance sheet section: {str(e)}")
        return None, None, None


def extract_balance_sheet_llm(text: str, time_period: str, currency: str | None = None) -> dict:
    """
    Use LLM to extract balance sheet line items exactly line by line.

    Args:
        text: Text containing balance sheet
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known

    Returns:
        Dictionary with balance sheet data
    """
    prompt = f"""Extract the balance sheet from the following document text for the time period: {time_period}.
Extract the balance sheet exactly line by line, including all line items and their values.
If the company is foreign, extract the values in the local currency.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null or omit that field
- Extract line items ONLY from the balance sheet table/section in the document text
- DO NOT use any external knowledge or assumptions
- Every line_value must correspond to an actual number shown in the document text
- If currency or unit is not explicitly stated in the document, use null

Return a JSON object with the following structure:
{{
    "currency": currency code (extract ONLY if explicitly stated in document, otherwise null),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract ONLY if explicitly stated like "in millions", "in thousands", etc., otherwise null),
    "time_period": "{time_period}",
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string) - MUST match exactly what is shown in the document,
            "line_category": one of ["Current Assets", "Non-Current Assets", "Total Assets", "Current Liabilities", "Non-Current Liabilities", "Total Liabilities", "Equity", "Total Liabilities and Equity"]
        }},
        ...
    ]
}}

IMPORTANT:
- Extract values exactly as they appear in the document (including negative values if present)
- DO NOT round, estimate, or modify values - use them exactly as written
- Include all subtotals (Current Assets, Total Assets, Current Liabilities, Total Liabilities, Total Equity, Total Liabilities and Equity) ONLY if they appear in the document
- Maintain the exact order of line items as they appear in the document
- Extract the currency code ONLY if explicitly stated in the document text
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- If you cannot find a specific value in the document text, DO NOT make it up - use null or omit it

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        # Ensure line_items exists and is a list
        if "line_items" not in result:
            result["line_items"] = []
        elif not isinstance(result["line_items"], list):
            result["line_items"] = []

        return result

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting balance sheet: {str(e)}")


def extract_balance_sheet_llm_with_feedback(
    text: str,
    time_period: str,
    previous_extraction: dict,
    validation_errors: list[str],
    currency: str | None = None,
) -> dict:
    """
    Use LLM to extract balance sheet with validation error feedback for retry.

    Args:
        text: Text containing balance sheet
        time_period: Time period (e.g., "Q3 2023")
        previous_extraction: Previous extraction attempt (to show what was extracted)
        validation_errors: List of validation errors with calculated differences
        currency: Currency code if known

    Returns:
        Dictionary with balance sheet data
    """
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    previous_items_text = json.dumps(previous_extraction.get("line_items", []), indent=2)

    prompt = f"""Extract the balance sheet from the following document text for the time period: {time_period}.
Extract the balance sheet exactly line by line, including all line items and their values.
If the company is foreign, extract the values in the local currency.

PREVIOUS EXTRACTION ATTEMPT:
{previous_items_text}

VALIDATION ERRORS (with calculated differences):
{errors_text}

Please review the previous extraction and fix the issues. Pay special attention to:
- Ensuring all line items are extracted correctly
- Checking that line item values match what's in the document
- Verifying that totals match the sum of their components
- Making sure line categories are correct

Return a JSON object with the following structure:
{{
    "currency": currency code (extract from document),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["Current Assets", "Non-Current Assets", "Total Assets", "Current Liabilities", "Non-Current Liabilities", "Total Liabilities", "Equity", "Total Liabilities and Equity"]
        }},
        ...
    ]
}}

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- Every line_value must correspond to an actual number shown in the document text
- If a value is not visible in the document text, use null or omit that field
- DO NOT use any external knowledge or assumptions

IMPORTANT:
- Extract values exactly as they appear in the document (including negative values if present)
- DO NOT round, estimate, or modify values - use them exactly as written
- Include all subtotals (Current Assets, Total Assets, Current Liabilities, Total Liabilities, Total Equity, Total Liabilities and Equity) ONLY if they appear in the document
- Maintain the exact order of line items as they appear in the document
- Extract the currency code ONLY if explicitly stated in the document text
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- Carefully review the validation errors and fix the issues in your extraction, but ONLY by correcting values that actually appear in the document text - do not invent new values

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        # Ensure line_items exists and is a list
        if "line_items" not in result:
            result["line_items"] = []
        elif not isinstance(result["line_items"], list):
            result["line_items"] = []

        return result

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting balance sheet: {str(e)}")


def validate_balance_sheet_section(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate balance sheet section (Stage 1): Check minimum line count and presence of key lines.
    This is used to validate that the correct section was found before proceeding to extraction validation.

    Args:
        line_items: List of balance sheet line items

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check if line_items is empty
    if not line_items or len(line_items) == 0:
        errors.append("Balance sheet is empty - no line items extracted")
        return False, errors

    # Check if we have at least some meaningful line items (not just empty strings)
    valid_items = [
        item for item in line_items if item.get("line_name") and item.get("line_name").strip()
    ]
    if len(valid_items) == 0:
        errors.append("Balance sheet has no valid line items")
        return False, errors

    # Check minimum number of lines required
    MIN_LINES_REQUIRED = 10
    if len(valid_items) < MIN_LINES_REQUIRED:
        errors.append(
            f"Balance sheet must have at least {MIN_LINES_REQUIRED} line items, found {len(valid_items)}"
        )
        return False, errors

    # Check for key totals (at least one should be present)
    items_dict = {item["line_name"].lower(): item["line_value"] for item in line_items}

    def is_total_line_name(name_lower):
        """Check if line name represents a total (more precise matching)"""
        total_phrases = [
            "total current assets",
            "total assets",
            "total current liabilities",
            "total liabilities",
            "total equity",
            "total liabilities and equity",
            "total liabilities and shareholders",
            "total stockholder",
            "total shareholder",
        ]
        for phrase in total_phrases:
            if name_lower.startswith(phrase) or name_lower.startswith(phrase + " "):
                return True
        if re.search(r"\btotal\b", name_lower):
            if (
                name_lower.startswith("total ")
                or "total current" in name_lower
                or "total assets" in name_lower
                or "total liabilities" in name_lower
                or "total equity" in name_lower
            ):
                return True
        return False

    has_key_total = False
    has_cash = False
    for key, _value in items_dict.items():
        if is_total_line_name(key):
            if (
                "total assets" in key
                and "non-current" not in key
                and "current" not in key
                and "liabilities" not in key
            ):
                has_key_total = True
            elif (
                "total liabilities" in key
                and "non-current" not in key
                and "current" not in key
                and "equity" not in key
            ):
                has_key_total = True
            elif "total equity" in key and "liabilities" not in key:
                has_key_total = True

        # Check for cash line item (case-insensitive)
        if "cash" in key.lower():
            has_cash = True

    if not has_key_total:
        errors.append(
            "Balance sheet is missing key totals (Total Assets, Total Liabilities, or Total Equity)"
        )
        return False, errors

    if not has_cash:
        errors.append("Balance sheet is missing a cash line item")
        return False, errors

    return True, []


def validate_balance_sheet_calculations(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate balance sheet calculations (Stage 2): Check that sums match reported totals.
    This is used after section validation passes to verify extraction accuracy.

    Args:
        line_items: List of balance sheet line items

    Returns:
        Tuple of (is_valid, list_of_errors_with_differences)
    """
    errors = []

    # Convert to dictionary for easier lookup
    items_dict = {item["line_name"].lower(): item["line_value"] for item in line_items}

    # Find key totals
    current_assets = None
    total_assets = None
    current_liabilities = None
    total_liabilities = None
    total_equity = None
    total_liabilities_equity = None

    # Helper function to check if a line name is a total line
    # More precise: checks if "total" appears as a distinct word at the start or as part of a total phrase
    def is_total_line_name(name_lower):
        """Check if line name represents a total (more precise matching)"""
        # Check for exact total phrases at the start of the name
        total_phrases = [
            "total current assets",
            "total assets",
            "total current liabilities",
            "total liabilities",
            "total equity",
            "total liabilities and equity",
            "total liabilities and shareholders",
            "total stockholder",
            "total shareholder",
        ]
        # Check if name starts with any total phrase
        for phrase in total_phrases:
            if name_lower.startswith(phrase) or name_lower.startswith(phrase + " "):
                return True
        # Also check if "total" appears as a distinct word (not part of another word)
        # Match "total" as a whole word (not part of "totally", "totaled", etc.)
        if re.search(r"\btotal\b", name_lower):
            # But exclude if it's clearly not a total line (e.g., "accounts receivable, net (total...")
            # Only consider it a total if "total" appears near the start or with key financial terms
            if (
                name_lower.startswith("total ")
                or "total current" in name_lower
                or "total assets" in name_lower
                or "total liabilities" in name_lower
                or "total equity" in name_lower
            ):
                return True
        return False

    for key, value in items_dict.items():
        # Use more precise matching for totals
        if is_total_line_name(key):
            # Check for "total current assets" - must contain both "total" and "current assets", but NOT "non-current"
            if (
                "current assets" in key
                and "non-current" not in key
                and "total non-current assets" not in key
            ):
                current_assets = value
            # Check for "total assets" - must contain "total assets" but NOT "non-current", "current", or "liabilities"
            elif (
                "total assets" in key
                and "non-current" not in key
                and "current" not in key
                and "liabilities" not in key
                and "total non-current assets" not in key
            ):
                total_assets = value
            # Check for "total current liabilities" - must contain both "total" and "current liabilities", but NOT "non-current"
            elif (
                "current liabilities" in key
                and "non-current" not in key
                and "total non-current liabilities" not in key
            ):
                current_liabilities = value
            # Check for "total liabilities" - must contain "total liabilities" but NOT "non-current", "current", or "equity"
            elif (
                "total liabilities" in key
                and "non-current" not in key
                and "current" not in key
                and "equity" not in key
                and "total non-current liabilities" not in key
            ):
                total_liabilities = value
            # Check for "total equity" - must contain "total equity" but NOT "liabilities"
            elif "total equity" in key and "liabilities" not in key:
                total_equity = value
            # Check for "total liabilities and equity" or "total liabilities and shareholders"
            elif (
                "total liabilities and equity" in key or "total liabilities and shareholders" in key
            ):
                total_liabilities_equity = value

    # Calculate sums from line items
    # Only sum base line items, exclude any totals or subtotals
    # Exclude items that are totals themselves (by name or category)
    def is_total_item(item):
        """Check if an item is a total/subtotal line (more precise)"""
        name_lower = item["line_name"].lower()
        category = item.get("line_category", "")

        # Use the same precise matching function
        if is_total_line_name(name_lower):
            return True

        # Also check category
        if "Total" in category:
            return True

        # Check for other total indicators (subtotal, sum) as whole words
        if re.search(r"\bsubtotal\b", name_lower) or re.search(r"\bsum\b", name_lower):
            return True

        return False

    # Only include base line items (not totals) in the EXACT correct category
    # Be very explicit about category matching to avoid confusion
    current_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() == "Current Assets"
            and not is_total_item(item)
            and "non-current" not in item.get("line_name", "").lower()
        )
    )

    total_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() in ["Current Assets", "Non-Current Assets"]
            and not is_total_item(item)
        )
    )

    current_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() == "Current Liabilities"
            and not is_total_item(item)
            and "non-current" not in item.get("line_name", "").lower()
        )
    )

    total_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip()
            in ["Current Liabilities", "Non-Current Liabilities"]
            and not is_total_item(item)
        )
    )

    # Validate current assets
    if current_assets is not None:
        diff = abs(current_assets - current_assets_sum)
        if diff > 0.01:  # Allow small rounding differences
            errors.append(
                f"Current assets sum mismatch: reported={current_assets}, calculated={current_assets_sum}"
            )

    # Validate total assets
    if total_assets is not None:
        diff = abs(total_assets - total_assets_sum)
        if diff > 0.01:
            errors.append(
                f"Total assets sum mismatch: reported={total_assets}, calculated={total_assets_sum}"
            )

    # Validate current liabilities
    if current_liabilities is not None:
        diff = abs(current_liabilities - current_liabilities_sum)
        if diff > 0.01:
            errors.append(
                f"Current liabilities sum mismatch: reported={current_liabilities}, calculated={current_liabilities_sum}"
            )

    # Validate total liabilities
    if total_liabilities is not None:
        diff = abs(total_liabilities - total_liabilities_sum)
        if diff > 0.01:
            errors.append(
                f"Total liabilities sum mismatch: reported={total_liabilities}, calculated={total_liabilities_sum}"
            )

    # Validate balance sheet equation: Assets = Liabilities + Equity
    if total_assets is not None and total_liabilities is not None and total_equity is not None:
        liabilities_equity_sum = total_liabilities + total_equity
        diff = abs(total_assets - liabilities_equity_sum)
        if diff > 0.01:
            errors.append(
                f"Balance sheet equation mismatch: Assets={total_assets}, Liabilities+Equity={liabilities_equity_sum}"
            )

    # Validate total liabilities and equity
    if total_liabilities_equity is not None and total_assets is not None:
        diff = abs(total_assets - total_liabilities_equity)
        if diff > 0.01:
            errors.append(
                f"Total liabilities and equity mismatch: reported={total_liabilities_equity}, should equal total assets={total_assets}"
            )

    # Check if we have at least one key total (total assets, total liabilities, or total equity)
    # This ensures we didn't get an empty or invalid balance sheet
    if total_assets is None and total_liabilities is None and total_equity is None:
        errors.append(
            "Balance sheet is missing key totals (Total Assets, Total Liabilities, or Total Equity)"
        )

    return len(errors) == 0, errors


def validate_balance_sheet(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Combined validation function for backward compatibility.
    Validates both section and calculations.

    Args:
        line_items: List of balance sheet line items

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    # First validate section
    section_valid, section_errors = validate_balance_sheet_section(line_items)
    if not section_valid:
        return False, section_errors

    # Then validate calculations
    calc_valid, calc_errors = validate_balance_sheet_calculations(line_items)
    return calc_valid, calc_errors


def check_balance_sheet_completeness_llm(text: str, time_period: str) -> bool:
    """
    Use LLM to check if the chunk text contains a complete consolidated balance sheet.
    This is called BEFORE extraction to validate we have the right chunk.

    Args:
        text: Text containing balance sheet section (chunk text)
        time_period: Time period (e.g., "Q3 2023")

    Returns:
        True if complete, False otherwise
    """
    prompt = f"""Analyze the following document text to determine if it contains a COMPLETE consolidated balance sheet starting from cash to total shareholder's equity for the time period: {time_period}.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY use information from the provided document text below
- DO NOT use external knowledge or assumptions
- Base your assessment ONLY on what is provided in the text

A COMPLETE consolidated balance sheet should:
- Start with cash or cash equivalents
- Include current assets (cash, accounts receivable, inventory, etc.)
- Include non-current assets (property, plant & equipment, intangible assets, etc.)
- Have a "Total Assets" line
- Include current liabilities (accounts payable, short-term debt, etc.)
- Include non-current liabilities (long-term debt, etc.)
- Have a "Total Liabilities" line
- Include equity items (common stock, retained earnings, etc.)
- Have a "Total Liabilities and Equity" or "Total Shareholder's Equity" line
- Balance (Total Assets = Total Liabilities and Equity)
- Avoid smaller informational tables that do not have the complete information

Document text:
{text[:10000]}

Return a JSON object:
{{
    "is_complete": true or false,
    "reason": "brief explanation of why it is or is not complete (only if not complete)"
}}

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for completeness check to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        return result.get("is_complete", False)
    except Exception as e:
        print(f"Error checking balance sheet completeness: {str(e)}")
        # If check fails, default to False (not complete) to be safe
        return False


def normalize_line_name(name: str) -> str:
    """
    Normalize a line item name for matching: trim, case-insensitive,
    collapse whitespace, remove leading/trailing punctuation.
    """
    if not name:
        return ""
    # Trim
    normalized = name.strip()
    # Case-insensitive (convert to lowercase)
    normalized = normalized.lower()
    # Collapse repeated whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    # Remove leading/trailing punctuation
    normalized = normalized.strip(".,;:!?()[]{}")
    return normalized


def get_balance_sheet_llm_insights(
    line_items: list[dict],
) -> tuple[dict, list[str]]:
    """
    Use LLM to identify key line items in a balance sheet.
    This function is used during post-processing to identify and standardize line item names.
    """
    if not line_items:
        return {}, []

    line_items_text = "\n".join(
        [
            f"{idx + 1}. {item['line_name']} | {item['line_value']}"
            for idx, item in enumerate(line_items)
        ]
    )

    prompt = f"""You are analyzing a balance sheet. Identify key line items by name.
Return ONLY valid JSON using the exact line names provided.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY match line items that ACTUALLY appear in the provided line items list below
- DO NOT invent line names - use null if a line item is not found in the list
- Match line names exactly as they appear in the list (case-sensitive matching is preferred)

Line items:
{line_items_text}

Return this JSON structure:
{{
    "cash_and_equivalents_line": "exact line name for cash and cash equivalents (must match a name from the list above, or null if not found)",
    "other_current_assets_line": "exact line name for other current assets (must match a name from the list above, or null if not found)",
    "total_current_assets_line": "exact line name for total current assets (must match a name from the list above, or null if not found)",
    "other_non_current_assets_line": "exact line name for other non-current assets (must match a name from the list above, or null if not found)",
    "other_current_liabilities_line": "exact line name for other current liabilities (must match a name from the list above, or null if not found)",
    "total_current_liabilities_line": "exact line name for total current liabilities (must match a name from the list above, or null if not found)",
    "other_non_current_liabilities_line": "exact line name for other non-current liabilities (must match a name from the list above, or null if not found)",
    "total_liabilities_line": "exact line name for total liabilities (must match a name from the list above, or null if not found)",
    "common_equity_line": "exact line name for common equity or common stockholders' equity (must match a name from the list above, or null if not found)",
    "total_equity_line": "exact line name for total equity or total shareholders' equity (must match a name from the list above, or null if not found)",
    "total_shareholder_equity_line": "exact line name for total shareholder's equity or total liabilities and equity (must match a name from the list above, or null if not found)"
}}

Guidance for matching (but only use names that actually appear in the list above):
- Cash and equivalents may be labeled as: Cash and cash equivalents, Cash and equivalents, Cash
- Other current assets may be labeled as: Other current assets, Other current assets, net
- Total current assets may be labeled as: Total current assets, Current assets
- Other non-current assets may be labeled as: Other non-current assets, Other assets, Other long-term assets
- Other current liabilities may be labeled as: Other current liabilities, Other accrued liabilities
- Total current liabilities may be labeled as: Total current liabilities, Current liabilities
- Other non-current liabilities may be labeled as: Other non-current liabilities, Other long-term liabilities
- Total liabilities may be labeled as: Total liabilities, Total liabilities
- Common equity may be labeled as: Common equity, Common stockholders' equity, Common equity (deficit)
- Total equity may be labeled as: Total equity, Total stockholders' equity, Total shareholders' equity
- Total shareholder equity may be labeled as: Total liabilities and equity, Total liabilities and shareholders' equity

Return only JSON with no extra text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        insights = json.loads(response_text)
        return (
            {
                "cash_and_equivalents_line": insights.get("cash_and_equivalents_line"),
                "other_current_assets_line": insights.get("other_current_assets_line"),
                "total_current_assets_line": insights.get("total_current_assets_line"),
                "other_non_current_assets_line": insights.get("other_non_current_assets_line"),
                "other_current_liabilities_line": insights.get("other_current_liabilities_line"),
                "total_current_liabilities_line": insights.get("total_current_liabilities_line"),
                "other_non_current_liabilities_line": insights.get(
                    "other_non_current_liabilities_line"
                ),
                "total_liabilities_line": insights.get("total_liabilities_line"),
                "common_equity_line": insights.get("common_equity_line"),
                "total_equity_line": insights.get("total_equity_line"),
                "total_shareholder_equity_line": insights.get("total_shareholder_equity_line"),
            },
            [],
        )
    except Exception as exc:
        return {}, [f"LLM insights unavailable: {str(exc)}"]


def post_process_balance_sheet_line_items(line_items: list[dict]) -> list[dict]:
    """
    Post-process balance sheet line items:
    1. Use LLM to identify key line items
    2. Rename identified items with standardized names (original in parentheses)

    Returns:
        Processed line items with standardized names
    """
    if not line_items:
        return line_items

    # Step 1: Get LLM insights to identify key line items
    llm_insights, _ = get_balance_sheet_llm_insights(line_items=line_items)

    # Mapping of standardized names to LLM insight keys
    standard_names = {
        "cash_and_equivalents_line": "Cash & Equivalents",
        "other_current_assets_line": "Other Current Assets",
        "total_current_assets_line": "Total Current Assets",
        "other_non_current_assets_line": "Other Non-Current Assets",
        "other_current_liabilities_line": "Other Current Liabilities",
        "total_current_liabilities_line": "Total Current Liabilities",
        "other_non_current_liabilities_line": "Other Non-Current Liabilities",
        "total_liabilities_line": "Total Liabilities",
        "common_equity_line": "Common Equity",
        "total_equity_line": "Total Equity",
        "total_shareholder_equity_line": "Total Equity",
    }

    # Step 2: Rename identified line items
    processed_items = []
    renamed_indices = set()

    for item in line_items:
        item_copy = item.copy()

        # Check if this item matches any of the identified key items
        for insight_key, standard_name in standard_names.items():
            llm_line_name = llm_insights.get(insight_key)
            if llm_line_name:
                # Use exact match first, then normalized match
                item_name = item.get("line_name", "")
                if item_name == llm_line_name or normalize_line_name(
                    item_name
                ) == normalize_line_name(llm_line_name):
                    # Rename: "Standard Name (Original Name)"
                    original_name = item_copy.get("line_name", "")
                    item_copy["line_name"] = f"{standard_name} ({original_name})"
                    renamed_indices.add(len(processed_items))
                    break

        processed_items.append(item_copy)

    return processed_items


def classify_line_items_llm(line_items: list[dict]) -> list[dict]:
    """
    Use LLM to categorize each balance sheet line item as operating or non-operating.

    Args:
        line_items: List of balance sheet line items

    Returns:
        List of line items with is_operating field added
    """

    def _is_total_or_subtotal(item: dict) -> bool:
        category = (item.get("line_category") or "").lower()
        if "total" in category:
            return True
        line_name = normalize_line_name(item.get("line_name", ""))
        total_keywords = [
            "total current assets",
            "total assets",
            "total current liabilities",
            "total liabilities",
            "total liabilities and equity",
            "total liabilities and shareholders equity",
            "total liabilities and stockholder equity",
            "total liabilities and stockholders equity",
            "total equity",
            "total shareholders equity",
            "total stockholders equity",
        ]
        return any(keyword in line_name for keyword in total_keywords)
    # AUTHORITATIVE_LOOKUP - binding decision table
    AUTHORITATIVE_LOOKUP = {
        "Cash and cash equivalents": "Non-Operating",
        "Marketable securities / Short-term investments": "Non-Operating",
        "Restricted cash": "Non-Operating",
        "Accounts receivable": "Operating",
        "Notes receivable (trade-related)": "Operating",
        "Inventories": "Operating",
        "Prepaid expenses": "Operating",
        "Other current assets": "Operating",
        "Property, plant and equipment (PPE)": "Operating",
        "Operating lease right-of-use assets": "Non-Operating",
        "Goodwill": "Non-Operating",
        "Intangible assets": "Non-Operating",
        "Long-term investments / Equity method investments": "Non-Operating",
        "Deferred tax assets": "Operating",
        "Other non-current assets": "Operating",
        "Accounts payable": "Operating",
        "Accrued expenses / Accrued liabilities": "Operating",
        "Unearned revenue / Deferred revenue": "Operating",
        "Short-term debt": "Non-Operating",
        "Current portion of long-term debt": "Non-Operating",
        "Current lease liabilities": "Non-Operating",
        "Other current liabilities": "Operating",
        "Long-term debt": "Non-Operating",
        "Non-current lease liabilities": "Non-Operating",
        "Deferred tax liabilities": "Operating",
        "Pension liabilities / Postretirement obligations": "Operating",
        "Other long-term liabilities": "Operating",
        "Common stock / Paid-in capital": "Non-Operating",
        "Retained earnings": "Non-Operating",
        "Treasury stock": "Non-Operating",
        "Accumulated other comprehensive income (AOCI)": "Non-Operating",
        "Noncontrolling interests": "Non-Operating",
        "Deferred compensation / Stock-based compensation liability": "Operating",
        "Customer deposits": "Operating",
        "Contract liabilities": "Operating",
        "Income taxes payable": "Operating",
        "Accrued payroll / Accrued compensation": "Operating",
        "Derivative assets/liabilities": "Non-Operating",
    }

    # Create normalized lookup map
    normalized_lookup = {normalize_line_name(k): v for k, v in AUTHORITATIVE_LOOKUP.items()}

    # Prepare lookup context for prompt
    lookup_context = "\n".join([f'  "{k}": "{v}"' for k, v in AUTHORITATIVE_LOOKUP.items()])

    prompt = f"""Classify each balance sheet line item as either "operating" or "non-operating" based on whether it relates to the company's core business operations.

HIGHEST PRIORITY: Use the AUTHORITATIVE_LOOKUP below as a binding decision table.
- If a provided line item matches a key in AUTHORITATIVE_LOOKUP after normalization, you MUST use that value.
- Normalization: trim, case-insensitive, collapse repeated whitespace, remove leading/trailing punctuation.
- If no match: use the fallback heuristics.
- If still uncertain: use best judgement.

FALLBACK HEURISTICS (only when no lookup match):
- Cash, marketable securities, debt, equity, goodwill, intangibles, lease ROU assets/liabilities -> Non-Operating
- Working capital items (AR, inventory, AP, accrued op expenses), PPE -> Operating
- Deferred taxes -> Operating (unless clearly financing-related)
- If mixed/ambiguous -> Unknown

AUTHORITATIVE_LOOKUP:
{{
{lookup_context}
}}

Balance sheet line items to classify:
{json.dumps([{"line_name": item["line_name"], "line_category": item["line_category"]} for item in line_items], indent=2)}

Return a JSON array with the same order as the input, where each item has:
{{
    "line_name": "exact name from input",
    "is_operating": true or false
}}

Return only valid JSON array, no additional text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        classifications = json.loads(response_text)

        # Map classifications back to line items
        classification_map = {item["line_name"]: item["is_operating"] for item in classifications}

        # Add is_operating to each line item, using lookup first if available
        for item in line_items:
            line_name = item["line_name"]
            normalized_name = normalize_line_name(line_name)

            # First try authoritative lookup
            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                item["is_operating"] = lookup_value == "Operating"
            # Then use LLM classification if available
            elif line_name in classification_map:
                item["is_operating"] = classification_map[line_name]
            else:
                # Default fallback: use heuristics
                # Cash, marketable securities, debt, equity, goodwill, intangibles, lease ROU -> Non-Operating
                line_lower = line_name.lower()
                if any(
                    keyword in line_lower
                    for keyword in [
                        "cash",
                        "marketable",
                        "securities",
                        "short-term investment",
                        "restricted cash",
                        "debt",
                        "loan",
                        "borrowing",
                        "equity",
                        "stock",
                        "treasury",
                        "goodwill",
                        "intangible",
                        "lease",
                        "right-of-use",
                        "rou asset",
                        "rou liability",
                    ]
                ):
                    item["is_operating"] = False
                # Working capital items, PPE -> Operating
                elif any(
                    keyword in line_lower
                    for keyword in [
                        "accounts receivable",
                        "inventory",
                        "inventories",
                        "accounts payable",
                        "accrued",
                        "prepaid",
                        "ppe",
                        "property",
                        "plant",
                        "equipment",
                    ]
                ):
                    item["is_operating"] = True
                # Default to operating
                else:
                    item["is_operating"] = True

        for item in line_items:
            if _is_total_or_subtotal(item):
                item["is_operating"] = None
        return line_items

    except Exception as e:
        print(f"Error classifying line items: {str(e)}")
        # Fallback: use lookup if available, otherwise default to operating
        for item in line_items:
            line_name = item["line_name"]
            normalized_name = normalize_line_name(line_name)

            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                item["is_operating"] = lookup_value == "Operating"
            else:
                # Default to operating if classification fails
                item["is_operating"] = True
        for item in line_items:
            if _is_total_or_subtotal(item):
                item["is_operating"] = None
        return line_items


def extract_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 3,
    document_type: str | None = None,
) -> dict:
    """
    Main function to extract balance sheet with two-stage validation and retries.

    Stage 1: Find correct section (retry with rank 1, 2, 3 chunks)
    Stage 2: Validate extraction calculations (retry extraction with LLM feedback)

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts for section finding (3 total: rank 1, 2, 3)
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Dictionary with balance sheet data and validation status
    """
    # Stage 1: Find correct section (retry with different chunk ranks)
    balance_sheet_text = None
    start_page = None
    log_info = None
    successful_chunk_index = None  # Track successful chunk index for income statement extraction

    for section_attempt in range(max_retries):  # 3 tries: rank 0, 1, 2
        try:
            section_msg = f"Stage 1: Finding balance sheet section (rank {section_attempt + 1})"
            print(section_msg)
            add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, section_msg)

            # Find balance sheet section using embeddings
            balance_sheet_text, start_page, log_info = find_balance_sheet_section(
                document_id, file_path, time_period, document_type, chunk_rank=section_attempt
            )

            if not balance_sheet_text:
                # Fallback: extract full document if embedding search fails
                fallback_msg = "Embedding search failed, extracting full document..."
                print(fallback_msg)
                add_log(
                    document_id, FinancialStatementMilestone.BALANCE_SHEET, fallback_msg
                )
                balance_sheet_text, _, _ = extract_text_from_pdf(file_path, max_pages=None)
                balance_sheet_text = balance_sheet_text[:50000]  # Limit to 50k chars
                extracted_msg = f"Extracted {len(balance_sheet_text)} characters from full document"
                print(extracted_msg)
                add_log(
                    document_id, FinancialStatementMilestone.BALANCE_SHEET, extracted_msg
                )
            else:
                # Log chunk/page information if available
                if log_info:
                    rank_text = f" (rank {section_attempt + 1})" if section_attempt > 0 else ""
                    chunk_msg = f"Best match{rank_text}: chunk {log_info['best_chunk_index']} (pages {log_info['chunk_start_page']}-{log_info['chunk_end_page']})"
                    print(chunk_msg)
                    add_log(
                        document_id, FinancialStatementMilestone.BALANCE_SHEET, chunk_msg
                    )
                    pages_msg = f"Found balance sheet section (pages {log_info['start_extract_page']}-{log_info['end_extract_page']})"
                    print(pages_msg)
                    add_log(
                        document_id, FinancialStatementMilestone.BALANCE_SHEET, pages_msg
                    )
                found_msg = f"Found balance sheet section starting at page {start_page}, extracted {len(balance_sheet_text)} characters"
                print(found_msg)
                add_log(
                    document_id, FinancialStatementMilestone.BALANCE_SHEET, found_msg
                )

            # Stage 1 validation: Check completeness of chunk text using LLM (before extraction)
            completeness_check_msg = (
                "Stage 1: Checking if chunk contains complete balance sheet using LLM"
            )
            print(completeness_check_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                completeness_check_msg,
            )

            is_complete = check_balance_sheet_completeness_llm(balance_sheet_text, time_period)

            if not is_complete:
                section_failed_msg = "Stage 1 validation failed: LLM determined chunk does not contain complete balance sheet"
                print(section_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    section_failed_msg,
                )
                if section_attempt < max_retries - 1:
                    continue  # Try next chunk rank
                else:
                    # All section attempts failed, need to create empty extracted_data for error handling
                    extracted_data = {
                        "line_items": [],
                        "currency": None,
                        "unit": None,
                        "time_period": time_period,
                    }
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = [
                        "Balance sheet completeness check failed"
                    ]
                    return extracted_data

            # Extract balance sheet using LLM (only if chunk is complete)
            extraction_msg = "Extracting balance sheet from complete chunk"
            print(extraction_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                extraction_msg,
            )

            extracted_data = extract_balance_sheet_llm(balance_sheet_text, time_period)

            # Ensure line_items exists and is a list
            if "line_items" not in extracted_data:
                extracted_data["line_items"] = []
            elif not isinstance(extracted_data["line_items"], list):
                print(
                    f"Warning: line_items is not a list, got {type(extracted_data['line_items'])}"
                )
                extracted_data["line_items"] = []

            extracted_count_msg = (
                f"Extracted {len(extracted_data.get('line_items', []))} line items"
            )
            print(extracted_count_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                extracted_count_msg,
            )

            # Post-process to add standard names
            extracted_data["line_items"] = post_process_balance_sheet_line_items(
                extracted_data["line_items"]
            )

            section_valid_msg = (
                "Stage 1 validation passed (complete balance sheet chunk found and extracted)"
            )
            print(section_valid_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                section_valid_msg,
            )
            # Store successful chunk index for income statement extraction
            successful_chunk_index = log_info.get("best_chunk_index") if log_info else None
            break  # Section found and validated, proceed to Stage 2

        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(
                keyword in error_str
                for keyword in [
                    "rate limit",
                    "quota",
                    "429",
                    "503",
                    "resource exhausted",
                    "service unavailable",
                    "too many requests",
                ]
            )
            if is_api_error:
                print(f"API error on section attempt {section_attempt + 1}: {str(e)}")
                raise
            print(f"Error on section attempt {section_attempt + 1}: {str(e)}")
            if section_attempt == max_retries - 1:
                raise

    if not balance_sheet_text:
        raise Exception("Failed to find balance sheet section after all attempts")

    # Stage 2: Validate extraction calculations (retry extraction with LLM feedback)
    EXTRACTION_MAX_RETRIES = 3
    # extracted_data was already set in Stage 1 and validated for completeness
    calc_errors = []  # Will be set by validation

    # Store successful chunk index in extracted_data for income statement extraction and persistence
    if successful_chunk_index is not None:
        extracted_data["balance_sheet_chunk_index"] = successful_chunk_index
        extracted_data["chunk_index"] = successful_chunk_index  # Also store for persistence

    for extraction_attempt in range(EXTRACTION_MAX_RETRIES):
        try:
            if extraction_attempt == 0:
                # First attempt: use initial extraction from Stage 1
                extraction_msg = "Stage 2: Validating extraction calculations"
                print(extraction_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    extraction_msg,
                )
                # extracted_data is already set from Stage 1
            else:
                # Retry with feedback from previous attempt
                retry_msg = f"Stage 2: Retry extraction {extraction_attempt + 1}/{EXTRACTION_MAX_RETRIES} with LLM feedback"
                print(retry_msg)
                add_log(
                    document_id, FinancialStatementMilestone.BALANCE_SHEET, retry_msg
                )
                # Re-extract with validation error feedback from previous attempt
                extracted_data = extract_balance_sheet_llm_with_feedback(
                    balance_sheet_text,
                    time_period,
                    extracted_data,  # Previous extraction
                    calc_errors,  # Validation errors with differences from previous attempt
                )

            # Stage 2 validation: Check calculations (sums)
            calc_valid, calc_errors = validate_balance_sheet_calculations(
                extracted_data["line_items"]
            )

            if calc_valid:
                calc_valid_msg = "Stage 2 validation passed (calculations are correct)"
                print(calc_valid_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    calc_valid_msg,
                )
                # Both stages passed, classify and return
                classified_items = classify_line_items_llm(extracted_data["line_items"])
                extracted_data["line_items"] = classified_items
                extracted_data["is_valid"] = True
                extracted_data["validation_errors"] = []
                # Ensure chunk_index is included in the return value
                if successful_chunk_index is not None:
                    extracted_data["chunk_index"] = successful_chunk_index
                return extracted_data
            else:
                calc_failed_msg = f"Stage 2 validation failed: {', '.join(calc_errors[:2])}"
                print(calc_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    calc_failed_msg,
                )
                if extraction_attempt < EXTRACTION_MAX_RETRIES - 1:
                    continue  # Retry with feedback
                else:
                    # All extraction attempts failed, return with errors
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = calc_errors
                    # Ensure chunk_index is included in the return value
                    if successful_chunk_index is not None:
                        extracted_data["chunk_index"] = successful_chunk_index
                    return extracted_data

        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(
                keyword in error_str
                for keyword in [
                    "rate limit",
                    "quota",
                    "429",
                    "503",
                    "resource exhausted",
                    "service unavailable",
                    "too many requests",
                ]
            )
            if is_api_error:
                print(f"API error on extraction attempt {extraction_attempt + 1}: {str(e)}")
                raise
            print(f"Error on extraction attempt {extraction_attempt + 1}: {str(e)}")
            if extraction_attempt == EXTRACTION_MAX_RETRIES - 1:
                raise

    raise Exception("Failed to extract balance sheet after all attempts")

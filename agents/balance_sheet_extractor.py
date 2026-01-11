"""
Balance sheet extraction agent using Gemini LLM and embeddings
"""

import json
import re

from agents.extractor_utils import (
    call_llm_and_parse_json,
    call_llm_with_retry,
    check_section_completeness_llm,
    get_llm_insights_generic,
)
from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.line_item_utils import extract_original_name_from_standardized as get_orig_name
from app.utils.line_item_utils import normalize_line_name


def extract_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 3,
    document_type: str | None = None,
    period_end_date: str | None = None,
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

            # Log chunk/page information if available
            if log_info:
                rank_text = f" (rank {section_attempt + 1})" if section_attempt > 0 else ""
                chunk_msg = f"Best match{rank_text}: chunk {log_info['best_chunk_index']} (pages {log_info['chunk_start_page']}-{log_info['chunk_end_page']})"
                print(chunk_msg)
                add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, chunk_msg)
                pages_msg = f"Found balance sheet section (pages {log_info['start_extract_page']}-{log_info['end_extract_page']})"
                print(pages_msg)
                add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, pages_msg)
            found_msg = f"Found balance sheet section starting at page {start_page}, extracted {len(balance_sheet_text)} characters"
            print(found_msg)
            add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, found_msg)

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

            is_complete, reason = check_balance_sheet_completeness_llm(
                balance_sheet_text, time_period, period_end_date
            )

            if not is_complete:
                section_failed_msg = f"Stage 1 validation failed: {reason}"
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
                        "is_valid": False,
                        "validation_errors": ["Balance sheet completeness check failed"],
                        "time_period": time_period,
                    }
                    return extracted_data

            # Extract balance sheet using LLM (only if chunk is complete)
            extraction_msg = "Extracting balance sheet from complete chunk"
            print(extraction_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                extraction_msg,
            )

            extracted_data = extract_balance_sheet_llm(
                balance_sheet_text, time_period, currency=None, period_end_date=period_end_date
            )

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
    # extracted_data was already set in Stage 1 and validated for completeness
    calc_errors = []  # Will be set by validation

    # Store successful chunk index in extracted_data for income statement extraction and persistence
    if successful_chunk_index is not None:
        extracted_data["balance_sheet_chunk_index"] = successful_chunk_index
        extracted_data["chunk_index"] = successful_chunk_index  # Also store for persistence

    try:
        # Step 0: Initial Validation
        extraction_msg = "Stage 2: Validating extraction calculations"
        print(extraction_msg)
        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            extraction_msg,
        )

        # Post-process to add standard names
        extracted_data["line_items"] = post_process_balance_sheet_line_items(
            extracted_data["line_items"]
        )

        calc_valid, calc_errors = validate_balance_sheet_calculations(extracted_data["line_items"])

        # Step 1: If validation fails, check time periods and remove out-of-place items
        if not calc_valid:
            validation_error_str = "; ".join(calc_errors)
            time_check_msg = f"Validation failed ({validation_error_str}). Checking for out-of-period line items."
            print(time_check_msg)
            add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, time_check_msg)

            time_check_result = check_line_item_time_periods_balance_sheet(
                extracted_data["line_items"], time_period
            )
            mismatched_items = time_check_result.get("mismatched_items", [])

            if mismatched_items:
                # Remove out-of-place items
                mismatched_names = {item["line_name"] for item in mismatched_items}
                original_count = len(extracted_data["line_items"])
                extracted_data["line_items"] = [
                    item
                    for item in extracted_data["line_items"]
                    if item["line_name"] not in mismatched_names
                ]

                removed_msg = f"Removed {len(mismatched_items)} out-of-period items from {original_count} total items. Re-validating."
                print(removed_msg)
                add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, removed_msg)

                # Post-process and Re-validate after removal
                extracted_data["line_items"] = post_process_balance_sheet_line_items(
                    extracted_data["line_items"]
                )
                calc_valid, calc_errors = validate_balance_sheet_calculations(
                    extracted_data["line_items"]
                )

        # Step 2: If validation still fails, try one last retry with feedback
        if not calc_valid:
            retry_msg = "Validation still failed. Attempting final extraction with LLM feedback."
            print(retry_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                retry_msg,
            )

            # Re-extract with validation error feedback
            extracted_data = extract_balance_sheet_llm_with_feedback(
                balance_sheet_text,
                time_period,
                extracted_data,  # Previous extraction
                calc_errors,
                currency=None,
                period_end_date=period_end_date,
            )

            # Post-process and Re-validate final attempt
            extracted_data["line_items"] = post_process_balance_sheet_line_items(
                extracted_data["line_items"]
            )
            calc_valid, calc_errors = validate_balance_sheet_calculations(
                extracted_data["line_items"]
            )

        # Final Result Processing
        if calc_valid:
            success_msg = "Stage 2 validation passed"
            if calc_errors:
                success_msg += " (deduced valid despite warnings)"
            print(success_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                success_msg,
            )
        else:
            fail_msg = f"Stage 2 validation failed after retries: {', '.join(calc_errors[:2])}"
            print(fail_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                fail_msg,
            )

        extracted_data["is_valid"] = calc_valid
        extracted_data["validation_errors"] = calc_errors

        # Classify final items
        classified_items = classify_line_items_llm(extracted_data["line_items"])
        extracted_data["line_items"] = classified_items

        # Ensure chunk indices are included
        if successful_chunk_index is not None:
            extracted_data["chunk_index"] = successful_chunk_index
            extracted_data["balance_sheet_chunk_index"] = successful_chunk_index

        # Final sanity check: if no line items, it cannot be valid
        if not extracted_data.get("line_items"):
            extracted_data["is_valid"] = False
            if "validation_errors" not in extracted_data:
                extracted_data["validation_errors"] = []
            if "No line items extracted" not in extracted_data["validation_errors"]:
                extracted_data["validation_errors"].append("No line items extracted")

        return extracted_data

    except Exception as e:
        print(f"Error in Stage 2 extraction: {str(e)}")
        extracted_data["is_valid"] = False
        extracted_data["validation_errors"] = [str(e)]
        if successful_chunk_index is not None:
            extracted_data["chunk_index"] = successful_chunk_index
        return extracted_data


def _is_balance_sheet_total_line_name(name_lower: str) -> bool:
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
    if re.search(r"\btotal\b|\bsubtotal\b|\bsum\b", name_lower):
        if (
            name_lower.startswith("total ")
            or "total current" in name_lower
            or "total assets" in name_lower
            or "total liabilities" in name_lower
            or "total equity" in name_lower
            or "subtotal" in name_lower
            or "sum" in name_lower
        ):
            return True
    return False


def _is_total_or_subtotal_item(item: dict) -> bool:
    """Check if an item is a total/subtotal line based on name and category."""
    category = (item.get("line_category") or "").lower()
    if "total" in category:
        return True
    line_name = (item.get("line_name") or "").lower()
    return _is_balance_sheet_total_line_name(line_name)


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
            ignore_front_fraction = 0
            ignore_back_fraction = 0
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
        ]
        rerank_query_texts = [normalize_line_name(term) for term in rerank_query_texts]

        return find_document_section(
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

    except Exception as e:
        print(f"Error finding balance sheet section: {str(e)}")
        return None, None, None


def check_balance_sheet_completeness_llm(
    text: str, time_period: str, period_end_date: str | None = None
) -> tuple[bool, str]:
    """
    Use LLM to check if the chunk text contains a complete consolidated balance sheet.
    This is called BEFORE extraction to validate we have the right chunk.

    Args:
        text: Text containing balance sheet section (chunk text)
        time_period: Time period (e.g., "Q3 2023")
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Tuple of (is_complete, reason)
    """
    validation_criteria = """- Start with cash
- Have multiple asset lines with a total
- Have multiple liability lines with a total
- Have a "Total Liabilities and Equity line"""

    return check_section_completeness_llm(
        text, time_period, "consolidated balance sheet", validation_criteria, period_end_date
    )


def extract_balance_sheet_llm(
    text: str, time_period: str, currency: str | None = None, period_end_date: str | None = None
) -> dict:
    """
    Use LLM to extract balance sheet line items exactly line by line.

    Args:
        text: Text containing balance sheet
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with balance sheet data
    """
    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""Extract the balance sheet from the following document text for the {period_info}.
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
- If currency or unit is not stated in the document, use null

Return a JSON object with the following structure:
{{
    "currency": currency code,
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract ONLY if explicitly stated like "in millions", "in thousands", etc., otherwise null),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string) - MUST match exactly what is shown in the document,
            "line_category": one of [
                "Current Assets",
                "Total Current Assets",
                "Non-Current Assets",
                "Total Assets",
                "Current Liabilities",
                "Total Current Liabilities",
                "Non-Current Liabilities",
                "Total Liabilities",
                "Equity",
                "Total Liabilities and Equity",
            ]
        }},
        ...
    ]
}}

IMPORTANT:
- Extract values exactly as they appear in the document (including negative values if present)
- DO NOT round, estimate, or modify values - use them exactly as written
- Include all subtotals (Current Assets, Total Assets, Current Liabilities, Total Liabilities, Total Equity, Total Liabilities and Equity) ONLY if they appear in the document
- Maintain the exact order of line items as they appear in the document
- Extract the currency code
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- If you cannot find a specific value in the document text, DO NOT make it up - use null or omit it

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        result = call_llm_and_parse_json(prompt, temperature=0.0)

        # Ensure line_items exists and is a list
        if "line_items" not in result:
            result["line_items"] = []
        elif not isinstance(result["line_items"], list):
            result["line_items"] = []

        return result

    except Exception as e:
        raise Exception(f"Error extracting balance sheet: {str(e)}")


def extract_balance_sheet_llm_with_feedback(
    text: str,
    time_period: str,
    previous_extraction: dict,
    validation_errors: list[str],
    currency: str | None = None,
    period_end_date: str | None = None,
) -> dict:
    """
    Use LLM to extract balance sheet with validation error feedback for retry.

    Args:
        text: Text containing balance sheet
        time_period: Time period (e.g., "Q3 2023")
        previous_extraction: Previous extraction attempt (to show what was extracted)
        validation_errors: List of validation errors with calculated differences
        currency: Currency code if known
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with balance sheet data
    """
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    previous_items_text = json.dumps(previous_extraction.get("line_items", []), indent=2)

    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""Extract the balance sheet from the following document text for the {period_info}.
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
    "currency": currency code,
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["Current Assets", "Non-Current Assets", "Total Assets", "Current Liabilities", "Non-Current Liabilities", "Total Liabilities", "Equity", "Total Liabilities and Equity"]
        }}
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
- Extract the currency code
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- Carefully review the validation errors and fix the issues in your extraction, but ONLY by correcting values that actually appear in the document text - do not invent new values

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        result = call_llm_and_parse_json(prompt, temperature=0.0)

        # Ensure line_items exists and is a list
        if "line_items" not in result:
            result["line_items"] = []
        elif not isinstance(result["line_items"], list):
            result["line_items"] = []

        return result

    except Exception as e:
        raise Exception(f"Error extracting balance sheet: {str(e)}")


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
        "accounts_receivable_line": "Accounts Receivable",
        "inventory_line": "Inventory",
        "other_current_assets_line": "Other Current Assets",
        "total_current_assets_line": "Total Current Assets",
        "ppe_line": "Property, Plant & Equipment",
        "goodwill_intangible_line": "Goodwill & Intangible Assets",
        "other_non_current_assets_line": "Other Non-Current Assets",
        "total_assets_line": "Total Assets",
        "accounts_payable_line": "Accounts Payable",
        "short_term_debt_line": "Short-Term Debt",
        "other_current_liabilities_line": "Other Current Liabilities",
        "total_current_liabilities_line": "Total Current Liabilities",
        "long_term_debt_line": "Long-Term Debt",
        "other_non_current_liabilities_line": "Other Non-Current Liabilities",
        "total_liabilities_line": "Total Liabilities",
        "common_equity_line": "Common Equity",
        "retained_earnings_line": "Retained Earnings",
        "total_equity_line": "Total Equity",
        "total_liabilities_equity_line": "Total Liabilities & Equity",
    }

    # Step 2: Rename identified line items
    processed_items = []

    for item in line_items:
        item_copy = item.copy()
        current_name = item.get("line_name", "")

        # Check if this item matches any of the identified key items
        for insight_key, standard_name in standard_names.items():
            llm_line_name = llm_insights.get(insight_key)
            if llm_line_name:
                # Use exact match first, then normalized match
                if current_name == llm_line_name or normalize_line_name(
                    current_name
                ) == normalize_line_name(llm_line_name):
                    # Extract original name if it was already standardized, otherwise use current name
                    original_name = get_orig_name(current_name) or current_name

                    # Rename: "Standard Name (Original Name)"
                    # Only apply if it's not already standardized to THIS standard name
                    new_name = f"{standard_name} ({original_name})"
                    if current_name != new_name:
                        item_copy["line_name"] = new_name
                    break

        processed_items.append(item_copy)

    return processed_items


def get_balance_sheet_llm_insights(
    line_items: list[dict],
) -> tuple[dict, list[str]]:
    """
    Use LLM to identify key line items in a balance sheet.
    This function is used during post-processing to identify and standardize line item names.
    """
    json_structure = """{
    "cash_and_equivalents_line": "exact line name for cash and cash equivalents (must match a name from the list above, or null if not found)",
    "accounts_receivable_line": "exact line name for accounts receivable (must match a name from the list above, or null if not found)",
    "inventory_line": "exact line name for inventory (must match a name from the list above, or null if not found)",
    "other_current_assets_line": "exact line name for other current assets (must match a name from the list above, or null if not found)",
    "total_current_assets_line": "exact line name for total current assets (must match a name from the list above, or null if not found)",
    "ppe_line": "exact line name for property, plant and equipment (must match a name from the list above, or null if not found)",
    "goodwill_intangible_line": "exact line name for goodwill and intangible assets (must match a name from the list above, or null if not found)",
    "other_non_current_assets_line": "exact line name for other non-current assets (must match a name from the list above, or null if not found)",
    "total_assets_line": "exact line name for total assets (must match a name from the list above, or null if not found)",
    "accounts_payable_line": "exact line name for accounts payable (must match a name from the list above, or null if not found)",
    "short_term_debt_line": "exact line name for short-term debt (must match a name from the list above, or null if not found)",
    "other_current_liabilities_line": "exact line name for other current liabilities (must match a name from the list above, or null if not found)",
    "total_current_liabilities_line": "exact line name for total current liabilities (must match a name from the list above, or null if not found)",
    "long_term_debt_line": "exact line name for long-term debt (must match a name from the list above, or null if not found)",
    "other_non_current_liabilities_line": "exact line name for other non-current liabilities (must match a name from the list above, or null if not found)",
    "total_liabilities_line": "exact line name for total liabilities (must match a name from the list above, or null if not found)",
    "common_equity_line": "exact line name for common equity or common stockholders' equity (must match a name from the list above, or null if not found)",
    "retained_earnings_line": "exact line name for retained earnings (must match a name from the list above, or null if not found)",
    "total_equity_line": "exact line name for total equity or total shareholders' equity (must match a name from the list above, or null if not found)",
    "total_liabilities_equity_line": "exact line name for total liabilities and equity or total liabilities and shareholders' equity (must match a name from the list above, or null if not found)"
}"""

    guidance = """- Cash and equivalents: Cash and cash equivalents, Cash, Cash & Equivalents
- Accounts receivable: Accounts receivable, Trade receivables
- Inventory: Inventories, Inventory
- Total current assets: Total current assets, Current assets
- Total assets: Total assets
- Accounts payable: Accounts payable, Trade payables
- Total current liabilities: Total current liabilities, Current liabilities
- Total liabilities: Total liabilities
- Common equity: Common equity, Common stockholders' equity, Common stock, Shareholders' equity
- Retained earnings: Retained earnings, Accumulated deficit
- Total equity: Total equity, Total stockholders' equity, Total shareholders' equity
- Total liabilities and equity: Total liabilities and equity, Total liabilities and shareholders' equity"""

    return get_llm_insights_generic(line_items, "a balance sheet", json_structure, guidance)


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

    # Find key totals using standardized line_category field
    current_assets = None
    total_assets = None
    current_liabilities = None
    total_liabilities = None
    total_equity = None
    total_liabilities_equity = None

    for item in line_items:
        category = item.get("line_category", "").strip()
        value = item.get("line_value")

        # Use exact category matching - much more robust than parsing line names
        if category == "Total Current Assets":
            current_assets = value
        elif category == "Total Assets":
            total_assets = value
        elif category == "Total Current Liabilities":
            current_liabilities = value
        elif category == "Total Liabilities":
            total_liabilities = value
        elif category == "Total Equity":
            total_equity = value
        elif category == "Total Liabilities and Equity":
            total_liabilities_equity = value

    # Calculate sums from line items
    # Only sum base line items, exclude any totals or subtotals
    # Exclude items that are totals themselves (by name or category)
    def is_total_item(item):
        return _is_total_or_subtotal_item(item)

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
        "Assets Held for Sale": "Non-Operating",
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
        "Liabilities Held for Sale": "Non-Operating",
        "Other current liabilities": "Non-Operating",
        "Long-term debt": "Non-Operating",
        "Non-current lease liabilities": "Non-Operating",
        "Deferred tax liabilities": "Operating",
        "Pension liabilities / Postretirement obligations": "Operating",
        "Other long-term liabilities": "Non-Operating",
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
- If no match: use best judgement.

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

    def _classify_with_lookup(name: str) -> bool:
        """Helper to classify using the authoritative lookup."""
        normalized = normalize_line_name(name)
        if normalized in normalized_lookup:
            return normalized_lookup[normalized] == "Operating"
        return True  # Default for lookup failure (if LLM also fails)

    try:
        # Use temperature 0.0 for extraction to prevent hallucination
        classifications = call_llm_and_parse_json(prompt, temperature=0.0)
        classification_map = {item["line_name"]: item["is_operating"] for item in classifications}

        for item in line_items:
            line_name = item["line_name"]
            normalized_name = normalize_line_name(line_name)

            # Check authoritative lookup first
            if normalized_name in normalized_lookup:
                item["is_operating"] = normalized_lookup[normalized_name] == "Operating"
            elif line_name in classification_map:
                item["is_operating"] = classification_map[line_name]
            else:
                item["is_operating"] = True  # Default fallback

        for item in line_items:
            if _is_total_or_subtotal_item(item):
                item["is_operating"] = None
        return line_items

    except Exception as e:
        print(f"Error classifying line items: {str(e)}")
        for item in line_items:
            item["is_operating"] = _classify_with_lookup(item["line_name"])
            if _is_total_or_subtotal_item(item):
                item["is_operating"] = None
        return line_items


def check_line_item_time_periods_balance_sheet(
    line_items: list[dict], expected_time_period: str
) -> dict:
    """
    Use LLM to check if each line item belongs to the expected time period.
    Returns items that don't match the expected period.

    Args:
        line_items: List of line items to check
        expected_time_period: Expected time period (e.g., "Q3 2024")

    Returns:
        Dictionary with mismatched items and their detected periods
    """
    items_json = json.dumps(line_items, indent=2)

    prompt = f"""Analyze the following balance sheet line items and determine if each one belongs to the time period: {expected_time_period}

Line items:
{items_json}

For each line item, check:
1. Does the line_name or any associated context suggest a different time period?
2. Are there any year/quarter/month indicators that don't match {expected_time_period}?
3. Is it clearly from a different column (e.g., "Prior Year", "Dec 31, 2022" when we want "2023")?

Return a JSON object with:
{{
    "mismatched_items": [
        {{
            "line_name": "name of item that doesn't match",
            "detected_period": "the period this item appears to belong to",
            "reason": "why it doesn't match"
        }}
    ]
}}

If all items match the expected period, return an empty mismatched_items array.
Return only valid JSON, no additional text."""

    try:
        result = call_llm_with_retry(prompt, max_retries=2, temperature=0.0)
        return result
    except Exception as e:
        print(f"Error checking time periods: {str(e)}")
        return {"mismatched_items": []}

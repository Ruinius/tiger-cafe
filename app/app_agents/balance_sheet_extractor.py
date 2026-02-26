"""
Balance sheet extraction agent using Gemini LLM and embeddings
"""

import json

from app.app_agents.extractor_utils import (
    call_llm_and_parse_json,
    call_llm_with_retry,
    check_section_completeness_llm,
    format_period_prompt_label,
)
from app.services.tiger_transformer_client import TigerTransformerClient
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)


def extract_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
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
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Dictionary with balance sheet data and validation status
    """
    # Stage 1: Find correct section (iterate through top dense chunks)
    balance_sheet_text = None
    log_info = None
    successful_chunk_index = None

    # Get top numeric chunks
    from app.utils.document_section_finder import (
        find_top_numeric_chunks,
        get_chunk_with_context,
        rank_chunks_by_query,
    )

    # Step 1: Find top-10 chunks by number density
    top_numeric_chunks = find_top_numeric_chunks(
        document_id, file_path, top_k=10, context_name="Balance Sheet"
    )

    # Step 2: Rank those top-10 chunks by query similarity
    query_texts = [
        "Cash",
        "Receivable",
        "Inventory",
        "Other Assets",
        "Property",
        "Goodwill",
        "Intangible",
        "Other Liabilities",
        "Payable",
        "Debt",
    ]
    candidate_chunks = rank_chunks_by_query(
        document_id, file_path, top_numeric_chunks, query_texts, context_name="Balance Sheet"
    )

    if not candidate_chunks:
        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            "I couldn't find any sections with clear financial figures. This is unusual, but I'll keep trying.",
        )
        # Legacy fallback logic could go here or just raise error

    for attempt_idx, chunk_index in enumerate(candidate_chunks):
        try:
            section_msg = f"I'm looking for the balance sheet section (attempt {attempt_idx + 1})."
            add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, section_msg)

            # Get text for this chunk with padding
            # Default padding of 2500 characters before/after
            balance_sheet_text, start_char, log_info = get_chunk_with_context(
                document_id, file_path, chunk_index, chars_before=2500, chars_after=2500
            )

            f"Checking chunk {chunk_index} (chars {log_info['chunk_start_char']}-{log_info['chunk_end_char']})"
            f"Extracted section (chars {log_info['start_extract_char']}-{log_info['end_extract_char']})"

            # Stage 1 validation: Check completeness of chunk text using LLM (before extraction)

            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                f"I'm asking Gemini to check if this section (chunk {chunk_index}) has a complete balance sheet for {time_period}.",
            )
            is_complete, reason = check_balance_sheet_completeness_llm(
                balance_sheet_text, time_period, period_end_date
            )
            if is_complete:
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    f"Gemini response: Section (chunk {chunk_index}) confirmed as a complete consolidated balance sheet. All required attributes (currency, units, totals) are present.",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    f"Gemini response: Section rejected. Incomplete data or header mismatch. Reason: {reason}.",
                    source="gemini",
                )

            if not is_complete:
                section_failed_msg = f"Stage 1 validation failed: {reason}"
                print(section_failed_msg)
                if attempt_idx < len(candidate_chunks) - 1:
                    continue  # Try next candidate
                else:
                    # All attempts failed
                    extracted_data = {
                        "line_items": [],
                        "currency": None,
                        "unit": None,
                        "is_valid": False,
                        "validation_errors": [
                            "Balance sheet completeness check failed on all candidates"
                        ],
                        "time_period": time_period,
                    }
                    return extracted_data

            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "I'm now asking Gemini to extract all the detailed line items from this section.",
            )
            extracted_data = extract_balance_sheet_llm(
                balance_sheet_text, time_period, currency=None, period_end_date=period_end_date
            )
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                f"Gemini response: Successfully extracted {len(extracted_data.get('line_items', []))} line items from the PDF table. Primary currency: {extracted_data.get('currency', 'Unknown')}, Unit scale: {extracted_data.get('unit', 'ones')}.",
                source="gemini",
            )

            # Ensure line_items exists and is a list
            if "line_items" not in extracted_data:
                extracted_data["line_items"] = []
            elif not isinstance(extracted_data["line_items"], list):
                extracted_data["line_items"] = []

            # Assign line_order to extracted items
            for i, item in enumerate(extracted_data.get("line_items", [])):
                item["line_order"] = i

            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "The section looks complete. I'm moving forward with this data.",
            )
            # Store successful chunk index for income statement extraction
            successful_chunk_index = chunk_index
            break  # Section found and validated, proceed to Stage 2

        except Exception as e:
            str(e).lower()
            if attempt_idx == len(candidate_chunks) - 1:
                raise

    # Stage 2: Validate extraction calculations (retry extraction with LLM feedback)
    # extracted_data was already set in Stage 1 and validated for completeness
    calc_errors = []  # Will be set by validation

    # Store successful chunk index in extracted_data for income statement extraction and persistence
    if successful_chunk_index is not None:
        extracted_data["balance_sheet_chunk_index"] = successful_chunk_index
        extracted_data["chunk_index"] = successful_chunk_index  # Also store for persistence

    try:
        # Step 0: Initial Validation
        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            "I'm now double-checking the math to make sure everything adds up correctly.",
        )

        # Post-process to add standard names
        # Inject document_id into items for logging if not present
        for item in extracted_data["line_items"]:
            item["document_id"] = document_id

        extracted_data["line_items"] = post_process_balance_sheet_line_items(
            extracted_data["line_items"], document_id
        )

        # Fix accumulated depreciation sign before validation
        extracted_data["line_items"] = fix_accumulated_depreciation_sign(
            extracted_data["line_items"]
        )

        calc_valid, calc_errors = validate_balance_sheet_calculations(extracted_data["line_items"])

        # Step 1: If validation fails, check time periods and remove out-of-place items
        if not calc_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "The subtotals don't quite match. I'm checking if some items belong to a different time period.",
            )

            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "I'm asking Gemini to check if any of these balance sheet items belong to a different time period.",
            )
            time_check_result = check_line_item_time_periods_balance_sheet(
                extracted_data["line_items"], time_period
            )
            mismatched_items = time_check_result.get("mismatched_items", [])
            if mismatched_items:
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    f"Gemini response: Audit complete. Identified {len(mismatched_items)} items belonging to prior or subsequent periods that will be excluded.",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    "Gemini response: No period mismatches detected. All items belong to the current reporting interval.",
                    source="gemini",
                )

            if mismatched_items:
                # Remove out-of-place items
                mismatched_names = {item["line_name"] for item in mismatched_items}
                len(extracted_data["line_items"])
                extracted_data["line_items"] = [
                    item
                    for item in extracted_data["line_items"]
                    if item["line_name"] not in mismatched_names
                ]

                add_log(
                    document_id,
                    FinancialStatementMilestone.BALANCE_SHEET,
                    f"I've removed {len(mismatched_items)} items that seemed out of place. Re-calculating now.",
                )

                # Re-assign line_order after removal
                for i, item in enumerate(extracted_data["line_items"]):
                    item["line_order"] = i

                # Post-process and Re-validate after removal
                # Inject document_id
                for item in extracted_data["line_items"]:
                    item["document_id"] = document_id

                extracted_data["line_items"] = post_process_balance_sheet_line_items(
                    extracted_data["line_items"], document_id
                )

                # Fix accumulated depreciation sign before validation
                extracted_data["line_items"] = fix_accumulated_depreciation_sign(
                    extracted_data["line_items"]
                )

                calc_valid, calc_errors = validate_balance_sheet_calculations(
                    extracted_data["line_items"]
                )

        # Step 2: If validation still fails, try one last retry with feedback
        if not calc_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "The numbers are still inconsistent. I'm asking for a more precise extraction with specific feedback.",
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
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                f"Gemini response: Corrected extraction complete. Re-extracted {len(extracted_data.get('line_items', []))} items with specific focus on fixing the reported subtotal imbalances.",
                source="gemini",
            )

            # Log completion of retry

            # Assign line_order to retried items
            for i, item in enumerate(extracted_data.get("line_items", [])):
                item["line_order"] = i

            # Post-process and Re-validate final attempt
            # Inject document_id
            for item in extracted_data["line_items"]:
                item["document_id"] = document_id

            extracted_data["line_items"] = post_process_balance_sheet_line_items(
                extracted_data["line_items"], document_id
            )

            # Fix accumulated depreciation sign before validation
            extracted_data["line_items"] = fix_accumulated_depreciation_sign(
                extracted_data["line_items"]
            )

            calc_valid, calc_errors = validate_balance_sheet_calculations(
                extracted_data["line_items"]
            )

        # Final Result Processing
        if calc_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "Great! All the numbers in the balance sheet are now verified and consistent.",
            )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                "I couldn't get all the numbers to balance perfectly, but I've captured the best available data.",
            )

        extracted_data["is_valid"] = calc_valid
        extracted_data["validation_errors"] = calc_errors

        # Classification is now handled by TigerTransformerClient in post_process_balance_sheet_line_items

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
        extracted_data["is_valid"] = False
        extracted_data["validation_errors"] = [str(e)]
        if successful_chunk_index is not None:
            extracted_data["chunk_index"] = successful_chunk_index
        return extracted_data


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
    validation_criteria = """
    - The title of the balance sheet needs to be visible
    - The table must have time header at the top signifying the date, quarter, or fiscal year
    - The statement itself starts with asset header or cash
    - Have multiple asset lines with a total
    - Have multiple liability lines with a total
    - Have a "Total Liabilities and Equity line
    """

    # For balance sheets, Q4 and FY (Full Year) are equivalent for the same year.
    # We update the time_period for the LLM check to be more flexible.
    if "Q4" in time_period:
        year = time_period.split()[-1]
        time_period_query = f"{time_period} or FY {year}"
        validation_criteria += f"\n    - Note: For Q4 reporting, the balance sheet may be labeled as 'FY' (Full Year) or for the year ended {year}. This is acceptable."
    else:
        time_period_query = time_period

    return check_section_completeness_llm(
        text, time_period_query, "consolidated balance sheet", validation_criteria, period_end_date
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
    period_info = format_period_prompt_label(time_period, period_end_date)

    prompt = f"""Extract the balance sheet from the following document text for the {period_info}.
Extract the balance sheet exactly line by line, including all line items and their values.
If the company is foreign, extract the values in the local currency (RMB, EUR, CAD, JPY).

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
    "currency": currency code (USD RMB EUR CAD or JPY),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract ONLY if explicitly stated like "in millions", "in thousands", etc., otherwise null),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but shortened. Do not include long notes. Do not include texts after net of...",
            "line_value": numeric value (as number, not string) - MUST match exactly what is shown in the document,
            "line_category": one of [
                "current_assets",
                "noncurrent_assets",
                "current_liabilities",
                "noncurrent_liabilities",
                "stockholders_equity"
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

    period_info = format_period_prompt_label(time_period, period_end_date)

    prompt = f"""Extract the balance sheet from the following document text for the {period_info}.
Extract the balance sheet exactly line by line, including all line items and their values.
If the company is foreign, extract the values in the local currency (RMB, EUR, CAD, JPY).

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
    "currency": currency code (USD RMB EUR CAD or JPY),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but shortened. Do not include long notes. Do not include texts after net of...",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["current_assets", "noncurrent_assets", "current_liabilities", "noncurrent_liabilities", "stockholders_equity"]
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


def post_process_balance_sheet_line_items(line_items: list[dict], document_id: str) -> list[dict]:
    """
    Post-process balance sheet line items using tiger-transformer:
    1. Validate and fix section tokens (fallback logic)
    2. Call TigerTransformerClient for standardization
    3. Populate standardized_name, is_calculated, is_operating from transformer + CSV lookup

    Returns:
        Processed line items with standardized metadata
    """
    if not line_items:
        return line_items

    # Valid section tokens
    VALID_TOKENS = {
        "current_assets",
        "noncurrent_assets",
        "current_liabilities",
        "noncurrent_liabilities",
        "stockholders_equity",
    }

    # Step 1: Section Tag Fallback - Validate and fix invalid tokens
    for i, item in enumerate(line_items):
        category = item.get("line_category", "").strip()

        # If token is missing or invalid, infer from neighbors
        if not category or category not in VALID_TOKENS:
            # Try to infer from previous item
            if i > 0:
                prev_category = line_items[i - 1].get("line_category", "").strip()
                if prev_category in VALID_TOKENS:
                    item["line_category"] = prev_category
                    continue

            # Try to infer from next item
            if i < len(line_items) - 1:
                next_category = line_items[i + 1].get("line_category", "").strip()
                if next_category in VALID_TOKENS:
                    item["line_category"] = next_category
                    continue

            # Default fallback based on line name heuristics
            line_name_lower = item.get("line_name", "").lower()
            if "asset" in line_name_lower:
                if "current" in line_name_lower or i < len(line_items) // 2:
                    item["line_category"] = "current_assets"
                else:
                    item["line_category"] = "noncurrent_assets"
            elif "liability" in line_name_lower or "liabilities" in line_name_lower:
                if "current" in line_name_lower:
                    item["line_category"] = "current_liabilities"
                else:
                    item["line_category"] = "noncurrent_liabilities"
            elif "equity" in line_name_lower or "stockholder" in line_name_lower:
                item["line_category"] = "stockholders_equity"
            else:
                # Last resort: use previous valid category or default to current_assets
                item["line_category"] = (
                    line_items[i - 1].get("line_category", "current_assets")
                    if i > 0
                    else "current_assets"
                )

    # Step 2: Call TigerTransformerClient for inference
    add_log(
        document_id,
        FinancialStatementMilestone.BALANCE_SHEET,
        "I'm sending the line items to the tiger-transformer model to standardize the names and categories.",
    )
    client = TigerTransformerClient()
    processed_items = client.predict_balance_sheet(line_items)
    add_log(
        document_id,
        FinancialStatementMilestone.BALANCE_SHEET,
        f"Tiger Transformer response: Classification complete. Standardized {len(processed_items)} line items and mapped them to the unified operating taxonomy.",
        source="tiger-transformer",
    )

    return processed_items


def fix_accumulated_depreciation_sign(line_items: list[dict]) -> list[dict]:
    """
    Ensure accumulated depreciation is always negative.

    Args:
        line_items: List of balance sheet line items

    Returns:
        Modified line items with corrected accumulated depreciation sign
    """
    for item in line_items:
        if item.get("standardized_name") == "accumulated_depreciation":
            value = item.get("line_value")
            if value is not None and value > 0:
                item["line_value"] = -value

    return line_items


def validate_balance_sheet_calculations(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate balance sheet calculations (Stage 2): Check that sums match reported totals.
    Uses standardized_name and is_calculated flags from tiger-transformer.

    Args:
        line_items: List of balance sheet line items with standardized_name and is_calculated

    Returns:
        Tuple of (is_valid, list_of_errors_with_differences)
    """
    errors = []

    # Find key totals using standardized_name
    totals = {}
    for item in line_items:
        std_name = item.get("standardized_name")
        value = item.get("line_value")
        if std_name and value is not None:
            totals[std_name] = value

    # Calculate sums from base line items (where is_calculated=False)
    # Group by section
    current_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category") == "current_assets"
            and item.get("is_calculated") is False
            and item.get("line_value") is not None
        )
    )

    noncurrent_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category") == "noncurrent_assets"
            and item.get("is_calculated") is False
            and item.get("line_value") is not None
        )
    )

    current_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category") == "current_liabilities"
            and item.get("is_calculated") is False
            and item.get("line_value") is not None
        )
    )

    noncurrent_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category") == "noncurrent_liabilities"
            and item.get("is_calculated") is False
            and item.get("line_value") is not None
        )
    )

    # Validate total current assets
    if "total_current_assets" in totals:
        reported = totals["total_current_assets"]
        diff = abs(reported - current_assets_sum)
        if diff > 0.01:
            errors.append(
                f"Total current assets mismatch: reported={reported}, calculated={current_assets_sum}"
            )

    # Validate total assets
    if "total_assets" in totals:
        reported = totals["total_assets"]
        calculated = current_assets_sum + noncurrent_assets_sum
        diff = abs(reported - calculated)
        if diff > 0.01:
            errors.append(f"Total assets mismatch: reported={reported}, calculated={calculated}")

    # Validate total current liabilities
    if "total_current_liabilities" in totals:
        reported = totals["total_current_liabilities"]
        diff = abs(reported - current_liabilities_sum)
        if diff > 0.01:
            errors.append(
                f"Total current liabilities mismatch: reported={reported}, calculated={current_liabilities_sum}"
            )

    # Validate total liabilities
    if "total_liabilities" in totals:
        reported = totals["total_liabilities"]
        calculated = current_liabilities_sum + noncurrent_liabilities_sum
        diff = abs(reported - calculated)
        if diff > 0.01:
            errors.append(
                f"Total liabilities mismatch: reported={reported}, calculated={calculated}"
            )

    # Validate balance sheet equation: Total Assets = Total Liabilities + Total Equity
    if "total_assets" in totals and "total_liabilities_and_equity" in totals:
        total_assets = totals["total_assets"]
        total_liab_equity = totals["total_liabilities_and_equity"]
        diff = abs(total_assets - total_liab_equity)
        if diff > 0.01:
            errors.append(
                f"Balance sheet equation mismatch: total_assets={total_assets}, total_liabilities_and_equity={total_liab_equity}"
            )

    # Check if we have at least one key total
    if not any(key in totals for key in ["total_assets", "total_liabilities", "total_equity"]):
        errors.append(
            "Balance sheet is missing key totals (total_assets, total_liabilities, or total_equity)"
        )

    return len(errors) == 0, errors


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

    if "Q4" in expected_time_period:
        year = expected_time_period.split()[-1]
        time_period_query = f"{expected_time_period} (or FY {year})"
        q4_note = f"\n- Note: For balance sheets, {expected_time_period} and FY {year} are equivalent. Accept items from either label."
    else:
        time_period_query = expected_time_period
        q4_note = ""

    prompt = f"""Analyze the following balance sheet line items and determine if each one belongs to the time period: {time_period_query}
{q4_note}

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

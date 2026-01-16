"""
Income statement extraction agent using Gemini LLM and embeddings
"""

import json

from agents.extractor_utils import (
    call_llm_and_parse_json,
    call_llm_with_retry,
    check_section_completeness_llm,
)
from app.services.tiger_transformer_client import TigerTransformerClient
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)


def _normalize_value(value: object) -> float | None:
    """
    Normalize a value to a float, handling various formats.

    Args:
        value: Value to normalize (can be int, float, string, or None)

    Returns:
        Normalized float value or None if invalid
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if not stripped:
            return None
        is_negative = stripped.startswith("(") and stripped.endswith(")")
        if is_negative:
            stripped = stripped[1:-1]
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return -parsed if is_negative else parsed
    return None


def extract_income_statement(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 4,
    document_type: str | None = None,
    balance_sheet_chunk_index: int | None = None,
    period_end_date: str | None = None,
) -> dict:
    """
    Main function to extract income statement with two-stage validation and retries.

    Stage 1: Find correct section (retry with chunk before, after, 2 after balance sheet)
    Stage 2: Post-process and validate extraction (retry extraction with LLM feedback)

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts for section finding (4 total: same, before, after, 2 after)
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Dictionary with income statement data and validation status
    """
    # Stage 1: Find correct section (iterate through top dense chunks)
    income_statement_text = None
    start_page = None
    log_info = None
    extracted_data = None
    successful_chunk_index = None

    # Get top numeric chunks
    from app.utils.document_section_finder import find_top_numeric_chunks, get_chunk_with_context

    candidate_chunks = find_top_numeric_chunks(document_id, file_path, top_k=5)

    if not candidate_chunks:
        print("No chunks found with numbers, falling back to legacy search")

    for attempt_idx, chunk_index in enumerate(candidate_chunks):
        try:
            section_msg = f"Stage 1: Finding income statement section (attempt {attempt_idx + 1}, chunk {chunk_index})"
            print(section_msg)
            add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, section_msg)

            # Get text for this chunk with padding
            # Default padding of 1 page before/after
            income_statement_text, start_page, log_info = get_chunk_with_context(
                document_id, file_path, chunk_index, pages_before=1, pages_after=1
            )

            chunk_msg = f"Checking chunk {chunk_index} (pages {log_info['chunk_start_page']}-{log_info['chunk_end_page']})"
            print(chunk_msg)
            add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, chunk_msg)

            # Stage 1 validation: Check completeness of chunk text using LLM (before extraction)
            completeness_check_msg = (
                "Stage 1: Checking if chunk contains complete income statement using LLM"
            )
            print(completeness_check_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                completeness_check_msg,
            )

            is_complete, reason = check_income_statement_completeness_llm(
                income_statement_text, time_period, period_end_date
            )

            if not is_complete:
                section_failed_msg = f"Stage 1 validation failed: {reason}"
                print(section_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    section_failed_msg,
                )
                if attempt_idx < len(candidate_chunks) - 1:
                    continue  # Try next candidate
                else:
                    # All attempts failed
                    # We will raise Exception at end of loop if not found
                    pass
            else:
                # Extract income statement using LLM (only if chunk is complete)
                extraction_msg = "Extracting income statement from complete chunk"
                print(extraction_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    extraction_msg,
                )

                extracted_data = extract_income_statement_llm(
                    income_statement_text,
                    time_period,
                    currency=None,
                    period_end_date=period_end_date,
                )

                # Classification is now handled by TigerTransformerClient in post_process_income_statement_line_items

                extracted_count_msg = (
                    f"Extracted {len(extracted_data.get('line_items', []))} line items"
                )
                print(extracted_count_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    extracted_count_msg,
                )

                section_valid_msg = "Stage 1 validation passed (complete income statement chunk found and extracted)"
                print(section_valid_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    section_valid_msg,
                )
                # Store successful chunk index
                successful_chunk_index = chunk_index
                extracted_data["chunk_index"] = chunk_index
                break  # Section found and validated, proceed to Stage 2

        except Exception as e:
            str(e).lower()
            print(f"Error on section attempt {attempt_idx + 1}: {str(e)}")
            if attempt_idx == len(candidate_chunks) - 1:
                # Last attempt failed
                pass

    # If loop finished without success (extracted_data is None), raise exception
    if not extracted_data:
        raise Exception("Failed to find or extract income statement after all attempts")

    # Stage 2: Post-process and validate extraction
    try:
        # Step 0: Initial Post-processing & Validation
        extraction_msg = "Stage 2: Post-processing and validating extraction"
        print(extraction_msg)
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            extraction_msg,
        )

        processed_line_items, normalization_errors = post_process_income_statement_line_items(
            extracted_data.get("line_items", [])
        )
        extracted_data["line_items"] = processed_line_items

        is_valid = len(normalization_errors) == 0

        # Step 1: If validation fails, check time periods and remove out-of-place items
        if not is_valid:
            validation_error_str = "; ".join(normalization_errors)
            time_check_msg = f"Validation failed ({validation_error_str}). Checking for out-of-period line items."
            print(time_check_msg)
            add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, time_check_msg)

            time_check_result = check_line_item_time_periods_income_statement(
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
                add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, removed_msg)

                # Re-validate after removal
                processed_line_items, normalization_errors = (
                    post_process_income_statement_line_items(extracted_data.get("line_items", []))
                )
                extracted_data["line_items"] = processed_line_items
                is_valid = len(normalization_errors) == 0

        # Step 2: If validation still fails, try one last retry with feedback
        if not is_valid:
            retry_msg = "Validation still failed. Attempting final extraction with LLM feedback."
            print(retry_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                retry_msg,
            )

            # Re-extract with validation error feedback
            extracted_data = extract_income_statement_llm_with_feedback(
                income_statement_text,
                time_period,
                extracted_data,  # Previous extraction
                normalization_errors,
                currency=None,
                period_end_date=period_end_date,
            )

            # Classification is now handled by TigerTransformerClient in post_process_income_statement_line_items

            # Post-process final attempt
            processed_line_items, normalization_errors = post_process_income_statement_line_items(
                extracted_data.get("line_items", [])
            )
            extracted_data["line_items"] = processed_line_items
            is_valid = len(normalization_errors) == 0

        # Final Result Processing
        if is_valid:
            success_msg = "Stage 2 validation passed"
            if normalization_errors:
                success_msg += " (deduced valid despite warnings)"
            print(success_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                success_msg,
            )
        else:
            fail_msg = (
                f"Stage 2 validation failed after retries: {', '.join(normalization_errors[:2])}"
            )
            print(fail_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                fail_msg,
            )

        extracted_data["is_valid"] = is_valid
        extracted_data["validation_errors"] = normalization_errors

        # Classification moved to earlier steps

        # Calculate revenue growth YoY
        current_revenue = None
        for item in extracted_data.get("line_items", []):
            item_name_lower = item.get("line_name", "").lower()
            if "total net revenue" in item_name_lower:
                current_revenue = _normalize_value(item.get("line_value"))
                if current_revenue is not None:
                    break

        if current_revenue is not None and extracted_data.get("revenue_prior_year") is not None:
            prior_revenue = extracted_data["revenue_prior_year"]
            if prior_revenue > 0:
                revenue_growth = ((current_revenue - prior_revenue) / prior_revenue) * 100
                extracted_data["revenue_growth_yoy"] = revenue_growth

        # Store chunk index for persistence
        if successful_chunk_index is not None:
            extracted_data["chunk_index"] = successful_chunk_index

        return extracted_data

    except Exception as e:
        print(f"Error in Stage 2 extraction: {str(e)}")
        extracted_data["is_valid"] = False
        extracted_data["validation_errors"] = [str(e)]
        return extracted_data


def find_income_statement_near_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: str | None = None,
    attempt: int = 0,
    balance_sheet_chunk_index: int | None = None,
) -> tuple[str | None, int | None, dict | None]:
    """
    Find income statement section by locating balance sheet first, then using adjacent chunks.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")
        attempt: 0 = same chunk as balance sheet, 1 = chunk before, 2 = chunk after, 3 = 2 chunks after
        balance_sheet_chunk_index: Optional balance sheet chunk index to use directly (if known from successful extraction)

    Returns:
        Tuple of (extracted_text, start_page, log_info) or (None, None, None) if not found
    """
    try:
        import pdfplumber

        from agents.balance_sheet_extractor import find_balance_sheet_section
        from app.utils.document_indexer import get_chunk_metadata, get_chunk_text

        # Get chunk metadata (needed for all paths)
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            print("Could not get chunk metadata")
            return None, None, None
        chunk_size = chunk_metadata.get("chunk_size", 2)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        # If balance_sheet_chunk_index is provided, use it directly (from successful balance sheet extraction)
        # Otherwise, find the balance sheet location by searching (will use rank 0 chunk)
        if balance_sheet_chunk_index is not None:
            # Use the provided chunk index (from successful balance sheet extraction)
            balance_chunk_index = balance_sheet_chunk_index
            if balance_chunk_index < 0 or balance_chunk_index >= num_chunks:
                print(
                    f"Balance sheet chunk index {balance_chunk_index} is out of bounds (0-{num_chunks - 1})"
                )
                return None, None, None
            # Get chunk text to determine page range
            balance_chunk_text, balance_chunk_start_page, balance_chunk_end_page = get_chunk_text(
                file_path, balance_chunk_index, chunk_size
            )
            balance_log_info = {
                "best_chunk_index": balance_chunk_index,
                "chunk_start_page": balance_chunk_start_page,
                "chunk_end_page": balance_chunk_end_page - 1,
            }
        else:
            # Fallback: find balance sheet location (uses rank 0 chunk)
            balance_sheet_text, balance_start_page, balance_log_info = find_balance_sheet_section(
                document_id, file_path, time_period, document_type, chunk_rank=0
            )

            if not balance_log_info or "best_chunk_index" not in balance_log_info:
                print("Could not find balance sheet location")
                return None, None, None

            balance_chunk_index = balance_log_info["best_chunk_index"]

        chunk_size = chunk_metadata.get("chunk_size", 2)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        # Determine which chunk to use based on attempt
        # attempt 0 = same chunk as balance sheet
        # attempt 1 = chunk before balance sheet
        # attempt 2 = chunk after balance sheet
        # attempt 3 = full document search for best chunk (excluding 0, 1, 2)
        if attempt == 0:
            target_chunk_index = balance_chunk_index
            direction = "same as"
        elif attempt == 1:
            target_chunk_index = balance_chunk_index - 1
            direction = "before"
        elif attempt == 2:
            target_chunk_index = balance_chunk_index + 1
            direction = "after"

            # Validate chunk index for attempts 0, 1, 2 (before continuing)
            if target_chunk_index < 0 or target_chunk_index >= num_chunks:
                print(
                    f"Target chunk index {target_chunk_index} is out of bounds (0-{num_chunks - 1}), skipping to next attempt"
                )
                return None, None, None
        elif attempt == 3:
            # Full document search using income statement queries
            from app.utils.document_section_finder import find_document_section

            # Income statement specific queries
            query_texts = ["net income", "revenue", "sales", "interest", "tax", "cost", "expenses"]

            # Exclude chunks already tried
            exclude_chunks = {
                balance_chunk_index,  # attempt 0
                balance_chunk_index - 1,  # attempt 1
                balance_chunk_index + 1,  # attempt 2
            }

            # Search full document (no ignore fractions), excluding already-tried chunks
            income_text, income_start_page, income_log_info = find_document_section(
                document_id=document_id,
                file_path=file_path,
                query_texts=query_texts,
                chunk_size=chunk_size,
                score_threshold=0.3,
                pages_before=1,
                pages_after=1,
                rerank_top_k=0,  # No reranking needed
                ignore_front_fraction=0.0,
                ignore_back_fraction=0.0,
                chunk_rank=0,  # Get best match
                min_numbers=15,
                exclude_chunks=exclude_chunks,
            )

            if not income_log_info or "best_chunk_index" not in income_log_info:
                msg = "Full document search failed to find income statement (excluding already-tried chunks)"
                print(msg)
                add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, msg)
                return None, None, None

            target_chunk_index = income_log_info["best_chunk_index"]
            direction = f"full search (chunk {target_chunk_index}, excluding chunks {sorted(exclude_chunks)})"

            # Use the text from find_document_section directly
            log_info = {
                "balance_sheet_chunk_index": balance_chunk_index,
                "income_statement_chunk_index": target_chunk_index,
                "direction": direction,
                "chunk_start_page": income_log_info.get("chunk_start_page"),
                "chunk_end_page": income_log_info.get("chunk_end_page"),
                "start_extract_page": income_log_info.get("start_extract_page"),
                "end_extract_page": income_log_info.get("end_extract_page"),
            }

            print(
                f"Income statement found via {direction}: chunk {target_chunk_index} "
                f"(pages {income_log_info.get('chunk_start_page')}-{income_log_info.get('chunk_end_page')}), "
                f"extracting pages {income_log_info.get('start_extract_page')}-{income_log_info.get('end_extract_page')}"
            )

            return income_text, income_start_page, log_info
        else:
            print(f"Invalid attempt number: {attempt}, must be 0, 1, 2, or 3")
            return None, None, None

        # Validate chunk index (for attempts 0, 1 only - attempt 2 validated above)
        if attempt in [0, 1] and (target_chunk_index < 0 or target_chunk_index >= num_chunks):
            print(f"Target chunk index {target_chunk_index} is out of bounds (0-{num_chunks - 1})")
            return None, None, None

        # Get chunk text (for attempts 0, 1, 2)
        chunk_text, chunk_start_page, chunk_end_page = get_chunk_text(
            file_path, target_chunk_index, chunk_size
        )

        # Apply "critical mass of numbers" filter
        from app.utils.document_section_finder import _count_numbers

        if chunk_text and _count_numbers(chunk_text) < 15:
            print(
                f"Attempt {attempt} (chunk {target_chunk_index}) has insufficient numbers, skipping"
            )
            return None, None, None

        # Extract with pages_before=1 and pages_after=1 (similar to find_document_section)
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

        start_extract_page = max(0, chunk_start_page - 1)
        end_extract_page = min(total_pages, chunk_end_page + 1)

        # Extract text from page range
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            clamped_start = max(0, min(start_extract_page, total_pages))
            clamped_end = max(clamped_start, min(end_extract_page, total_pages))
            for page_index in range(clamped_start, clamped_end):
                page_text = pdf.pages[page_index].extract_text()
                if page_text:
                    text_parts.append(page_text)
        extracted_text = "\n\n".join(text_parts)

        log_info = {
            "balance_sheet_chunk_index": balance_chunk_index,
            "income_statement_chunk_index": target_chunk_index,
            "direction": direction,
            "chunk_start_page": chunk_start_page,
            "chunk_end_page": chunk_end_page - 1,
            "start_extract_page": start_extract_page,
            "end_extract_page": end_extract_page - 1,
        }

        print(
            f"Income statement found {direction} balance sheet: chunk {target_chunk_index} "
            f"(pages {chunk_start_page}-{chunk_end_page - 1}), "
            f"extracting pages {start_extract_page}-{end_extract_page - 1}"
        )

        return extracted_text, start_extract_page, log_info

    except Exception as e:
        print(f"Error finding income statement near balance sheet: {str(e)}")
        import traceback

        traceback.print_exc()
        return None, None, None


def check_income_statement_completeness_llm(
    text: str, time_period: str, period_end_date: str | None = None
) -> tuple[bool, str]:
    """
    Use LLM to check if the chunk text contains a complete consolidated income statement.
    This is called BEFORE extraction to validate we have the right chunk.

    Args:
        text: Text containing income statement section (chunk text)
        time_period: Time period (e.g., "Q3 2023")
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Tuple of (is_complete, reason)
    """
    validation_criteria = """- Start with revenue or sales
- Include cost of revenue, cost of sales, or cost of goods sold
- Include operating expenses (R&D, SG&A, etc.)
- Include tax expense
- End with net income or net earnings"""

    return check_section_completeness_llm(
        text, time_period, "consolidated income statement", validation_criteria, period_end_date
    )


def extract_income_statement_llm(
    text: str, time_period: str, currency: str | None = None, period_end_date: str | None = None
) -> dict:
    """
    Use LLM to extract income statement line items exactly line by line.
    Also extracts revenue for the same period in the prior year.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with income statement data
    """
    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the {period_info}.
Extract the income statement exactly line by line, including all line items and their values starting with revenue.
If the company is foreign, extract the values in the local currency.

Also extract the revenue for the same period in the prior year (for year-over-year growth calculation).

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null or omit that field
- Extract line items ONLY from the income statement table/section in the document text
- DO NOT use any external knowledge or assumptions
- Every line_value must correspond to an actual number shown in the document text
- If currency or unit is not explicitly stated in the document, use null
- For revenue_prior_year, ONLY extract if you can find the same period in the prior year explicitly stated in the document text - do not calculate or infer it

Return a JSON object with the following structure:
{{
    "currency": currency code,
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract ONLY if explicitly stated like "in millions", "in thousands", etc., otherwise null),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "revenue_prior_year": revenue for the same period in the prior year (as number, null if not EXPLICITLY found in document),
    "revenue_prior_year_unit": unit for revenue_prior_year - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as "unit", null if revenue_prior_year is null),
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but shortened. Do not include long notes. Do not include texts after net of...",
            "line_value": numeric value (as number, not string) - MUST match exactly what is shown in the document,
            "line_category": "income_statement"
        }},
        ...
    ]
}}

IMPORTANT:
- Stop after the net income line item is extracted
- Extract values exactly as they appear in the document (no rounding, include negative values if present)
- DO NOT round, estimate, or modify values - use them exactly as written
- Include all line items that appear in the document, including but not limited to: Revenue, Cost of Revenue/Cost of Goods Sold, Gross Profit, Operating Expenses, Operating Income, Net Income, etc.
- DO NOT add line items that are not in the document
- Maintain the exact order of line items as they appear in the document
- Extract the currency code
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue) - ONLY if explicitly shown in the document text, otherwise use null
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
        raise Exception(f"Error extracting income statement: {str(e)}")


def extract_income_statement_llm_with_feedback(
    text: str,
    time_period: str,
    previous_extraction: dict,
    validation_errors: list[str],
    currency: str | None = None,
    period_end_date: str | None = None,
) -> dict:
    """
    Use LLM to extract income statement with validation error feedback for retry.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        previous_extraction: Previous extraction attempt (to show what was extracted)
        validation_errors: List of validation errors with calculated differences
        currency: Currency code if known
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with income statement data
    """
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    previous_items_text = json.dumps(previous_extraction.get("line_items", []), indent=2)

    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the {period_info}.
Extract the income statement exactly line by line, including all line items and their values starting with revenue.
If the company is foreign, extract the values in the local currency.

PREVIOUS EXTRACTION ATTEMPT:
{previous_items_text}

VALIDATION ERRORS (with calculated differences):
{errors_text}

Please review the previous extraction and fix the issues. Pay special attention to:
- Ensuring all line items are extracted correctly
- Checking that line item values match what's in the document
- Verifying that calculations are correct (e.g., Revenue - Costs = Gross Profit, etc.)
- Note: Line items should be normalized so that costs are shown as negative values

Return a JSON object with the following structure:
{{
    "currency": currency code,
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
    "revenue_prior_year": revenue for the same period in the prior year (as number, null if not found),
    "revenue_prior_year_unit": unit for revenue_prior_year - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as "unit", null if revenue_prior_year is null),
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but shortened. Do not include long notes. Do not include texts after net of...",
            "line_value": numeric value (as number, not string),
            "line_category": "income_statement"
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
- When fixing validation errors, ONLY correct values that actually appear in the document text - do not invent new values

IMPORTANT:
- Stop after the net income line item is extracted
- Extract values exactly as they appear in the document (no rounding, include negative values if present)
- DO NOT round, estimate, or modify values - use them exactly as written
- Include all line items that appear in the document, including but not limited to: Revenue, Cost of Revenue/Cost of Goods Sold, Gross Profit, Operating Expenses, Operating Income, Net Income, etc.
- DO NOT add line items that are not in the document
- Maintain the exact order of line items as they appear in the document
- Extract the currency code
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue) - ONLY if explicitly shown in the document text, otherwise use null
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- IMPORTANT: Line items are normalized for costs to show as negative (e.g., Cost of Revenue should be negative). If the document shows costs as positive, you may need to convert them to negative to match the expected format.
- Carefully review the validation errors and fix the issues in your extraction by referencing the actual document text - do not invent values to fix calculation errors

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
        raise Exception(f"Error extracting income statement: {str(e)}")


def post_process_income_statement_line_items(
    line_items: list[dict],
) -> tuple[list[dict], list[str]]:
    """
    Post-process income statement line items using tiger-transformer:
    1. Call TigerTransformerClient for standardization
    2. Normalize signs based on is_expense (flip to negative if needed)
    3. Validate calculations with residual solver for ambiguous items

    Returns:
        Tuple of (processed_line_items, validation_errors)
    """
    if not line_items:
        return line_items, []

    # Step 1: Call TigerTransformerClient for inference and enrichment
    client = TigerTransformerClient()
    processed_items = client.predict_income_statement(line_items)

    # Step 2: Normalize signs based on is_expense
    # Confirmed expenses (is_expense=True) should be negative
    for item in processed_items:
        is_expense = item.get("is_expense")
        line_value = item.get("line_value", 0)

        if is_expense is True and line_value > 0:
            # Flip to negative
            item["line_value"] = -line_value

    # Step 3: Validate calculations using standardized_name and is_calculated
    validation_errors = []

    # Find key totals
    totals = {}
    for item in processed_items:
        std_name = item.get("standardized_name")
        value = item.get("line_value")
        if std_name and value is not None:
            totals[std_name] = value

    # Calculate sums from base items (is_calculated=False)
    def sum_items_with_filter(filter_func):
        return sum(
            item["line_value"]
            for item in processed_items
            if item.get("is_calculated") is False and filter_func(item)
        )

    # Validate Total Revenue - Costs = Income before taxes
    if "total_revenue" in totals and "income_before_taxes" in totals:
        revenue = totals["total_revenue"]
        income_before_taxes = totals["income_before_taxes"]

        # Sum costs between revenue and income before taxes
        costs_sum = sum_items_with_filter(
            lambda item: item.get("standardized_name")
            not in ["total_revenue", "income_before_taxes"]
            and processed_items.index(item)
            > next(
                i
                for i, x in enumerate(processed_items)
                if x.get("standardized_name") == "total_revenue"
            )
            and processed_items.index(item)
            < next(
                i
                for i, x in enumerate(processed_items)
                if x.get("standardized_name") == "income_before_taxes"
            )
        )

        calculated_gp = revenue + costs_sum  # costs are negative
        diff = abs(calculated_gp - income_before_taxes)

        if diff > 0.01:
            # Try residual solver for ambiguous items
            residual = calculated_gp - income_before_taxes
            ambiguous_items = [
                item
                for item in processed_items
                if item.get("is_expense") is None and item.get("is_calculated") is False
            ]

            # Check if flipping one or two ambiguous items resolves the residual
            solved = False
            for item in ambiguous_items:
                if abs(abs(item["line_value"]) * 2 - abs(residual)) < 0.01:
                    # Flipping this item resolves the residual
                    item["line_value"] = -item["line_value"]
                    solved = True
                    break

            if not solved:
                validation_errors.append(
                    f"Income before taxes mismatch: revenue + costs = {calculated_gp:.2f}, but income before taxes = {income_before_taxes:.2f}"
                )

    # Validate Revenue (NOT TOTAL) - Costs = Income before taxes
    if "revenue" in totals and "income_before_taxes" in totals:
        revenue = totals["revenue"]
        income_before_taxes = totals["income_before_taxes"]

        # Sum costs between revenue and income before taxes
        costs_sum = sum_items_with_filter(
            lambda item: item.get("standardized_name") not in ["revenue", "income_before_taxes"]
            and processed_items.index(item)
            > next(
                i for i, x in enumerate(processed_items) if x.get("standardized_name") == "revenue"
            )
            and processed_items.index(item)
            < next(
                i
                for i, x in enumerate(processed_items)
                if x.get("standardized_name") == "income_before_taxes"
            )
        )

        calculated_gp = revenue + costs_sum  # costs are negative
        diff = abs(calculated_gp - income_before_taxes)

        if diff > 0.01:
            # Try residual solver for ambiguous items
            residual = calculated_gp - income_before_taxes
            ambiguous_items = [
                item
                for item in processed_items
                if item.get("is_expense") is None and item.get("is_calculated") is False
            ]

            # Check if flipping one or two ambiguous items resolves the residual
            solved = False
            for item in ambiguous_items:
                if abs(abs(item["line_value"]) * 2 - abs(residual)) < 0.01:
                    # Flipping this item resolves the residual
                    item["line_value"] = -item["line_value"]
                    solved = True
                    break

            if not solved:
                validation_errors.append(
                    f"Income before taxes mismatch: revenue + costs = {calculated_gp:.2f}, but income before taxes = {income_before_taxes:.2f}"
                )

    # Check if we have at least one key total
    if not any(key in totals for key in ["total_revenue", "revenue", "income_before_taxes"]):
        validation_errors.append(
            "Income statement is missing key totals (total_revenue, revenue, or income_before_taxes)"
        )

    return processed_items, validation_errors


def check_line_item_time_periods_income_statement(
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

    prompt = f"""Analyze the following line items and determine if each one belongs to the time period: {expected_time_period}

Line items:
{items_json}

For each line item, check:
1. Does the line_name or any associated context suggest a different time period?
2. Are there any year/quarter/month indicators that don't match {expected_time_period}?

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

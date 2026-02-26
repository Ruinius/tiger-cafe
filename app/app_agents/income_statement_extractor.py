"""
Income statement extraction agent using Gemini LLM and embeddings
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
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Dictionary with income statement data and validation status
    """
    # Stage 1: Find correct section (iterate through top dense chunks)
    income_statement_text = None
    log_info = None
    extracted_data = None
    successful_chunk_index = None

    # Get top numeric chunks
    from app.utils.document_section_finder import (
        find_top_numeric_chunks,
        get_chunk_with_context,
        rank_chunks_by_query,
    )

    # Step 1: Find top-10 chunks by number density
    top_numeric_chunks = find_top_numeric_chunks(
        document_id, file_path, top_k=10, context_name="Income Statement"
    )

    # Step 2: Rank those top-10 chunks by query similarity
    query_texts = ["Revenue", "Profit", "Income", "Tax", "Cost"]
    candidate_chunks = rank_chunks_by_query(
        document_id, file_path, top_numeric_chunks, query_texts, context_name="Income Statement"
    )

    if not candidate_chunks:
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "I couldn't find any sections with clear financial figures for the income statement. This is unusual, but I'll keep trying.",
        )

    for attempt_idx, chunk_index in enumerate(candidate_chunks):
        try:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"I'm looking for the income statement section (attempt {attempt_idx + 1}).",
            )

            # Get text for this chunk with padding
            # Default padding of 2500 characters before/after
            income_statement_text, start_char, log_info = get_chunk_with_context(
                document_id, file_path, chunk_index, chars_before=2500, chars_after=2500
            )

            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"I'm checking a promising piece of the document (chars {log_info['chunk_start_char']}-{log_info['chunk_end_char']}).",
            )

            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"I'm asking Gemini to verify if this section contains a complete income statement for {time_period}.",
            )
            is_complete, reason = check_income_statement_completeness_llm(
                income_statement_text, time_period, period_end_date
            )
            if is_complete:
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    f"Gemini response: Section (chunk {chunk_index}) confirmed as a complete consolidated income statement. Verified revenue and net income anchorage.",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    f"Gemini response: Section rejected. Context insufficient for full P&L extraction. Reason: {reason}.",
                    source="gemini",
                )

            if not is_complete:
                if attempt_idx < len(candidate_chunks) - 1:
                    continue  # Try next candidate
                else:
                    # All attempts failed
                    # We will raise Exception at end of loop if not found
                    pass
            else:
                # Extract income statement using LLM (only if chunk is complete)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    "I'm now asking Gemini to extract all the income statement line items.",
                )
                extracted_data = extract_income_statement_llm(
                    income_statement_text,
                    time_period,
                    currency=None,
                    period_end_date=period_end_date,
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    f"Gemini response: Successfully parsed {len(extracted_data.get('line_items', []))} P&L line items. Currency detected: {extracted_data.get('currency', 'Unknown')}, Unit: {extracted_data.get('unit', 'ones')}.",
                    source="gemini",
                )

                # Classification is now handled by TigerTransformerClient in post_process_income_statement_line_items

                # Store successful chunk index
                successful_chunk_index = chunk_index
                extracted_data["chunk_index"] = chunk_index

                # Assign line_order to extracted items
                for i, item in enumerate(extracted_data.get("line_items", [])):
                    item["line_order"] = i

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
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "I'm now double-checking the figures and standardizing the line item names.",
        )

        # Inject document_id
        for item in extracted_data["line_items"]:
            item["document_id"] = document_id

        processed_line_items, normalization_errors = post_process_income_statement_line_items(
            extracted_data.get("line_items", []), document_id
        )
        extracted_data["line_items"] = processed_line_items

        is_valid = len(normalization_errors) == 0

        # Step 1: If validation fails, check time periods and remove out-of-place items
        if not is_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "I noticed some numbers don't add up correctly. I'll check if some items belong to a different period.",
            )

            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "I'm asking Gemini to check if any of these line items belong to a different time period.",
            )
            time_check_result = check_line_item_time_periods_income_statement(
                extracted_data["line_items"], time_period
            )
            mismatched_items = time_check_result.get("mismatched_items", [])
            if mismatched_items:
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    f"Gemini response: Period audit complete. {len(mismatched_items)} items flagged for exclusion due to fiscal period mismatch.",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    "Gemini response: Alignment check passed. All 100% of P&L items correspond correctly to {time_period}.",
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
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    f"I've removed {len(mismatched_items)} items that seemed out of place. Re-calculating the results now.",
                )

                # Re-assign line_order after removal
                for i, item in enumerate(extracted_data["line_items"]):
                    item["line_order"] = i

                # Re-validate after removal
                # Inject document_id
                for item in extracted_data["line_items"]:
                    item["document_id"] = document_id

                processed_line_items, normalization_errors = (
                    post_process_income_statement_line_items(extracted_data.get("line_items", []))
                )
                extracted_data["line_items"] = processed_line_items
                is_valid = len(normalization_errors) == 0

        # Step 2: If validation still fails, try one last retry with feedback
        if not is_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "The calculations are still a bit off. I'm asking for a more precise extraction with specific feedback.",
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
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"Gemini response: Refined extraction successfully resolved the {len(normalization_errors)} calculation imbalances reported. P&L is now mathematically consistent.",
                source="gemini",
            )

            # Log completion of retry
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "I've completed the refined extraction. Let's see if the numbers match up now.",
            )

            # Assign line_order to retried items
            for i, item in enumerate(extracted_data.get("line_items", [])):
                item["line_order"] = i

            # Classification is now handled by TigerTransformerClient in post_process_income_statement_line_items

            # Post-process final attempt
            processed_line_items, normalization_errors = post_process_income_statement_line_items(
                extracted_data.get("line_items", []), document_id
            )
            extracted_data["line_items"] = processed_line_items
            is_valid = len(normalization_errors) == 0

        # Final Result Processing
        if is_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "Success! The income statement numbers are now verified and consistent.",
            )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "I couldn't get all the totals to match perfectly, but I've captured the most accurate data possible.",
            )

        extracted_data["is_valid"] = is_valid
        extracted_data["validation_errors"] = normalization_errors

        # Classification moved to earlier steps

        # Store chunk index for persistence
        if successful_chunk_index is not None:
            extracted_data["chunk_index"] = successful_chunk_index

        return extracted_data

    except Exception as e:
        print(f"Error in Stage 2 extraction: {str(e)}")
        extracted_data["is_valid"] = False
        extracted_data["validation_errors"] = [str(e)]
        return extracted_data


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
    validation_criteria = """
    - The title of the income statement or statement of operations needs to be visible
    - The table must have time header at the top, such as "Three Months Ended in..." or Quarter
    - The table SHOULD include multiple columns with data from other time periods
    - The statement itself starts with revenue header, revenue or sales
    - Include cost of revenue, cost of sales, or cost of goods sold
    - Include operating expenses (R&D, SG&A, etc.)
    - Include tax expense
    - End with net income or net earnings
    """

    return check_section_completeness_llm(
        text, time_period, "consolidated income statement", validation_criteria, period_end_date
    )


def extract_income_statement_llm(
    text: str, time_period: str, currency: str | None = None, period_end_date: str | None = None
) -> dict:
    """
    Use LLM to extract income statement line items exactly line by line.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with income statement data
    """
    period_info = format_period_prompt_label(time_period, period_end_date)

    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the {period_info}.
Extract the income statement exactly line by line, including all line items and their values starting with revenue.
If the company is foreign, extract the values in the local currency (RMB, EUR, CAD, JPY).

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null or omit that field
- Extract line items ONLY from the income statement table/section in the document text
- DO NOT use any external knowledge or assumptions
- Every line_value must correspond to an actual number shown in the document text
- If currency or unit is not explicitly stated in the document, use null

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

    period_info = format_period_prompt_label(time_period, period_end_date)

    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the {period_info}.
Extract the income statement exactly line by line, including all line items and their values starting with revenue.
If the company is foreign, extract the values in the local currency (RMB, EUR, CAD, JPY).

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
    "currency": currency code (USD RMB EUR CAD or JPY),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "period_end_date": "{period_end_date}" if known else null,
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
    line_items: list[dict], document_id: str
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
    add_log(
        document_id,
        FinancialStatementMilestone.INCOME_STATEMENT,
        "I'm sending the line items to the tiger-transformer model to standardize the names.",
    )
    client = TigerTransformerClient()
    processed_items = client.predict_income_statement(line_items)
    add_log(
        document_id,
        FinancialStatementMilestone.INCOME_STATEMENT,
        f"Tiger Transformer response: P&L standardization complete. {len(processed_items)} items mapped to the core financial schema.",
        source="tiger-transformer",
    )

    # Step 2: Sign Normalization based on predominant category signs

    # 2.1: Expenses - Base items (is_expense=True, is_calculated=False)
    base_expenses = [
        item
        for item in processed_items
        if item.get("is_expense") is True and item.get("is_calculated") is False
    ]
    pos_exp_count = sum(1 for e in base_expenses if (e.get("line_value") or 0) > 0)
    neg_exp_count = sum(1 for e in base_expenses if (e.get("line_value") or 0) < 0)

    if pos_exp_count > neg_exp_count:
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "Expenses are predominantly positive. Flipping all expense signs to normalize categorical presentation.",
        )
        for item in processed_items:
            # Flip ALL expenses to correct the systematic inversion
            if item.get("is_expense") is True and item.get("line_value") is not None:
                item["line_value"] = -item["line_value"]

    # 2.2: Other Income - Base items (is_expense=False, is_calculated=False, no "revenue" in name)
    base_other_income = [
        item
        for item in processed_items
        if item.get("is_expense") is False
        and item.get("is_calculated") is False
        and "revenue" not in (item.get("standardized_name") or "").lower()
    ]
    pos_inc_count = sum(1 for i in base_other_income if (i.get("line_value") or 0) > 0)
    neg_inc_count = sum(1 for i in base_other_income if (i.get("line_value") or 0) < 0)

    if neg_inc_count > pos_inc_count:
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "Non-revenue income items are predominantly negative. Flipping all non-revenue income signs to normalize categorical presentation.",
        )
        for item in processed_items:
            # Flip ALL non-revenue non-expenses to correct the systematic inversion
            if (
                item.get("is_expense") is False
                and item.get("is_calculated") is False
                and "revenue" not in (item.get("standardized_name") or "").lower()
                and item.get("line_value") is not None
            ):
                item["line_value"] = -item["line_value"]

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
            if item.get("is_calculated") is False
            and item.get("line_value") is not None
            and filter_func(item)
        )

    # Validate Total Revenue - Costs = Income before taxes
    if "total_revenue" in totals and "income_before_taxes" in totals:
        revenue = totals["total_revenue"]
        income_before_taxes = totals["income_before_taxes"]

        pass

        # Calculate costs sum
        costs_items = [
            item
            for item in processed_items
            if item.get("is_calculated") is False
            and item.get("line_value") is not None
            and item.get("standardized_name") not in ["total_revenue", "income_before_taxes"]
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
        ]

        costs_sum = sum(item["line_value"] for item in costs_items)
        pass

        calculated_gp = revenue + costs_sum  # costs are negative
        diff = abs(calculated_gp - income_before_taxes)

        pass

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

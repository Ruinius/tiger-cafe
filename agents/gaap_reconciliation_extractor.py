"""
GAAP/EBITDA reconciliation extraction agent for earnings announcements.
Uses chunk-based embedding search to find reconciliation tables, similar to balance sheet finding.
"""

from __future__ import annotations

import json

from agents.extractor_utils import call_llm_with_retry, check_section_completeness_llm
from app.models.document import DocumentType
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import normalize_line_name


def extract_gaap_reconciliation(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: DocumentType | None = None,
    period_end_date: str | None = None,
) -> dict:
    """
    Extract line items from operating income or EBITDA reconciliation table for earnings announcements.

    This extractor is exclusive to earnings announcements and uses chunk-based embedding search
    to find reconciliation tables, similar to the balance sheet finding workflow.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2024")
        document_type: Document type (should be EARNINGS_ANNOUNCEMENT)

    Returns:
        Dictionary with extraction results:
        {
            "line_items": list of line items,
            "chunk_index": best chunk index found,
            "is_valid": bool,
            "validation_errors": list of error messages
        }
    """
    # Try top 5 dense chunks in sequence to find a complete reconciliation table
    text = None
    chunk_index = None

    # Get top numeric chunks
    from app.utils.document_section_finder import (
        find_top_numeric_chunks,
        get_chunk_with_context,
        rank_chunks_by_query,
    )

    # Step 1: Find top-10 chunks by number density
    top_numeric_chunks = find_top_numeric_chunks(document_id, file_path, top_k=10)

    # Step 2: Rank those top-10 chunks by query similarity
    query_texts = [
        "amortization",
        "depreciation",
        "stock-based",
        "acquisition",
        "restructuring",
        "non-GAAP",
        "adjusted",
        "reconciliation",
        "impairment",
    ]
    candidate_chunks = rank_chunks_by_query(document_id, file_path, top_numeric_chunks, query_texts)

    if not candidate_chunks:
        print("No chunks found with numbers, falling back to legacy search")  # Optional fallback

    for attempt_idx, idx in enumerate(candidate_chunks):
        chunk_msg = f"Checking chunk {idx} (attempt {attempt_idx + 1}) for complete GAAP to non-GAAP reconciliation table"
        print(chunk_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, chunk_msg)

        # Get chunk text with context
        chunk_text, start_char, log_info = get_chunk_with_context(
            document_id, file_path, idx, chars_before=2500, chars_after=2500
        )

        chars_msg = f"Extracted section (chars {log_info['start_extract_char']}-{log_info['end_extract_char']})"
        print(chars_msg)

        # Check if this chunk has a complete reconciliation table
        completeness_msg = f"Checking if chunk {idx} contains complete reconciliation table"
        print(completeness_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, completeness_msg
        )

        is_complete, explanation = check_table_completeness(
            chunk_text, time_period, period_end_date
        )

        if is_complete:
            complete_msg = f"Found complete reconciliation table in chunk {idx}: {explanation}"
            print(complete_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, complete_msg
            )
            text = chunk_text
            chunk_index = idx
            break
        else:
            incomplete_msg = (
                f"Chunk {idx} does not contain complete reconciliation table: {explanation}"
            )
            print(incomplete_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, incomplete_msg
            )

    if not text:
        error_msg = "No complete GAAP to non-GAAP reconciliation table found after checking top dense chunks"
        print(error_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, error_msg)
        return {
            "line_items": [],
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["No complete GAAP to non-GAAP reconciliation table found"],
        }

    # Extract line items using LLM
    extraction_msg = "Extracting line items from operating income or EBITDA reconciliation table"
    print(extraction_msg)
    add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, extraction_msg)

    validation_errors: list[str] = []
    extraction = extract_gaap_reconciliation_llm(text, time_period, period_end_date)
    line_items = extraction.get("line_items", []) if isinstance(extraction, dict) else []

    extracted_count_msg = f"Extracted {len(line_items)} line items from reconciliation table"
    print(extracted_count_msg)
    add_log(
        document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, extracted_count_msg
    )

    # Validate: sum of all items except last should equal last item (excluding intermediate totals)
    is_valid, validation_error = validate_reconciliation_table(line_items)

    if not is_valid and line_items:
        validation_errors.append(validation_error)
        validation_msg = f"Validation failed: {validation_error}"
        print(validation_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, validation_msg
        )

        # Step 1: Check if line items are from wrong time period
        time_check_msg = "Checking if line items belong to correct time period"
        print(time_check_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, time_check_msg
        )

        time_check_result = check_line_item_time_periods(line_items, time_period)
        mismatched_items = time_check_result.get("mismatched_items", [])

        if mismatched_items:
            # Remove out-of-place items
            mismatched_names = {item["line_name"] for item in mismatched_items}
            line_items = [item for item in line_items if item["line_name"] not in mismatched_names]

            removed_msg = f"Removed {len(mismatched_items)} out-of-period items: {', '.join(mismatched_names)}"
            print(removed_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, removed_msg
            )

            # Re-validate after removing mismatched items
            if line_items:
                is_valid, validation_error = validate_reconciliation_table(line_items)
                if is_valid:
                    validation_errors = []  # Clear errors if validation now passes
                    success_msg = "Validation passed after removing out-of-period items"
                    print(success_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        success_msg,
                    )
                else:
                    validation_errors.append(
                        f"Validation still failed after removing out-of-period items: {validation_error}"
                    )

        # Step 2: If still invalid, try final retry with full feedback
        if not is_valid and line_items:
            final_retry_msg = "Attempting final extraction with validation feedback"
            print(final_retry_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                final_retry_msg,
            )

            retry_result = retry_extraction_with_feedback(
                text, time_period, line_items, validation_error, period_end_date
            )

            final_line_items = retry_result.get("line_items", [])
            if final_line_items:
                line_items = final_line_items
                final_msg = f"Final retry extracted {len(line_items)} line items"
                print(final_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    final_msg,
                )

                # Final validation
                is_valid, validation_error = validate_reconciliation_table(line_items)
                if is_valid:
                    validation_errors = []
                    success_msg = "Validation passed after final retry"
                    print(success_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        success_msg,
                    )
                else:
                    validation_errors.append(
                        f"Validation failed after final retry: {validation_error}"
                    )

    if not line_items:
        validation_errors.append("No reconciliation line items extracted")
        error_msg = "No reconciliation line items extracted"
        print(error_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, error_msg)
        is_valid = False

    # Classify line items
    if line_items:
        classification_msg = "Classifying line items using LLM"
        print(classification_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, classification_msg
        )
        line_items = classify_line_items_llm(line_items)

    if is_valid:
        success_msg = f"Non-GAAP reconciliation extraction completed: {len(line_items)} line items"
        print(success_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, success_msg)

    return {
        "line_items": line_items,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }


def check_table_completeness(
    text: str, time_period: str, period_end_date: str | None = None
) -> tuple[bool, str]:
    """
    Check if the chunk contains a complete GAAP to non-GAAP reconciliation table for EBITDA or operating income.

    Args:
        text: Text from chunk to check
        time_period: Time period (e.g., "Q3 2024")
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Tuple of (is_complete, explanation)
    """
    validation_criteria = """- Be for either: EBITDA (Earnings Before Interest, Taxes, Depreciation, and Amortization) or Operating Income/Loss or Income from Operations
- Start with an operating income, other GAAP results, or something similar
- List all adjustments/addbacks (amortization, depreciation, stock-based compensation, etc.)
- End with the non-GAAP measure (non-GAAP operating income, EBITDA, adjusted EBITDA, etc.)
- The sum of the starting measure plus all adjustments should equal the ending non-GAAP measure

IMPORTANT: The table must be for EBITDA or operating income reconciliation.
DO NOT consider:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other types of reconciliation table
RARE CASES, the table has Gross Profit, Operating Income, Taxes, Net Income all mixed. In this case pull the correct column.
"""

    return check_section_completeness_llm(
        text,
        time_period,
        "GAAP to non-GAAP reconciliation table",
        validation_criteria,
        period_end_date,
    )


def extract_gaap_reconciliation_llm(
    text: str, time_period: str, period_end_date: str | None = None
) -> dict:
    """
    Extract line items from operating income or EBITDA reconciliation table.

    Args:
        text: Text containing GAAP reconciliation table
        time_period: Time period (e.g., "Q3 2024")
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with extracted line items
    """
    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""Extract all line items from the OPERATING INCOME reconciliation table or EBITDA reconciliation table
in the following document text for the {period_info}.

IMPORTANT: Extract ONLY from operating income reconciliation or EBITDA reconciliation tables.
DO NOT extract from:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other type of reconciliation table

Focus on extracting all line items from the operating income or EBITDA reconciliation table, such as:
- Amortization
- Depreciation
- Stock-based compensation
- Acquisition-related expenses
- Restructuring charges
- Other adjustments that reconcile GAAP operating income or GAAP net income to non-GAAP operating income or EBITDA

For each line item, classify it as:
- "Recurring": Normal business operations that occur regularly (e.g., depreciation, amortization, stock-based compensation)
- "One-Time": Unusual or infrequent events (e.g., restructuring charges, impairment, acquisition costs)
- "Total": Summary/total line items (e.g., "Total Adjustments", "Adjusted EBITDA", "Non-GAAP Operating Income")

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null
- Extract line items ONLY from the operating income or EBITDA reconciliation table/section in the document text

Return a JSON object with the following structure:
{{
  "line_items": [
    {{
      "line_name": "exact name as it appears in the document",
      "line_value": numeric value (as number, not string),
      "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
      "line_category": "Recurring", "One-Time", or "Total"
    }}
  ]
}}

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    response_text = generate_content_safe(prompt, temperature=0.0)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def validate_reconciliation_table(line_items: list[dict]) -> tuple[bool, str]:
    """
    Validate that the sum of all line items except the last equals the last line item.
    Excludes any "Total" line items from the middle of the calculation.

    Args:
        line_items: List of line items from reconciliation table

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(line_items) < 2:
        return False, "Reconciliation table must have at least 2 line items"

    # Filter out any "Total" items from the middle (not the last item)
    # The last item is expected to be the final total
    items_to_sum = []
    for i, item in enumerate(line_items[:-1]):
        # Always include the first item (the starting GAAP measure) as it is the base for the reconciliation
        if i == 0:
            items_to_sum.append(item)
            continue

        line_category = item.get("line_category", "")
        # Skip items with line_category "Total" (these are intermediate totals)
        # Fallback to checking line_name if line_category is not set or not "Total"
        if line_category == "Total":
            continue  # Skip this item if its category is "Total"
        else:
            # If line_category is not "Total" (e.g., Recurring, One-Time, or empty),
            # then check line_name as a fallback for older/less structured extractions
            line_name = item.get("line_name", "").lower()
            if "total" not in line_name:
                items_to_sum.append(item)

    last_item = line_items[-1]

    # Sum all values except the last (excluding intermediate totals)
    total_sum = 0.0
    for item in items_to_sum:
        value = item.get("line_value")
        if value is not None:
            total_sum += float(value)

    # Get the last item's value
    last_value = last_item.get("line_value")
    if last_value is None:
        return False, "Last line item has no value"

    last_value_float = float(last_value)

    # Check if they match (allow small floating point differences)
    tolerance = 0.01
    if abs(total_sum - last_value_float) > tolerance:
        return (
            False,
            f"Sum of all items except last ({total_sum}) does not equal last item ({last_value_float}). Difference: {abs(total_sum - last_value_float)}",
        )

    return True, ""


def check_line_item_time_periods(line_items: list[dict], expected_time_period: str) -> dict:
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


def retry_extraction_with_feedback(
    text: str,
    time_period: str,
    current_line_items: list[dict],
    validation_error: str,
    period_end_date: str | None = None,
) -> dict:
    """
    Final retry attempt: pass full context, validation error, and current table to LLM
    for one last extraction attempt.

    Args:
        text: Document text containing reconciliation table
        time_period: Expected time period
        current_line_items: Current extracted line items that failed validation
        validation_error: The validation error message
        period_end_date: Period end date (e.g., "2024-03-31")

    Returns:
        Dictionary with new line items
    """
    items_json = json.dumps(current_line_items, indent=2)

    period_info = f"time period: {time_period}"
    if period_end_date:
        period_info += f" (period ending {period_end_date})"

    prompt = f"""I attempted to extract an operating income or EBITDA reconciliation table for {period_info}, but validation failed.

Current extraction:
{items_json}

Validation error:
{validation_error}

Please re-extract the reconciliation table from the document text below, ensuring:
1. The table is for {time_period} (not other periods)
2. All line items are from the same reconciliation table
3. The sum of all items (excluding any intermediate "Total" items) equals the final total
4. Start with the GAAP measure (operating income, net income, or similar)
5. List all adjustments/addbacks
6. End with the non-GAAP measure (non-GAAP operating income, EBITDA, adjusted EBITDA, etc.)

IMPORTANT: Extract ONLY from operating income or EBITDA reconciliation tables.
DO NOT extract from:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other type of reconciliation table

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null

Return a JSON object with:
{{
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document",
            "line_value": numeric value (as number, not string),
            "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
            "line_category": "Recurring", "One-Time", or "Total"
        }}
    ]
}}

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    try:
        result = call_llm_with_retry(prompt, max_retries=2, temperature=0.0)
        return result
    except Exception as e:
        print(f"Error in final retry extraction: {str(e)}")
        return {"line_items": []}


def classify_line_items_llm(line_items: list[dict], max_retries: int = 3) -> list[dict]:
    """
    Use LLM to categorize each line item as operating or non-operating.
    Includes retry logic for transient API errors.
    """
    AUTHORITATIVE_LOOKUP = {
        "Total Net Revenue": "Operating",
        "Revenue": "Operating",
        "Cost of Revenue": "Operating",
        "Cost of Goods Sold": "Operating",
        "Gross Profit": "Operating",
        "Operating Expenses": "Operating",
        "Research and Development": "Operating",
        "Sales and Marketing": "Operating",
        "Sales": "Operating",
        "Marketing": "Operating",
        "General and Administrative": "Operating",
        "Depreciation": "Operating",
        "Amortization of Intangible Assets": "Non-Operating",
        "Operating Income": "Operating",
        "Interest Expense": "Non-Operating",
        "Interest Income": "Non-Operating",
        "Other Income (Expense)": "Non-Operating",
        "Foreign Exchange Gain (Loss)": "Non-Operating",
        "Gain (Loss) on Investments": "Non-Operating",
        "Gain (Loss) on Sale of Assets": "Non-Operating",
        "Restructuring Charges": "Non-Operating",
        "Impairment Charges": "Non-Operating",
        "Write-offs": "Non-Operating",
        "Legal Settlements": "Non-Operating",
        "Income Tax Expense": "Operating",
        "Sales Tax": "Operating",
        "Property Tax": "Operating",
    }

    # Create normalized lookup map
    normalized_lookup = {normalize_line_name(k): v for k, v in AUTHORITATIVE_LOOKUP.items()}

    # Prepare lookup context for prompt
    lookup_context = "\n".join([f'  "{k}": "{v}"' for k, v in AUTHORITATIVE_LOOKUP.items()])

    # Prepare context for LLM
    items_text = "\n".join([f"- {item['line_name']}" for item in line_items])

    prompt = f"""Classify each line item as operating or non-operating.

HIGHEST PRIORITY: Use the AUTHORITATIVE_LOOKUP below as a binding decision table.
- If a provided line item matches a key in AUTHORITATIVE_LOOKUP after normalization, you MUST use that value.
- Normalization: trim, case-insensitive, collapse repeated whitespace, remove leading/trailing punctuation.
- If no match: use the definitions below.

AUTHORITATIVE_LOOKUP:
{{
{lookup_context}
}}

Operating items are normal business operations:
- Revenue, Cost of Revenue, Operating Expenses, Depreciation, Interest Expense, Taxes
- Regular business operations that happen every period

Non-operating items are unusual or outside core operations:
- Restructuring Charges, Impairment Charges, Gain/Loss on Sale of Assets
- Legal Settlements, Acquisition Costs, Discontinued Operations
- Amortization of Intangible Assets
- Other unusual gains or losses

Line items:
{items_text}

Return a JSON object with the following structure:
{{
    "classifications": [
        {{
            "line_name": "exact line name as provided",
            "is_operating": true, false, or null (null for totals except "Total Net Revenue")
        }},
        ...
    ]
}}

Return only valid JSON, no additional text."""

    def process_result(result):
        classifications = {
            item["line_name"]: {
                "is_operating": item.get("is_operating"),
            }
            for item in result.get("classifications", [])
        }

        classified_items = []
        for item in line_items:
            item_copy = item.copy()
            line_name = item["line_name"]
            classification = classifications.get(line_name, {})

            # First try authoritative lookup for is_operating
            normalized_name = normalize_line_name(line_name)

            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                # Map "Operating" -> True, "Non-Operating" -> False
                is_operating_lookup = lookup_value == "Operating"
                item_copy["is_operating"] = is_operating_lookup
            else:
                # Fallback to LLM
                item_copy["is_operating"] = classification.get("is_operating", None)

            # Handle Totals special case - check existing line_category first
            existing_category = item_copy.get("line_category", "")
            line_name_lower = line_name.lower()
            is_total = existing_category == "Total" or "total" in line_name_lower

            if is_total:
                if "total net revenue" in line_name_lower or "total revenue" in line_name_lower:
                    item_copy["is_operating"] = True
                else:
                    item_copy["is_operating"] = None

            # Preserve line_category if it exists from initial extraction
            # Only set default if missing
            if "line_category" not in item_copy or not item_copy.get("line_category"):
                item_copy["line_category"] = "Recurring"  # Default fallback

            classified_items.append(item_copy)

        return classified_items

    try:
        # Use call_llm_with_retry but we need to handle the custom processing
        # Since call_llm_with_retry returns the parsed JSON, we can just use that
        result = call_llm_with_retry(prompt, max_retries=max_retries, temperature=0.0)
        return process_result(result)

    except Exception as e:
        print(f"Error classifying line items: {str(e)}")
        # Return items without classification if classification fails
        return line_items

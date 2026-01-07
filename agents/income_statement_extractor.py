"""
Income statement extraction agent using Gemini LLM and embeddings
"""

import json

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
from app.utils.line_item_utils import normalize_line_name
from app.utils.pdf_extractor import extract_text_from_pdf


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
        attempt: 0 = chunk before balance sheet, 1 = chunk after balance sheet, 2 = 2 chunks after
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
        # attempt 0 = chunk before balance sheet
        # attempt 1 = chunk after balance sheet
        # attempt 2 = 2 chunks after balance sheet
        if attempt == 0:
            target_chunk_index = balance_chunk_index - 1
            direction = "before"
        elif attempt == 1:
            target_chunk_index = balance_chunk_index + 1
            direction = "after"
        elif attempt == 2:
            target_chunk_index = balance_chunk_index + 2
            direction = "2 after"
        else:
            print(f"Invalid attempt number: {attempt}, must be 0, 1, or 2")
            return None, None, None

        # Validate chunk index
        if target_chunk_index < 0 or target_chunk_index >= num_chunks:
            print(f"Target chunk index {target_chunk_index} is out of bounds (0-{num_chunks - 1})")
            return None, None, None

        # Get chunk text
        chunk_text, chunk_start_page, chunk_end_page = get_chunk_text(
            file_path, target_chunk_index, chunk_size
        )

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


def find_income_statement_section(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: str | None = None,
    chunk_rank: int = 0,
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embedding to locate the income statement section.
    May be called by various names (e.g., "consolidated statement of operations").

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

        # Initial query texts for finding the income statement section
        query_texts = [
            "consolidated statement of operations",
            "income statement",
            "statement of operations",
            "consolidated income statement",
        ]

        # Re-ranking query terms: normalized income statement line items
        rerank_query_texts = [
            # "Net Income",
            # "Tax",
            # "Interest Expense",
            # "Interest Income",
            "consolidated statement of operations",
            "income statement",
            "statement of operations",
            "consolidated income statement",
        ]
        rerank_query_texts = [normalize_line_name(term) for term in rerank_query_texts]

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
        print(f"Error finding income statement section: {str(e)}")
        return None, None, None


def extract_income_statement_llm(text: str, time_period: str, currency: str | None = None) -> dict:
    """
    Use LLM to extract income statement line items exactly line by line.
    Also extracts revenue for the same period in the prior year.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known

    Returns:
        Dictionary with income statement data
    """
    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the time period: {time_period}.
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
    "currency": currency code (extract ONLY if explicitly stated in document, otherwise null),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract ONLY if explicitly stated like "in millions", "in thousands", etc., otherwise null),
    "time_period": "{time_period}",
    "revenue_prior_year": revenue for the same period in the prior year (as number, null if not EXPLICITLY found in document),
    "revenue_prior_year_unit": unit for revenue_prior_year - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as "unit", null if revenue_prior_year is null),
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string) - MUST match exactly what is shown in the document,
            "line_category": one of ["Recurring", "One-Time", "Total"] - categorize each line item:
              - "Recurring": Normal business operations that occur regularly
              - "One-Time": Unusual or infrequent items
              - "Total": Summary/total line items (e.g., "Total Net Revenue", "Total Expenses", "Total Operating Expenses")
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
- Extract the currency code ONLY if explicitly stated in the document text
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue) - ONLY if explicitly shown in the document text, otherwise use null
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- Categorize each line item as "Recurring", "One-Time", or "Total":
  - "Recurring": Normal business operations that occur regularly (e.g., Revenue, Cost of Revenue, Operating Expenses, Depreciation, Interest Expense, Taxes)
  - "One-Time": Unusual or infrequent items (e.g., Restructuring Charges, Impairment Charges, Gain/Loss on Sale of Assets, Legal Settlements, Acquisition Costs, Discontinued Operations)
  - "Total": Summary/total line items (e.g., "Total Net Revenue", "Total Expenses", "Total Operating Expenses", "Total Costs")
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
) -> dict:
    """
    Use LLM to extract income statement with validation error feedback for retry.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        previous_extraction: Previous extraction attempt (to show what was extracted)
        validation_errors: List of validation errors with calculated differences
        currency: Currency code if known

    Returns:
        Dictionary with income statement data
    """
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    previous_items_text = json.dumps(previous_extraction.get("line_items", []), indent=2)

    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the time period: {time_period}.
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
- Making sure line categories are correct
- Note: Line items should be normalized so that costs are shown as negative values

Return a JSON object with the following structure:
{{
    "currency": currency code (extract from document),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "revenue_prior_year": revenue for the same period in the prior year (as number, null if not found),
    "revenue_prior_year_unit": unit for revenue_prior_year - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as "unit", null if revenue_prior_year is null),
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["Recurring", "One-Time", "Total"]
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
- Extract the currency code ONLY if explicitly stated in the document text
- Extract the unit ONLY if the document explicitly states it (look for phrases like "in millions", "in thousands", "in billions", or "in ten thousands")
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue) - ONLY if explicitly shown in the document text, otherwise use null
- Use "ten_thousands" ONLY if the document explicitly states values are in ten thousands
- Categorize each line item as "Recurring" or "One-Time"
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


def _parse_llm_json_response(response_text: str) -> dict:
    """Parse LLM JSON response, handling code blocks."""
    import json

    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def get_income_statement_llm_insights(
    line_items: list[dict],
) -> tuple[dict, list[str]]:
    """
    Use LLM to identify key line items in an income statement.
    This function is used during post-processing to identify and standardize line item names.
    """
    json_structure = """{
    "total_net_revenue_line": "exact line name for total net revenue (must match a name from the list above, or null if not found)",
    "cost_of_revenue_line": "exact line name for cost of revenue or cost of goods sold (must match a name from the list above, or null if not found)",
    "gross_profit_line": "exact line name for gross profit (must match a name from the list above, or null if not found)",
    "operating_expenses_line": "exact line name for total operating expenses (must match a name from the list above, or null if not found)",
    "operating_income_line": "exact line name for operating income (must match a name from the list above, or null if not found)",
    "pretax_income_line": "exact line name for income before taxes (must match a name from the list above, or null if not found)",
    "tax_expense_line": "exact line name for tax expense (must match a name from the list above, or null if not found)",
    "net_income_line": "exact line name for net income (must match a name from the list above, or null if not found)"
}"""
    guidance = """- Total net revenue: Revenue, Total Revenue, Net Sales, Net Revenue, Total Net Revenue
- Cost of revenue: Cost of revenue, Cost of goods sold, COGS, Cost of sales
- Gross profit: Gross Profit, Gross Margin, Gross Income
- Operating expenses: Total operating expenses, Operating expenses
- Operating income: Operating Income, Income from Operations, Operating Profit, Operating Earnings
- Pretax income: Income Before Tax, Earnings Before Income Tax, Profit Before Tax, Income Before Income Tax Expense
- Tax expense: Income Tax Expense, Provision for Income Taxes, Income Taxes, Taxes
- Net income: Net Income, Net Earnings, Profit After Tax, After Tax Profit"""

    return get_llm_insights_generic(line_items, "an income statement", json_structure, guidance)


def check_income_statement_completeness_llm(text: str, time_period: str) -> bool:
    """
    Use LLM to check if the chunk text contains a complete consolidated income statement.
    This is called BEFORE extraction to validate we have the right chunk.

    Args:
        text: Text containing income statement section (chunk text)
        time_period: Time period (e.g., "Q3 2023")

    Returns:
        True if complete, False otherwise
    """
    validation_criteria = """- Start with revenue (total net revenue, net sales, etc.)
- Include cost of revenue/cost of goods sold
- Have a gross profit line
- Include operating expenses (R&D, SG&A, etc.)
- Have an operating income/income from operations line
- Include interest income/expense and other non-operating items
- Have an income before taxes/pretax income line
- Include tax expense
- End with net income/net earnings"""

    return check_section_completeness_llm(
        text, time_period, "consolidated income statement", validation_criteria
    )


def _match_line_item(line_items: list[dict], target_name: str | None) -> dict | None:
    """Find matching line item by name."""
    from difflib import SequenceMatcher

    if not target_name:
        return None

    normalized_target = normalize_line_name(target_name)
    best_item = None
    best_ratio = 0.0

    for item in line_items:
        normalized_item = normalize_line_name(item.get("line_name", ""))
        if normalized_item == normalized_target:
            return item

        ratio = SequenceMatcher(None, normalized_item, normalized_target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_item = item

    if best_ratio >= 0.75:
        return best_item

    return None


def post_process_income_statement_line_items(
    line_items: list[dict],
) -> tuple[list[dict], list[str]]:
    """
    Post-process income statement line items:
    1. Use LLM to identify key line items
    2. Rename identified items with standardized names (original in parentheses)
    3. Detect cost format (positive vs negative) and normalize to negative costs
    4. Validate calculations during normalization

    Returns:
        Tuple of (processed_line_items, validation_errors)
    """
    if not line_items:
        return line_items, []

    # Step 1: Get LLM insights to identify key line items
    llm_insights, _ = get_income_statement_llm_insights(line_items=line_items)

    # Mapping of standardized names to LLM insight keys
    standard_names = {
        "total_net_revenue_line": "Total Net Revenue",
        "cost_of_revenue_line": "Cost of Revenue",
        "gross_profit_line": "Gross Profit",
        "operating_expenses_line": "Operating Expenses",
        "operating_income_line": "Operating Income",
        "pretax_income_line": "Pretax Income",
        "tax_expense_line": "Tax Expense",
        "net_income_line": "Net Income",
    }

    # Step 2: Rename identified line items
    from app.utils.line_item_utils import extract_original_name_from_standardized as get_orig_name

    processed_items = []

    for item in line_items:
        item_copy = item.copy()
        current_name = item.get("line_name", "")

        # Check if this item matches any of the identified key items
        for insight_key, standard_name in standard_names.items():
            llm_line_name = llm_insights.get(insight_key)
            if llm_line_name and _match_line_item([item], llm_line_name):
                # Extract original name if it was already standardized
                original_name = get_orig_name(current_name)

                # Rename: "Standard Name (Original Name)"
                # Only apply if it's not already standardized to THIS standard name
                new_name = f"{standard_name} ({original_name})"
                if current_name != new_name:
                    item_copy["line_name"] = new_name
                break

        processed_items.append(item_copy)

    # Step 3: Detect cost format and normalize
    # Find key line items: revenue, gross profit, operating income, pretax income
    revenue_item = None
    gross_profit_item = None
    operating_income_item = None
    pretax_income_item = None

    for idx, item in enumerate(processed_items):
        item_name_lower = item.get("line_name", "").lower()
        # Look for Total Net Revenue (standardized name) first, then fallback to any total revenue
        if "total net revenue" in item_name_lower:
            if revenue_item is None:
                revenue_item = (idx, item)
        elif "revenue" in item_name_lower and "total" in item_name_lower:
            if revenue_item is None:
                revenue_item = (idx, item)

        if "gross profit" in item_name_lower:
            if gross_profit_item is None:
                gross_profit_item = (idx, item)

        # Look for standardized Operating Income name
        if "operating income (" in item_name_lower:
            if operating_income_item is None:
                operating_income_item = (idx, item)
        elif "operating income" in item_name_lower and "operating income (" not in item_name_lower:
            # Fallback: any operating income line
            if operating_income_item is None:
                operating_income_item = (idx, item)

        # Look for standardized Pretax Income name
        if "pretax income (" in item_name_lower:
            if pretax_income_item is None:
                pretax_income_item = (idx, item)
        elif any(
            term in item_name_lower
            for term in ["pretax income", "income before tax", "income before income tax"]
        ):
            if pretax_income_item is None:
                pretax_income_item = (idx, item)

    # Debug: print found items
    print(
        f"Post-processing: Found revenue_item at idx={revenue_item[0] if revenue_item else None} "
        f"(name={revenue_item[1].get('line_name') if revenue_item else None}), "
        f"gross_profit_item at idx={gross_profit_item[0] if gross_profit_item else None}, "
        f"operating_income_item at idx={operating_income_item[0] if operating_income_item else None} "
        f"(name={operating_income_item[1].get('line_name') if operating_income_item else None}), "
        f"pretax_income_item at idx={pretax_income_item[0] if pretax_income_item else None}"
    )

    validation_errors = []  # Collect validation errors during normalization

    def normalize_items_between(start_item, end_item, description):
        """Normalize items between two line items by detecting if they should be flipped.
        Also validates that the calculation matches the reported value.
        Returns a validation error message if validation fails, None otherwise.
        """
        if not start_item or not end_item:
            return None

        start_idx = start_item[0]
        end_idx = end_item[0]

        if start_idx >= end_idx:
            return None

        items_between = processed_items[start_idx + 1 : end_idx]
        if not items_between:
            return None

        # Filter out totals to avoid double counting in validation
        # Totals are identified by line_category == "Total" or line name containing "total"
        non_total_items = []
        for item in items_between:
            line_name_lower = item.get("line_name", "").lower()
            line_category = item.get("line_category", "").lower()
            is_total = line_category == "total" or "total" in line_name_lower
            if not is_total:
                non_total_items.append(item)

        # Calculate sums to test both formats (excluding totals)
        sum_between_raw = sum(item.get("line_value", 0) for item in non_total_items)
        sum_between_abs = sum(abs(item.get("line_value", 0)) for item in non_total_items)
        start_value = start_item[1].get("line_value", 0)
        end_value = end_item[1].get("line_value", 0)
        start_name = start_item[1].get("line_name", "Start")
        end_name = end_item[1].get("line_name", "End")

        # Test which formula matches: start + items = end (negative costs) or start - items = end (positive costs)
        # When costs are negative: Revenue + (negative sum) = Operating Income ✓ (desired format)
        # When costs are positive: Revenue - (positive sum) = Operating Income (needs flipping)
        diff_with_negative = abs((start_value + sum_between_raw) - end_value)
        diff_with_positive = abs((start_value - sum_between_abs) - end_value)

        # Validation: If at least one of the differences is not zero, validation has failed
        # Use a small tolerance for floating point comparison
        tolerance = max(abs(end_value) * 0.01, 0.01) if end_value != 0 else 0.01
        validation_failed = (diff_with_negative > tolerance) and (diff_with_positive > tolerance)

        # Count negative vs positive items to help decide when there's a tie (excluding totals)
        negative_count = sum(1 for item in non_total_items if item.get("line_value", 0) < 0)
        positive_count = sum(1 for item in non_total_items if item.get("line_value", 0) > 0)
        mostly_positive = positive_count > negative_count

        # Debug output
        print(
            f"Normalizing {description}: start={start_value}, end={end_value}, raw_sum={sum_between_raw}, abs_sum={sum_between_abs}"
        )
        print(
            f"  Diff with negative costs (desired): {diff_with_negative}, Diff with positive costs: {diff_with_positive}"
        )
        print(
            f"  Items: {negative_count} negative, {positive_count} positive (mostly_positive={mostly_positive})"
        )

        # Default assumption: costs should be NEGATIVE, so flip if positive format matches or if tie and mostly positive
        # If positive format matches better, OR if they're equal but mostly positive, flip ALL signs to make costs negative
        should_flip = (diff_with_positive < diff_with_negative) or (
            diff_with_positive == diff_with_negative and mostly_positive
        )

        if should_flip:
            print("  Costs detected as positive, flipping signs to make negative...")
            for item in non_total_items:  # Only flip non-total items
                item_value = item.get("line_value", 0)
                if item_value == 0:
                    continue

                item_name_lower = item.get("line_name", "").lower()
                is_benefit = any(
                    keyword in item_name_lower
                    for keyword in ["benefit", "credit", "gain", "recovery", "refund"]
                )

                if not is_benefit:
                    # Flip ALL signs (both positive and negative) to normalize costs to negative
                    old_value = item["line_value"]
                    item["line_value"] = -item_value
                    print(
                        f"    Flipped {item.get('line_name')}: {old_value} -> {item['line_value']}"
                    )
                else:
                    print(f"    Skipped benefit/credit: {item.get('line_name')} = {item_value}")

        # After normalization, check validation again with updated values
        # Recalculate with potentially flipped values (excluding totals)
        final_diff = diff_with_negative
        final_sum = sum_between_raw

        if should_flip:
            # After flipping, recalculate the sum of all items (now normalized to negative costs, excluding totals)
            final_sum = sum(item.get("line_value", 0) for item in non_total_items)
            final_diff = abs((start_value + final_sum) - end_value)
        else:
            # Use the already calculated sum (which excludes totals)
            final_sum = sum_between_raw
            final_diff = diff_with_negative

        # Return validation error if validation failed (at least one diff was not zero)
        if validation_failed:
            # After normalization, re-check if it's still invalid
            tolerance = max(abs(end_value) * 0.01, 0.01) if end_value != 0 else 0.01
            if final_diff > tolerance:
                calculated_value = start_value + final_sum
                return f"{description.capitalize()} calculation mismatch: {start_name} + items = {calculated_value:.2f}, but {end_name} = {end_value:.2f} (difference: {final_diff:.2f})"

        return None

    # Normalize items between revenue and gross profit
    if revenue_item and gross_profit_item:
        error = normalize_items_between(revenue_item, gross_profit_item, "costs")
        if error:
            validation_errors.append(error)

    # Normalize items between gross profit and operating income
    if gross_profit_item and operating_income_item:
        error = normalize_items_between(
            gross_profit_item, operating_income_item, "operating expenses"
        )
        if error:
            validation_errors.append(error)

    # Normalize items between operating income and pretax income
    if operating_income_item and pretax_income_item:
        error = normalize_items_between(
            operating_income_item, pretax_income_item, "non-operating items"
        )
        if error:
            validation_errors.append(error)

    # Handle missing gross profit: check between revenue and operating income or pretax income
    if revenue_item and not gross_profit_item:
        print(
            "Gross profit missing, normalizing between Revenue and Operating Income/Pretax Income"
        )
        if operating_income_item:
            error = normalize_items_between(
                revenue_item, operating_income_item, "costs and expenses"
            )
            if error:
                validation_errors.append(error)
        elif pretax_income_item:
            error = normalize_items_between(revenue_item, pretax_income_item, "costs and expenses")
            if error:
                validation_errors.append(error)

    # Handle missing operating income: check between revenue/gross profit and pretax income
    if not operating_income_item and pretax_income_item:
        print(
            "Operating income missing, normalizing between Revenue/Gross Profit and Pretax Income"
        )
        if gross_profit_item:
            error = normalize_items_between(
                gross_profit_item, pretax_income_item, "operating and non-operating items"
            )
            if error:
                validation_errors.append(error)
        elif revenue_item:
            error = normalize_items_between(revenue_item, pretax_income_item, "all expenses")
            if error:
                validation_errors.append(error)

    return processed_items, validation_errors


def validate_income_statement_section(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate income statement section (Stage 1): Check minimum line count and presence of required items.
    This is used to validate that the correct section was found before proceeding to extraction validation.

    Args:
        line_items: List of income statement line items

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check if line_items is empty
    if not line_items or len(line_items) == 0:
        errors.append("Income statement is empty - no line items extracted")
        return False, errors

    # Check if we have at least some meaningful line items (not just empty strings)
    valid_items = [
        item for item in line_items if item.get("line_name") and item.get("line_name").strip()
    ]
    if len(valid_items) == 0:
        errors.append("Income statement has no valid line items")
        return False, errors

    # Check minimum number of lines required
    MIN_LINES_REQUIRED = 5
    if len(valid_items) < MIN_LINES_REQUIRED:
        errors.append(
            f"Income statement must have at least {MIN_LINES_REQUIRED} line items, found {len(valid_items)}"
        )
        return False, errors

    def normalize_value(value: object) -> float | None:
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

    # Find key values - prioritize standardized names first
    revenue_value = None
    net_income = None

    # First pass: Look for standardized names (e.g., "Total Net Revenue (Revenue)")
    for item in line_items:
        item_name_lower = item["line_name"].lower()
        item_value = normalize_value(item.get("line_value"))
        if item_value is None:
            continue

        if "total net revenue (" in item_name_lower:
            revenue_value = item_value
        elif "net income (" in item_name_lower and "per share" not in item_name_lower:
            net_income = item_value

    # Second pass: Look for revenue and net income if not found with standardized name
    items_dict = {}
    for item in line_items:
        item_value = normalize_value(item.get("line_value"))
        if item_value is None:
            continue
        items_dict[item["line_name"].lower()] = item_value

    if revenue_value is None:
        for key, value in items_dict.items():
            if "total net revenue" in key or ("revenue" in key and "total" in key):
                revenue_value = value
                break
            elif "revenue" in key and "total" not in key and "net" not in key:
                if revenue_value is None:
                    revenue_value = value

    if net_income is None:
        for key, value in items_dict.items():
            if ("net income" in key or "net earnings" in key) and "per share" not in key:
                net_income = value
                break

    # Check that required key items are present
    # Total Net Revenue is required
    if revenue_value is None:
        errors.append("Income statement is missing Total Net Revenue")

    # Net Income is required
    if net_income is None:
        errors.append("Income statement is missing Net Income")

    return len(errors) == 0, errors


def validate_income_statement(
    line_items: list[dict], revenue: float | None = None
) -> tuple[bool, list[str]]:
    """
    Combined validation function for backward compatibility.
    Validates section (line count + required items).

    Args:
        line_items: List of income statement line items
        revenue: Revenue value (if available) - not used in section validation

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    return validate_income_statement_section(line_items)


def classify_line_items_llm(line_items: list[dict], max_retries: int = 3) -> list[dict]:
    """
    Use LLM to categorize each income statement line item as operating or non-operating.
    Includes retry logic for transient API errors.

    Args:
        line_items: List of income statement line items
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        List of line items with is_operating classification added
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

    prompt = f"""Classify each income statement line item as operating or non-operating, and as recurring, one-time, or total.

HIGHEST PRIORITY: Use the AUTHORITATIVE_LOOKUP below as a binding decision table.
- If a provided line item matches a key in AUTHORITATIVE_LOOKUP after normalization, you MUST use that value.
- Normalization: trim, case-insensitive, collapse repeated whitespace, remove leading/trailing punctuation.
- If no match: use the definitions below.

AUTHORITATIVE_LOOKUP:
{{
{lookup_context}
}}

Recurring items are normal business operations that occur regularly:
- Revenue, Cost of Revenue, Operating Expenses, Depreciation, Interest Expense, Taxes
- Regular business operations that happen every period

One-time items are unusual or infrequent events:
- Restructuring Charges, Impairment Charges, Gain/Loss on Sale of Assets
- Legal Settlements, Acquisition Costs, Discontinued Operations
- Other unusual gains or losses that are not expected to recur

Total items are summary/total line items:
- "Total Net Revenue", "Total Revenue", "Total Expenses", "Total Operating Expenses", "Total Costs", etc.
- IMPORTANT: For total items, set is_operating to null (do not provide true or false), EXCEPT for "Total Net Revenue" which should be is_operating: true

Line items:
{items_text}

Return a JSON object with the following structure:
{{
    "classifications": [
        {{
            "line_name": "exact line name as provided",
            "is_operating": true, false, or null (null for totals except "Total Net Revenue"),
            "line_category": "Recurring", "One-Time", or "Total"
        }},
        ...
    ]
}}

Return only valid JSON, no additional text."""

    def process_result(result):
        classifications = {
            item["line_name"]: {
                "is_operating": item.get("is_operating"),
                "line_category": item.get("line_category", "Recurring"),
            }
            for item in result.get("classifications", [])
        }

        classified_items = []
        for item in line_items:
            item_copy = item.copy()
            line_name = item["line_name"]
            classification = classifications.get(line_name, {})

            line_name_lower = line_name.lower()
            normalized_name = normalize_line_name(line_name)

            # First try authoritative lookup for is_operating
            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                # Map "Operating" -> True, "Non-Operating" -> False
                is_operating_lookup = lookup_value == "Operating"
                item_copy["is_operating"] = is_operating_lookup
            else:
                # Fallback to LLM
                item_copy["is_operating"] = classification.get("is_operating", None)

            # Handle Totals special case
            is_total = classification.get("line_category") == "Total" or "total" in line_name_lower

            if is_total:
                if "total net revenue" in line_name_lower or "total revenue" in line_name_lower:
                    item_copy["is_operating"] = True
                else:
                    item_copy["is_operating"] = None

            # If authoritative lookup said Operating/Non-Op, trust it unless it's a Total that should be null
            # (The Total logic above overrides the lookup if it's a total)

            if "line_category" not in item_copy or not item_copy.get("line_category"):
                item_copy["line_category"] = classification.get("line_category", "Recurring")
            classified_items.append(item_copy)

        return classified_items

    try:
        # Use call_llm_with_retry but we need to handle the custom processing
        # Since call_llm_with_retry returns the parsed JSON, we can just use that
        result = call_llm_with_retry(prompt, max_retries=max_retries, temperature=0.0)
        return process_result(result)

    except Exception as e:
        print(f"Error classifying income statement line items: {str(e)}")
        # Return items without classification if classification fails
        return line_items


def extract_income_statement(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 3,
    document_type: str | None = None,
    balance_sheet_chunk_index: int | None = None,
) -> dict:
    """
    Main function to extract income statement with two-stage validation and retries.

    Stage 1: Find correct section (retry with chunk before, after, 2 after balance sheet)
    Stage 2: Post-process and validate extraction (retry extraction with LLM feedback)

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts for section finding (3 total: before, after, 2 after)
        document_type: Document type (e.g., "earnings_announcement", "annual_filing", "quarterly_filing")

    Returns:
        Dictionary with income statement data and validation status
    """
    # Stage 1: Find correct section (retry with different chunk positions relative to balance sheet)
    income_statement_text = None
    start_page = None
    log_info = None
    extracted_data = None
    successful_chunk_index = None  # Track successful chunk index for persistence

    for section_attempt in range(max_retries):  # 3 tries: before, after, 2 after
        try:
            section_msg = f"Stage 1: Finding income statement section (attempt {section_attempt + 1}: {'before' if section_attempt == 0 else 'after' if section_attempt == 1 else '2 after'} balance sheet)"
            print(section_msg)
            add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, section_msg)

            # Find income statement section near balance sheet
            income_statement_text, start_page, log_info = find_income_statement_near_balance_sheet(
                document_id,
                file_path,
                time_period,
                document_type,
                attempt=section_attempt,
                balance_sheet_chunk_index=balance_sheet_chunk_index,
            )

            if not income_statement_text:
                # Fallback: extract full document if embedding search fails
                fallback_msg = "Embedding search failed, extracting full document..."
                print(fallback_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    fallback_msg,
                )
                income_statement_text, _, _ = extract_text_from_pdf(file_path, max_pages=None)
                income_statement_text = income_statement_text[:50000]  # Limit to 50k chars
                extracted_msg = (
                    f"Extracted {len(income_statement_text)} characters from full document"
                )
                print(extracted_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    extracted_msg,
                )
            else:
                # Log chunk/page information if available
                if log_info:
                    direction_text = log_info.get("direction", "near")
                    chunk_index = log_info.get("income_statement_chunk_index", "unknown")
                    chunk_start = log_info.get("chunk_start_page", "unknown")
                    chunk_end = log_info.get("chunk_end_page", "unknown")
                    chunk_msg = f"Income statement found {direction_text} balance sheet: chunk {chunk_index} (pages {chunk_start}-{chunk_end})"
                    print(chunk_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.INCOME_STATEMENT,
                        chunk_msg,
                    )
                    pages_msg = f"Found income statement section (pages {log_info['start_extract_page']}-{log_info['end_extract_page']})"
                    print(pages_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.INCOME_STATEMENT,
                        pages_msg,
                    )
                found_msg = f"Found income statement section starting at page {start_page}, extracted {len(income_statement_text)} characters"
                print(found_msg)
                add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, found_msg)

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

            is_complete = check_income_statement_completeness_llm(
                income_statement_text, time_period
            )

            if not is_complete:
                section_failed_msg = "Stage 1 validation failed: LLM determined chunk does not contain complete income statement"
                print(section_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    section_failed_msg,
                )
                if section_attempt < max_retries - 1:
                    continue  # Try next chunk position
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
                        "Income statement completeness check failed"
                    ]
                    # Note: chunk_index not set here since Stage 1 validation failed
                    return extracted_data

            # Extract income statement using LLM (only if chunk is complete)
            extraction_msg = "Extracting income statement from complete chunk"
            print(extraction_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                extraction_msg,
            )

            extracted_data = extract_income_statement_llm(income_statement_text, time_period)
            extracted_count_msg = (
                f"Extracted {len(extracted_data.get('line_items', []))} line items"
            )
            print(extracted_count_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                extracted_count_msg,
            )

            section_valid_msg = (
                "Stage 1 validation passed (complete income statement chunk found and extracted)"
            )
            print(section_valid_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                section_valid_msg,
            )
            # Store successful chunk index
            if log_info:
                successful_chunk_index = log_info.get("income_statement_chunk_index")
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

    if not income_statement_text or extracted_data is None:
        raise Exception("Failed to find income statement section after all attempts")

    # Stage 2: Post-process and validate extraction (retry extraction with LLM feedback)
    EXTRACTION_MAX_RETRIES = 3
    normalization_errors = []

    for extraction_attempt in range(EXTRACTION_MAX_RETRIES):
        try:
            if extraction_attempt == 0:
                # First attempt: post-process initial extraction from Stage 1
                extraction_msg = "Stage 2: Post-processing and validating extraction"
                print(extraction_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    extraction_msg,
                )
                # extracted_data is already set from Stage 1
            else:
                # Retry with feedback from previous attempt
                retry_msg = f"Stage 2: Retry extraction {extraction_attempt + 1}/{EXTRACTION_MAX_RETRIES} with LLM feedback"
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
                    normalization_errors,  # Validation errors with differences from previous attempt
                )
            # Post-process line items (rename key items, normalize cost format)
            # This performs validation during normalization using final_diff logic
            processed_line_items, normalization_errors = post_process_income_statement_line_items(
                extracted_data.get("line_items", [])
            )
            extracted_data["line_items"] = processed_line_items

            # Stage 2 validation: Check if post-processing validation passed
            if len(normalization_errors) == 0:
                calc_valid_msg = (
                    "Stage 2 validation passed (post-processing calculations are correct)"
                )
                print(calc_valid_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    calc_valid_msg,
                )
                # Both stages passed, classify and return
                classified_items = classify_line_items_llm(extracted_data["line_items"])
                extracted_data["line_items"] = classified_items
                extracted_data["is_valid"] = True
                extracted_data["validation_errors"] = []

                # Calculate revenue growth YoY
                def normalize_value(value: object) -> float | None:
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

                current_revenue = None
                for item in extracted_data.get("line_items", []):
                    item_name_lower = item.get("line_name", "").lower()
                    if "total net revenue" in item_name_lower:
                        current_revenue = normalize_value(item.get("line_value"))
                        if current_revenue is not None:
                            break

                if (
                    current_revenue is not None
                    and extracted_data.get("revenue_prior_year") is not None
                ):
                    prior_revenue = extracted_data["revenue_prior_year"]
                    if prior_revenue > 0:
                        revenue_growth = ((current_revenue - prior_revenue) / prior_revenue) * 100
                        extracted_data["revenue_growth_yoy"] = revenue_growth

                # Store chunk index for persistence
                if successful_chunk_index is not None:
                    extracted_data["chunk_index"] = successful_chunk_index

                return extracted_data
            else:
                calc_failed_msg = (
                    f"Stage 2 validation failed: {', '.join(normalization_errors[:2])}"
                )
                print(calc_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    calc_failed_msg,
                )
                if extraction_attempt < EXTRACTION_MAX_RETRIES - 1:
                    continue  # Retry with feedback
                else:
                    # All extraction attempts failed, return with errors
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = normalization_errors

                    # Still calculate revenue growth if possible
                    def normalize_value(value: object) -> float | None:
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

                    current_revenue = None
                    for item in extracted_data.get("line_items", []):
                        item_name_lower = item.get("line_name", "").lower()
                        if "total net revenue" in item_name_lower:
                            current_revenue = normalize_value(item.get("line_value"))
                            if current_revenue is not None:
                                break

                    if (
                        current_revenue is not None
                        and extracted_data.get("revenue_prior_year") is not None
                    ):
                        prior_revenue = extracted_data["revenue_prior_year"]
                        if prior_revenue > 0:
                            revenue_growth = (
                                (current_revenue - prior_revenue) / prior_revenue
                            ) * 100
                            extracted_data["revenue_growth_yoy"] = revenue_growth

                    # Store chunk index for persistence (even if validation failed)
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

    raise Exception("Failed to extract income statement after all attempts")

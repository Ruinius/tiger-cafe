"""
Income statement extraction agent using Gemini LLM and embeddings
"""

import json

from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.pdf_extractor import extract_text_from_pdf


def find_income_statement_section(
    document_id: str, file_path: str, time_period: str
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embedding to locate the income statement section.
    May be called by various names (e.g., "consolidated statement of operations").

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")

    Returns:
        Tuple of (extracted_text, start_page, log_info) or (None, None, None) if not found
    """
    try:
        # Generate query embeddings for various income statement names
        query_texts = [
            "consolidated statement of operations",
            "income statement",
            "statement of operations",
            "consolidated income statement",
        ]
        result = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_size=None,
            score_threshold=0.3,
            pages_before=1,  # Include 1 page before the best chunk
            pages_after=1,  # Include 1 page after the best chunk
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
            "line_category": one of ["Recurring", "One-Time"] - categorize each line item based on whether it represents recurring business operations or one-time events
        }},
        ...
    ]
}}

IMPORTANT:
- Stop after the net income line item is extracted
- Extract values exactly as they appear (no rounding, include negative values if present)
- Include all line items, including but not limited to: Revenue, Cost of Revenue/Cost of Goods Sold, Gross Profit, Operating Expenses, Operating Income, Net Income, etc.
- Maintain the exact order of line items as they appear in the document
- Extract the currency code from the document if available
- Extract the unit from the document (look for notes like "in millions", "in thousands", "in billions", or "in ten thousands" for foreign stocks)
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue)
- Use "ten_thousands" only if the stock is foreign and the document explicitly states values are in ten thousands
- Categorize each line item as "Recurring" or "One-Time":
  - "Recurring": Normal business operations that occur regularly (e.g., Revenue, Cost of Revenue, Operating Expenses, Depreciation, Interest Expense, Taxes)
  - "One-Time": Unusual or infrequent items (e.g., Restructuring Charges, Impairment Charges, Gain/Loss on Sale of Assets, Legal Settlements, Acquisition Costs, Discontinued Operations)

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        response_text = generate_content_safe(prompt)

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
        raise Exception(f"Error extracting income statement: {str(e)}")


def find_additional_data_section(document_id: str, file_path: str, time_period: str) -> str | None:
    """
    Use document embedding to locate sections containing shares outstanding, diluted shares, and amortization.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")

    Returns:
        Extracted text containing the relevant sections, or None if not found
    """
    try:
        # Generate query embeddings for various search terms
        query_texts = [
            "shares outstanding",
            "diluted shares",
            "amortization",
            "weighted average number of shares",
            "common shares outstanding",
            "basic shares",
        ]

        result = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_size=None,
            score_threshold=0.3,
            pages_before=0,  # Include 0 pages before the best chunk
            pages_after=0,  # Include 0 pages after the best chunk
        )

        # Handle both old (2-tuple) and new (3-tuple) return formats for backward compatibility
        if len(result) == 2:
            extracted_text = result[0]
        else:
            extracted_text = result[0]

        return extracted_text

    except Exception as e:
        print(f"Error finding additional data section: {str(e)}")
        return None


def extract_additional_data_llm(text: str, time_period: str) -> dict:
    """
    Extract additional data: total shares outstanding, diluted shares outstanding, and amortization.

    Args:
        text: Document text
        time_period: Time period (e.g., "Q3 2023")

    Returns:
        Dictionary with additional data
    """
    prompt = f"""Extract the following financial data from the document for the time period: {time_period}:

1. Basic shares outstanding (basic weighted average shares outstanding, common shares outstanding)
2. Diluted shares outstanding (diluted weighted average shares)
3. Amortization (amortization expense)

Return a JSON object with the following structure:
{{
    "basic_shares_outstanding": number (as number, not string, null if not found),
    "basic_shares_outstanding_unit": unit for basic_shares_outstanding - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually "ones", null if basic_shares_outstanding is null),
    "diluted_shares_outstanding": number (as number, not string, null if not found),
    "diluted_shares_outstanding_unit": unit for diluted_shares_outstanding - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually "ones", null if diluted_shares_outstanding is null),
    "amortization": number (as number, not string, null if not found),
    "amortization_unit": unit for amortization - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as income statement unit, null if amortization is null)
}}

IMPORTANT:
- Extract values exactly as they appear
- Values should be numeric (not strings with commas)
- If a value is not found, use null
- Look for these values in the income statement, notes, or financial highlights sections
- Extract units from the document (shares are usually in "ones", amortization usually matches the income statement unit)
- Use "ten_thousands" only if the stock is foreign and the document explicitly states values are in ten thousands

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        response_text = generate_content_safe(prompt)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        return result

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting additional data: {str(e)}")


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

    if not line_items:
        return {}, []

    line_items_text = "\n".join(
        [
            f"{idx + 1}. {item['line_name']} | {item['line_value']}"
            for idx, item in enumerate(line_items)
        ]
    )

    prompt = f"""You are analyzing an income statement. Identify key line items by name.
Return ONLY valid JSON using the exact line names provided.

Line items:
{line_items_text}

Return this JSON structure:
{{
    "total_net_revenue_line": "exact line name for total net revenue (or null if not found)",
    "gross_profit_line": "exact line name for gross profit (or null if not found)",
    "operating_income_line": "exact line name for operating income (or null if not found)",
    "pretax_income_line": "exact line name for income before taxes (or null if not found)",
    "tax_expense_line": "exact line name for tax expense (or null if not found)",
    "net_income_line": "exact line name for net income (or null if not found)"
}}

Guidance:
- Total net revenue may be labeled as: Revenue, Total Revenue, Net Sales, Net Revenue, Total Net Revenue
- Gross profit may be labeled as: Gross Profit, Gross Margin, Gross Income
- Operating income may be labeled as: Operating Income, Income from Operations, Operating Profit, Operating Earnings
- Pretax income may be labeled as: Income Before Tax, Earnings Before Income Tax, Profit Before Tax, Income Before Income Tax Expense
- Tax expense may include: Income Tax Expense, Provision for Income Taxes, Income Taxes, Taxes
- Net income may be labeled as: Net Income, Net Earnings, Profit After Tax, After Tax Profit

Return only JSON with no extra text."""

    try:
        response_text = generate_content_safe(prompt)
        insights = _parse_llm_json_response(response_text)

        return (
            {
                "total_net_revenue_line": insights.get("total_net_revenue_line"),
                "gross_profit_line": insights.get("gross_profit_line"),
                "operating_income_line": insights.get("operating_income_line"),
                "pretax_income_line": insights.get("pretax_income_line"),
                "tax_expense_line": insights.get("tax_expense_line"),
                "net_income_line": insights.get("net_income_line"),
            },
            [],
        )
    except Exception as exc:
        return {}, [f"LLM insights unavailable: {str(exc)}"]


def _normalize_line_name(line_name: str) -> str:
    """Normalize line name for matching."""
    import re

    return re.sub(r"[^a-z0-9]+", " ", line_name.lower()).strip()


def _match_line_item(line_items: list[dict], target_name: str | None) -> dict | None:
    """Find matching line item by name."""
    from difflib import SequenceMatcher

    if not target_name:
        return None

    normalized_target = _normalize_line_name(target_name)
    best_item = None
    best_ratio = 0.0

    for item in line_items:
        normalized_item = _normalize_line_name(item.get("line_name", ""))
        if normalized_item == normalized_target:
            return item

        ratio = SequenceMatcher(None, normalized_item, normalized_target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_item = item

    if best_ratio >= 0.75:
        return best_item

    return None


def post_process_income_statement_line_items(line_items: list[dict]) -> list[dict]:
    """
    Post-process income statement line items:
    1. Use LLM to identify key line items
    2. Rename identified items with standardized names (original in parentheses)
    3. Detect cost format (positive vs negative) and normalize to positive costs
    """
    if not line_items:
        return line_items

    # Step 1: Get LLM insights to identify key line items
    llm_insights, _ = get_income_statement_llm_insights(line_items=line_items)

    # Mapping of standardized names to LLM insight keys
    standard_names = {
        "total_net_revenue_line": "Total Net Revenue",
        "gross_profit_line": "Gross Profit",
        "operating_income_line": "Operating Income",
        "pretax_income_line": "Pretax Income",
        "tax_expense_line": "Tax Expense",
        "net_income_line": "Net Income",
    }

    # Step 2: Rename identified line items
    processed_items = []
    renamed_indices = set()

    for item in line_items:
        item_copy = item.copy()

        # Check if this item matches any of the identified key items
        for insight_key, standard_name in standard_names.items():
            llm_line_name = llm_insights.get(insight_key)
            if llm_line_name and _match_line_item([item], llm_line_name):
                # Rename: "Standard Name (Original Name)"
                original_name = item_copy.get("line_name", "")
                item_copy["line_name"] = f"{standard_name} ({original_name})"
                renamed_indices.add(len(processed_items))
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

    def normalize_items_between(start_item, end_item, description):
        """Normalize items between two line items by detecting if they should be flipped."""
        if not start_item or not end_item:
            return

        start_idx = start_item[0]
        end_idx = end_item[0]

        if start_idx >= end_idx:
            return

        items_between = processed_items[start_idx + 1 : end_idx]
        if not items_between:
            return

        # Calculate sums to test both formats
        sum_between_raw = sum(item.get("line_value", 0) for item in items_between)
        sum_between_abs = sum(abs(item.get("line_value", 0)) for item in items_between)
        start_value = start_item[1].get("line_value", 0)
        end_value = end_item[1].get("line_value", 0)

        # Test which formula matches: start + items = end (negative costs) or start - items = end (positive costs)
        # When costs are negative: Revenue + (negative sum) = Operating Income ✓ (desired format)
        # When costs are positive: Revenue - (positive sum) = Operating Income (needs flipping)
        diff_with_negative = abs((start_value + sum_between_raw) - end_value)
        diff_with_positive = abs((start_value - sum_between_abs) - end_value)

        # Count negative vs positive items to help decide when there's a tie
        negative_count = sum(1 for item in items_between if item.get("line_value", 0) < 0)
        positive_count = sum(1 for item in items_between if item.get("line_value", 0) > 0)
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
            for item in items_between:
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

    # Normalize items between revenue and gross profit
    if revenue_item and gross_profit_item:
        normalize_items_between(revenue_item, gross_profit_item, "costs")

    # Normalize items between gross profit and operating income
    if gross_profit_item and operating_income_item:
        normalize_items_between(gross_profit_item, operating_income_item, "operating expenses")

    # Normalize items between operating income and pretax income
    if operating_income_item and pretax_income_item:
        normalize_items_between(operating_income_item, pretax_income_item, "non-operating items")

    # Handle missing gross profit: check between revenue and operating income or pretax income
    if revenue_item and not gross_profit_item:
        print(
            "Gross profit missing, normalizing between Revenue and Operating Income/Pretax Income"
        )
        if operating_income_item:
            normalize_items_between(revenue_item, operating_income_item, "costs and expenses")
        elif pretax_income_item:
            normalize_items_between(revenue_item, pretax_income_item, "costs and expenses")

    # Handle missing operating income: check between revenue/gross profit and pretax income
    if not operating_income_item and pretax_income_item:
        print(
            "Operating income missing, normalizing between Revenue/Gross Profit and Pretax Income"
        )
        if gross_profit_item:
            normalize_items_between(
                gross_profit_item, pretax_income_item, "operating and non-operating items"
            )
        elif revenue_item:
            normalize_items_between(revenue_item, pretax_income_item, "all expenses")

    return processed_items


def validate_income_statement(
    line_items: list[dict], revenue: float | None = None
) -> tuple[bool, list[str]]:
    """
    Validate income statement calculations.

    Args:
        line_items: List of income statement line items
        revenue: Revenue value (if available)

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

    # Find key values - prioritize standardized names first
    revenue_value = None
    cost_of_revenue = None
    gross_profit = None
    operating_expenses = None
    operating_income = None
    net_income = None

    # First pass: Look for standardized names (e.g., "Total Net Revenue (Revenue)")
    for item in line_items:
        item_name_lower = item["line_name"].lower()
        item_value = item["line_value"]

        if "total net revenue (" in item_name_lower:
            revenue_value = item_value
        elif "gross profit (" in item_name_lower:
            gross_profit = item_value
        elif "operating income (" in item_name_lower:
            operating_income = item_value
        elif "net income (" in item_name_lower and "per share" not in item_name_lower:
            net_income = item_value

    # Second pass: Look for cost of revenue and operating expenses (may not be standardized)
    # Also look for revenue if not found with standardized name
    items_dict = {item["line_name"].lower(): item["line_value"] for item in line_items}

    if revenue_value is None:
        for key, value in items_dict.items():
            if "total net revenue" in key or ("revenue" in key and "total" in key):
                revenue_value = value
                break
            elif "revenue" in key and "total" not in key and "net" not in key:
                if revenue_value is None:
                    revenue_value = value

    # Look for cost of revenue
    for key, value in items_dict.items():
        if (
            "cost of revenue" in key or "cost of goods sold" in key or "cogs" in key
        ) and "total" not in key:
            cost_of_revenue = value
            break

    # Look for operating expenses
    for key, value in items_dict.items():
        if (
            "operating expenses" in key or "total operating expenses" in key
        ) and "income" not in key:
            operating_expenses = value
            break

    # Use provided revenue if available (override any found value)
    if revenue is not None:
        revenue_value = revenue

    # Validate gross profit: Revenue + Cost of Revenue = Gross Profit (costs are negative)
    # Note: Cost of Revenue should be negative after normalization (costs are normalized to negative)
    if revenue_value is not None and gross_profit is not None:
        if cost_of_revenue is not None:
            # Cost of revenue is now normalized to negative, so add it (subtracting absolute value)
            calculated_gross_profit = revenue_value + cost_of_revenue  # cost_of_revenue is negative
            diff = abs(gross_profit - calculated_gross_profit)
            if diff > 0.01:
                errors.append(
                    f"Gross profit calculation mismatch: reported={gross_profit}, calculated (Revenue + Cost of Revenue)={calculated_gross_profit}"
                )
        # If cost_of_revenue is None, we can't validate gross profit, but that's okay

    # Validate operating income: Gross Profit + Operating Expenses = Operating Income (expenses are negative)
    # Note: Operating Expenses should be negative after normalization (costs are normalized to negative)
    if gross_profit is not None and operating_income is not None:
        if operating_expenses is not None:
            # Operating expenses are now normalized to negative, so add them
            calculated_operating_income = (
                gross_profit + operating_expenses
            )  # operating_expenses is negative
            diff = abs(operating_income - calculated_operating_income)
            if diff > 0.01:
                errors.append(
                    f"Operating income calculation mismatch: reported={operating_income}, calculated (Gross Profit + Operating Expenses)={calculated_operating_income}"
                )
        # If operating_expenses is None, we can't validate operating income, but that's okay

    # Validate net income (if we can calculate it)
    # Net Income = Operating Income - Other Expenses + Other Income - Taxes
    # This is more complex, so we'll just check if net income exists
    if net_income is None:
        # Try to find it with standardized name first
        for item in line_items:
            item_name_lower = item["line_name"].lower()
            if "net income (" in item_name_lower and "per share" not in item_name_lower:
                net_income = item["line_value"]
                break

        # Fallback to alternative names
        if net_income is None:
            for key, value in items_dict.items():
                if ("net income" in key or "net earnings" in key) and "per share" not in key:
                    net_income = value
                    break

    # Check if we have at least one key income statement item (revenue, gross profit, operating income, or net income)
    # This ensures we didn't get an empty or invalid income statement
    if (
        revenue_value is None
        and gross_profit is None
        and operating_income is None
        and net_income is None
    ):
        errors.append(
            "Income statement is missing key items (Revenue, Gross Profit, Operating Income, or Net Income)"
        )

    return len(errors) == 0, errors


def classify_line_items_llm(line_items: list[dict]) -> list[dict]:
    """
    Use LLM to categorize each income statement line item as operating or non-operating.

    Args:
        line_items: List of income statement line items

    Returns:
        List of line items with is_operating classification added
    """
    # Prepare context for LLM
    items_text = "\n".join([f"- {item['line_name']}" for item in line_items])

    prompt = f"""Classify each income statement line item as operating or non-operating, and as recurring or one-time.

Operating items are related to the core business operations:
- Revenue, Cost of Revenue, Operating Expenses, Operating Income
- Sales, Marketing, R&D, General & Administrative expenses
- Sales tax, income tax, property tax
- Items that are part of normal business operations

Non-operating items are not part of core operations:
- Interest income/expense
- Foreign exchange gains/losses
- Investment gains/losses
- Restructuring charges
- Impairment charges
- Write-offs
- Gains/losses on sale of assets
- Amortization of intangible assets, because intangibles generally arise from acquisitions
- One-time items

Recurring items are normal business operations that occur regularly:
- Revenue, Cost of Revenue, Operating Expenses, Depreciation, Interest Expense, Taxes
- Regular business operations that happen every period

One-time items are unusual or infrequent events:
- Restructuring Charges, Impairment Charges, Gain/Loss on Sale of Assets
- Legal Settlements, Acquisition Costs, Discontinued Operations
- Other unusual gains or losses that are not expected to recur

Line items:
{items_text}

Return a JSON object with the following structure:
{{
    "classifications": [
        {{
            "line_name": "exact line name as provided",
            "is_operating": true or false,
            "line_category": "Recurring" or "One-Time"
        }},
        ...
    ]
}}

Return only valid JSON, no additional text."""

    try:
        response_text = generate_content_safe(prompt)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        classifications = {
            item["line_name"]: {
                "is_operating": item.get("is_operating"),
                "line_category": item.get(
                    "line_category", "Recurring"
                ),  # Default to Recurring if not specified
            }
            for item in result.get("classifications", [])
        }

        # Add classifications to line items
        classified_items = []
        for item in line_items:
            item_copy = item.copy()
            classification = classifications.get(item["line_name"], {})
            item_copy["is_operating"] = classification.get("is_operating", None)
            # Preserve line_category from extraction if available, otherwise use classification
            if "line_category" not in item_copy or not item_copy.get("line_category"):
                item_copy["line_category"] = classification.get("line_category", "Recurring")
            classified_items.append(item_copy)

        return classified_items

    except Exception as e:
        print(f"Error classifying income statement line items: {str(e)}")
        # Return items without classification if classification fails
        return line_items


def extract_income_statement(
    document_id: str, file_path: str, time_period: str, max_retries: int = 3
) -> dict:
    """
    Main function to extract income statement with validation and retries.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with income statement data and validation status
    """
    for attempt in range(max_retries):
        try:
            attempt_msg = f"Income statement extraction attempt {attempt + 1}/{max_retries}"
            print(attempt_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT, attempt_msg
            )

            # Step 1: Find income statement section using embeddings
            income_statement_text, start_page, log_info = find_income_statement_section(
                document_id, file_path, time_period
            )

            if not income_statement_text:
                # Fallback: extract full document if embedding search fails
                fallback_msg = "Embedding search failed, extracting full document..."
                print(fallback_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
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
                    FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                    extracted_msg,
                )
            else:
                # Log chunk/page information if available
                if log_info:
                    chunk_msg = f"Best match: chunk {log_info['best_chunk_index']} (pages {log_info['chunk_start_page']}-{log_info['chunk_end_page']})"
                    print(chunk_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                        chunk_msg,
                    )
                    pages_msg = f"Found income statement section (pages {log_info['start_extract_page']}-{log_info['end_extract_page']})"
                    print(pages_msg)
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                        pages_msg,
                    )
                found_msg = f"Found income statement section starting at page {start_page}, extracted {len(income_statement_text)} characters"
                print(found_msg)
                add_log(
                    document_id, FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT, found_msg
                )

            # Step 2: Extract income statement using LLM
            extracted_data = extract_income_statement_llm(income_statement_text, time_period)
            extracted_count_msg = (
                f"Extracted {len(extracted_data.get('line_items', []))} line items"
            )
            print(extracted_count_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                extracted_count_msg,
            )

            # Step 3: Find and extract additional data (shares outstanding, amortization) using embedding search
            additional_data_msg = (
                "Searching for additional data (shares outstanding, amortization)..."
            )
            print(additional_data_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                additional_data_msg,
            )

            additional_data_text = find_additional_data_section(document_id, file_path, time_period)
            if additional_data_text:
                found_additional_msg = f"Found additional data section, extracted {len(additional_data_text)} characters"
                print(found_additional_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    found_additional_msg,
                )
                additional_data = extract_additional_data_llm(additional_data_text, time_period)
            else:
                # Fallback: try with income statement text if embedding search fails
                fallback_additional_msg = (
                    "Embedding search for additional data failed, trying with income statement text"
                )
                print(fallback_additional_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    fallback_additional_msg,
                )
                additional_data = extract_additional_data_llm(income_statement_text, time_period)
            extracted_data.update(additional_data)
            additional_complete_msg = "Additional data extraction completed"
            print(additional_complete_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                additional_complete_msg,
            )

            # Step 4.5: Post-process line items (rename key items, normalize cost format)
            # Do this BEFORE validation so validation can use standardized names
            extracted_data["line_items"] = post_process_income_statement_line_items(
                extracted_data.get("line_items", [])
            )

            # Step 4: Validate (after post-processing)
            extracted_data.get("revenue_prior_year")  # Use revenue from extraction
            # Find current revenue from line items (use standardized name if available)
            current_revenue = None
            for item in extracted_data.get("line_items", []):
                item_name_lower = item.get("line_name", "").lower()
                if "total net revenue (" in item_name_lower:
                    current_revenue = item.get("line_value")
                    break

            # Fallback to non-standardized name
            if current_revenue is None:
                for item in extracted_data.get("line_items", []):
                    if (
                        "revenue" in item.get("line_name", "").lower()
                        and "total" not in item.get("line_name", "").lower()
                    ):
                        current_revenue = item.get("line_value")
                        break

            is_valid, errors = validate_income_statement(
                extracted_data.get("line_items", []), current_revenue
            )

            if is_valid:
                validation_msg = "Validation passed"
                print(validation_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                    validation_msg,
                )
                # Step 5: Classify line items
                classified_items = classify_line_items_llm(extracted_data["line_items"])
                extracted_data["line_items"] = classified_items
                extracted_data["is_valid"] = True
                extracted_data["validation_errors"] = []

                # Calculate revenue growth YoY
                if (
                    current_revenue is not None
                    and extracted_data.get("revenue_prior_year") is not None
                ):
                    prior_revenue = extracted_data["revenue_prior_year"]
                    if prior_revenue > 0:
                        revenue_growth = ((current_revenue - prior_revenue) / prior_revenue) * 100
                        extracted_data["revenue_growth_yoy"] = revenue_growth

                return extracted_data
            else:
                validation_failed_msg = (
                    f"Validation failed: {', '.join(errors[:3])}"  # Show first 3 errors
                )
                print(validation_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                    validation_failed_msg,
                )
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    # Post-process line items even if validation failed
                    extracted_data["line_items"] = post_process_income_statement_line_items(
                        extracted_data.get("line_items", [])
                    )
                    # Return with errors on final attempt
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = errors

                    # Still calculate revenue growth if possible
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

                    return extracted_data

        except Exception as e:
            error_str = str(e).lower()
            # Check if it's an API error that was already retried at the API level
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

            # If it's an API error that failed after 3 retries, don't retry at agent level
            # (it's likely a persistent issue, not transient)
            if is_api_error:
                print(f"API error after retries on attempt {attempt + 1}: {str(e)}")
                raise  # Don't retry - API-level already tried 3 times

            # For other errors (validation, extraction issues), retry makes sense
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise

    raise Exception(f"Failed to extract income statement after {max_retries} attempts")

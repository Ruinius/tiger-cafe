"""
Historical calculations utility for computing financial metrics
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from typing import Any

from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem


def _normalize_line_name(line_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", line_name.lower()).strip()


def _match_line_item(
    line_items: list[IncomeStatementLineItem], target_name: str | None
) -> IncomeStatementLineItem | None:
    if not target_name:
        return None

    normalized_target = _normalize_line_name(target_name)
    best_item = None
    best_ratio = 0.0

    for item in line_items:
        normalized_item = _normalize_line_name(item.line_name)
        if normalized_item == normalized_target:
            return item

        ratio = SequenceMatcher(None, normalized_item, normalized_target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_item = item

    if best_ratio >= 0.75:
        return best_item

    return None


def calculate_net_working_capital(balance_sheet: BalanceSheet) -> Decimal | None:
    """
    Calculate net working capital by summing all Current Assets labeled as Operating
    and subtracting the sum of all Current Liabilities labeled as Operating.
    """
    if not balance_sheet or not balance_sheet.line_items:
        return None

    current_assets_operating = Decimal("0")
    current_liabilities_operating = Decimal("0")

    for item in balance_sheet.line_items:
        # Check if it's a current asset
        if (
            item.line_category
            and "current" in item.line_category.lower()
            and "asset" in item.line_category.lower()
        ):
            if item.is_operating:
                current_assets_operating += item.line_value

        # Check if it's a current liability
        elif (
            item.line_category
            and "current" in item.line_category.lower()
            and "liability" in item.line_category.lower()
        ):
            if item.is_operating:
                current_liabilities_operating += item.line_value

    net_working_capital = current_assets_operating - current_liabilities_operating
    return net_working_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_net_long_term_operating_assets(balance_sheet: BalanceSheet) -> Decimal | None:
    """
    Calculate net long term operating assets by summing all Non-current Assets labeled as Operating
    and subtracting the sum of all Non-current Liabilities labeled as Operating.
    """
    if not balance_sheet or not balance_sheet.line_items:
        return None

    non_current_assets_operating = Decimal("0")
    non_current_liabilities_operating = Decimal("0")

    for item in balance_sheet.line_items:
        # Check if it's a non-current asset (exclude totals)
        category_lower = item.line_category.lower() if item.line_category else ""
        if "non-current" in category_lower or (
            "long" in category_lower and "term" in category_lower
        ):
            if "asset" in category_lower and item.is_operating and "total" not in category_lower:
                non_current_assets_operating += item.line_value
            elif (
                "liability" in category_lower
                and item.is_operating
                and "total" not in category_lower
            ):
                non_current_liabilities_operating += item.line_value

    net_long_term = non_current_assets_operating - non_current_liabilities_operating
    return net_long_term.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_invested_capital(
    net_working_capital: Decimal | None, net_long_term: Decimal | None
) -> Decimal | None:
    """
    Calculate invested capital by adding net working capital and net long term operating assets.
    """
    if net_working_capital is None or net_long_term is None:
        return None

    invested_capital = net_working_capital + net_long_term
    return invested_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_capital_turnover(
    revenue: Decimal | None, invested_capital: Decimal | None, time_period: str | None = None
) -> Decimal | None:
    """
    Calculate capital turnover by dividing revenue by invested capital.
    If the time period is quarterly (Q1, Q2, Q3, Q4), annualize the revenue by multiplying by 4.
    """
    if revenue is None or invested_capital is None or invested_capital == 0:
        return None

    # Check if time_period is quarterly (Q1, Q2, Q3, Q4) vs fiscal year (FY)
    annualized_revenue = revenue
    if time_period:
        time_period_upper = time_period.upper().strip()
        # Check if it's quarterly: starts with Q followed by a digit (Q1, Q2, Q3, Q4)
        # or contains Q1/Q2/Q3/Q4 as a pattern (e.g., "2024-Q1")
        is_quarterly = (
            bool(re.match(r"^Q[1-4]\s", time_period_upper))  # "Q1 2023", "Q2 2024", etc.
            or bool(re.match(r"^Q[1-4]$", time_period_upper))  # "Q1", "Q2", etc.
            or bool(re.search(r"[Q][1-4][\s-]?", time_period_upper))  # "2024-Q1", "2024 Q2", etc.
        )
        if is_quarterly and not time_period_upper.startswith("FY"):
            # Annualize quarterly revenue by multiplying by 4
            annualized_revenue = revenue * Decimal("4")

    turnover = annualized_revenue / invested_capital
    return turnover.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def get_revenue_line_item(
    income_statement: IncomeStatement,
) -> IncomeStatementLineItem | None:
    """
    Extract the revenue line item from the income statement.
    Uses standardized name "Total Net Revenue" if available.
    """
    if not income_statement or not income_statement.line_items:
        return None

    # First, try to find standardized "Total Net Revenue" name
    for item in income_statement.line_items:
        if "Total Net Revenue" in item.line_name and item.line_value > 0:
            return item

    # Fallback to original logic
    for item in income_statement.line_items:
        name_lower = item.line_name.lower()
        category_lower = item.line_category.lower() if item.line_category else ""

        if (
            "revenue" in name_lower
            or "revenue" in category_lower
            or "sales" in name_lower
            or "net sales" in name_lower
        ):
            if item.line_value > 0:
                return item

    return None


def get_revenue(income_statement: IncomeStatement) -> Decimal | None:
    """
    Extract revenue from income statement line items.
    """
    revenue_item = get_revenue_line_item(income_statement)
    return revenue_item.line_value if revenue_item else None


def get_operating_income(
    income_statement: IncomeStatement, llm_insights: dict[str, Any] | None = None
) -> Decimal | None:
    """
    Extract operating income from income statement line items.
    Uses standardized name "Operating Income" if available.
    """
    if not income_statement or not income_statement.line_items:
        return None

    # First, try to find standardized "Operating Income" name
    for item in income_statement.line_items:
        if "Operating Income (" in item.line_name:
            return item.line_value

    # Fallback to LLM insights if available
    if llm_insights:
        llm_line = llm_insights.get("operating_income_line")
        matched_item = _match_line_item(income_statement.line_items, llm_line)
        if matched_item:
            return matched_item.line_value

    # Fallback to original logic
    for item in income_statement.line_items:
        name_lower = item.line_name.lower()

        if any(
            term in name_lower
            for term in [
                "operating income",
                "income from operations",
                "operating profit",
                "operating earnings",
                "operating result",
            ]
        ):
            if "total" not in name_lower and "subtotal" not in name_lower:
                return item.line_value

    return None


def get_non_operating_line_items(
    income_statement: IncomeStatement,
) -> list[IncomeStatementLineItem]:
    """
    Identify non-operating line items using persisted classification.
    """
    if not income_statement or not income_statement.line_items:
        return []

    return [item for item in income_statement.line_items if item.is_operating is False]


def get_non_operating_items_between_revenue_and_operating_income(
    income_statement: IncomeStatement, llm_insights: dict[str, Any] | None = None
) -> Decimal:
    """
    Get sum of all non-operating items between Revenue and Operating Income.
    These need to be subtracted from Operating Income to get EBITA.
    Uses standardized names if available.
    Note: llm_insights parameter is kept for backward compatibility but no longer used.
    """
    if not income_statement or not income_statement.line_items:
        return Decimal("0")

    sorted_items = sorted(income_statement.line_items, key=lambda x: x.line_order)

    # Find revenue item (prefer standardized name)
    revenue_item = get_revenue_line_item(income_statement)

    # Find operating income item (prefer standardized name)
    operating_item = None
    for item in sorted_items:
        if "Operating Income (" in item.line_name:
            operating_item = item
            break

    # Fallback to search
    if not operating_item:
        for item in sorted_items:
            name_lower = item.line_name.lower()
            if any(
                term in name_lower
                for term in ["operating income", "income from operations", "operating profit"]
            ):
                operating_item = item
                break

    non_operating_candidates = get_non_operating_line_items(income_statement)
    candidate_names = {_normalize_line_name(item.line_name) for item in non_operating_candidates}

    non_operating_sum = Decimal("0")
    use_range = revenue_item and operating_item

    for item in sorted_items:
        if use_range:
            if not (revenue_item.line_order < item.line_order < operating_item.line_order):
                continue

        if candidate_names:
            if _normalize_line_name(item.line_name) not in candidate_names:
                continue
        elif item.is_operating is not False:
            continue

        non_operating_sum -= item.line_value

    if use_range or candidate_names:
        return non_operating_sum

    return Decimal("0")


def calculate_ebita(
    income_statement: IncomeStatement,
    amortization: Decimal | None = None,
    llm_insights: dict[str, Any] | None = None,
) -> Decimal | None:
    """
    Calculate EBITA by taking Operating Income, subtracting non-operating items
    between Revenue and Operating Income, and subtracting Amortization if available.
    """
    operating_income = get_operating_income(income_statement, llm_insights)
    if operating_income is None:
        return None

    # Add non-operating items between revenue and operating income
    non_operating_items = get_non_operating_items_between_revenue_and_operating_income(
        income_statement, llm_insights
    )
    ebita = operating_income + non_operating_items

    # Add amortization if available
    if amortization is not None:
        ebita = ebita + amortization

    return ebita.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_ebita_margin(ebita: Decimal | None, revenue: Decimal | None) -> Decimal | None:
    """
    Calculate EBITA margin by dividing EBITA by revenue.
    Returns as decimal (e.g., 0.15 for 15%).
    """
    if ebita is None or revenue is None or revenue == 0:
        return None

    margin = ebita / revenue
    return margin.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def extract_tax_inputs(
    income_statement: IncomeStatement, llm_insights: dict[str, Any] | None = None
) -> dict[str, Decimal | None]:
    """
    Extract pretax income, tax expense, and net income.
    Uses standardized names if available.
    Note: llm_insights parameter is kept for backward compatibility but no longer used.
    """
    if not income_statement or not income_statement.line_items:
        return {"income_before_taxes": None, "income_tax_expense": None, "net_income": None}

    income_before_taxes = None
    income_tax_expense = None
    net_income = None
    provision_for_income_taxes = None

    # First, try to find standardized names
    for item in income_statement.line_items:
        item_name = item.line_name
        if "Pretax Income (" in item_name:
            income_before_taxes = item.line_value
        elif "Tax Expense (" in item_name:
            income_tax_expense = abs(item.line_value)
        elif "Net Income (" in item_name:
            net_income = item.line_value

    # Fallback to original logic
    for item in income_statement.line_items:
        name_lower = item.line_name.lower()

        if income_before_taxes is None and any(
            term in name_lower
            for term in [
                "income before tax",
                "earnings before income tax",
                "profit before tax",
                "pre-tax income",
                "income before income tax expense",
            ]
        ):
            income_before_taxes = item.line_value

        if income_tax_expense is None and any(
            term in name_lower
            for term in ["income tax expense", "income taxes", "provision for income taxes"]
        ):
            if "provision" in name_lower:
                provision_for_income_taxes = abs(item.line_value)
            else:
                income_tax_expense = abs(item.line_value)

        if net_income is None and any(
            term in name_lower
            for term in ["net income", "net earnings", "profit after tax", "after tax profit"]
        ):
            if "total" not in name_lower:
                net_income = item.line_value

    if income_tax_expense is None and provision_for_income_taxes is not None:
        income_tax_expense = provision_for_income_taxes

    return {
        "income_before_taxes": income_before_taxes,
        "income_tax_expense": income_tax_expense,
        "net_income": net_income,
    }


def calculate_effective_tax_rate_from_inputs(
    income_before_taxes: Decimal | None,
    income_tax_expense: Decimal | None,
    net_income: Decimal | None,
) -> Decimal | None:
    """
    Calculate effective tax rate using provided inputs.
    Returns as decimal (e.g., 0.25 for 25%).
    """
    if income_before_taxes and income_before_taxes != 0:
        if income_tax_expense is not None:
            tax_rate = income_tax_expense / abs(income_before_taxes)
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        if net_income is not None:
            taxes_paid = abs(income_before_taxes) - abs(net_income)
            if taxes_paid > 0:
                tax_rate = taxes_paid / abs(income_before_taxes)
                return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return None


def calculate_adjusted_tax_rate(
    effective_tax_rate: Decimal | None,
    income_before_taxes: Decimal | None,
    income_tax_expense: Decimal | None,
    non_operating_items: list[IncomeStatementLineItem],
) -> Decimal | None:
    """
    Calculate an adjusted tax rate when effective tax rate is unusually high or low.
    """
    if (
        effective_tax_rate is None
        or income_before_taxes in (None, 0)
        or income_tax_expense is None
        or not non_operating_items
    ):
        return None

    if Decimal("0.10") <= effective_tax_rate <= Decimal("0.35"):
        return None

    if effective_tax_rate > Decimal("0.35"):
        adjustment = sum(item.line_value for item in non_operating_items if item.line_value < 0)
    else:
        adjustment = sum(item.line_value for item in non_operating_items if item.line_value > 0)

    if adjustment == 0:
        return None

    adjusted_pretax_income = income_before_taxes - adjustment
    if adjusted_pretax_income == 0:
        return None

    adjusted_rate = income_tax_expense / abs(adjusted_pretax_income)
    return adjusted_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_all_historical_metrics(
    balance_sheet: BalanceSheet, income_statement: IncomeStatement
) -> dict[str, Any]:
    """
    Calculate all historical financial metrics for a document.
    Returns a dictionary with all calculated values and any notes.
    Note: Line items should already be standardized during extraction, so no LLM calls are needed here.
    """
    notes = []

    # Get basic values
    revenue = get_revenue(income_statement)
    amortization = income_statement.amortization if income_statement else None

    # Calculate metrics
    net_working_capital = calculate_net_working_capital(balance_sheet)
    net_long_term = calculate_net_long_term_operating_assets(balance_sheet)
    invested_capital = calculate_invested_capital(net_working_capital, net_long_term)
    capital_turnover = calculate_capital_turnover(
        revenue, invested_capital, income_statement.time_period if income_statement else None
    )
    ebita = calculate_ebita(income_statement, amortization, None)
    ebita_margin = calculate_ebita_margin(ebita, revenue)

    tax_inputs = extract_tax_inputs(income_statement, None)
    effective_tax_rate = calculate_effective_tax_rate_from_inputs(
        tax_inputs.get("income_before_taxes"),
        tax_inputs.get("income_tax_expense"),
        tax_inputs.get("net_income"),
    )

    adjusted_tax_rate = calculate_adjusted_tax_rate(
        effective_tax_rate,
        tax_inputs.get("income_before_taxes"),
        tax_inputs.get("income_tax_expense"),
        get_non_operating_line_items(income_statement),
    )

    # Add notes for missing data
    if revenue is None:
        notes.append("Revenue not found in income statement")
    if amortization is None:
        notes.append("Amortization not available")
    if net_working_capital is None:
        notes.append(
            "Net working capital could not be calculated (missing operating current assets/liabilities)"
        )
    if net_long_term is None:
        notes.append("Net long term operating assets could not be calculated")
    if effective_tax_rate is None:
        notes.append("Effective tax rate could not be calculated")

    # Check for unusual tax rates (and record when adjusted)
    if effective_tax_rate:
        if effective_tax_rate > Decimal("0.35"):
            notes.append(
                f"Effective tax rate ({effective_tax_rate * 100:.1f}%) appears high (>35%)"
            )
        elif effective_tax_rate < Decimal("0.10"):
            notes.append(f"Effective tax rate ({effective_tax_rate * 100:.1f}%) appears low (<10%)")

    if adjusted_tax_rate is not None:
        notes.append(
            f"Adjusted tax rate calculated using non-operating items: {(adjusted_tax_rate * 100):.1f}%"
        )

    return {
        "net_working_capital": net_working_capital,
        "net_long_term_operating_assets": net_long_term,
        "invested_capital": invested_capital,
        "capital_turnover": capital_turnover,
        "ebita": ebita,
        "ebita_margin": ebita_margin,
        "effective_tax_rate": effective_tax_rate,
        "adjusted_tax_rate": adjusted_tax_rate,
        "calculation_notes": notes,
    }

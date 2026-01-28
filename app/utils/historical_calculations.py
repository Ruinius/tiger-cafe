"""
Historical calculations utility for computing financial metrics
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from typing import Any

from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
from app.utils.line_item_utils import normalize_line_name


def _match_line_item(
    line_items: list[IncomeStatementLineItem], target_name: str | None
) -> IncomeStatementLineItem | None:
    if not target_name:
        return None

    normalized_target = normalize_line_name(target_name)
    best_item = None
    best_ratio = 0.0

    for item in line_items:
        normalized_item = normalize_line_name(item.line_name)
        if normalized_item == normalized_target:
            return item

        ratio = SequenceMatcher(None, normalized_item, normalized_target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_item = item

    if best_ratio >= 0.75:
        return best_item

    return None


def calculate_net_working_capital(balance_sheet: BalanceSheet) -> dict[str, Any] | None:
    """
    Calculate net working capital by summing all Current Assets labeled as Operating
    and subtracting the sum of all Current Liabilities labeled as Operating.

    Returns a dictionary with:
    - total: The net working capital value
    - current_assets: List of current asset items used
    - current_liabilities: List of current liability items used
    - current_assets_total: Sum of current assets
    - current_liabilities_total: Sum of current liabilities
    """
    if not balance_sheet or not balance_sheet.line_items:
        return None

    current_assets_operating = Decimal("0")
    current_liabilities_operating = Decimal("0")
    current_assets_items = []
    current_liabilities_items = []

    for item in balance_sheet.line_items:
        # Skip calculated totals (use is_calculated field instead of name matching)
        if item.is_calculated is True:
            continue

        # Strict check for Current Assets/Liabilities using explicit category tokens
        if item.line_category == "current_assets":
            if item.is_operating is True:
                current_assets_operating += item.line_value
                current_assets_items.append({"name": item.line_name, "order": item.line_order})

        elif item.line_category == "current_liabilities":
            if item.is_operating is True:
                current_liabilities_operating += item.line_value
                current_liabilities_items.append({"name": item.line_name, "order": item.line_order})

    net_working_capital = current_assets_operating - current_liabilities_operating

    return {
        "total": float(net_working_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "current_assets": current_assets_items,
        "current_liabilities": current_liabilities_items,
        "current_assets_total": float(
            current_assets_operating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "current_liabilities_total": float(
            current_liabilities_operating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
    }


def calculate_net_long_term_operating_assets(balance_sheet: BalanceSheet) -> dict[str, Any] | None:
    """
    Calculate net long term operating assets by summing all Non-current Assets labeled as Operating
    and subtracting the sum of all Non-current Liabilities labeled as Operating.

    Returns a dictionary with:
    - total: The net long term operating assets value
    - non_current_assets: List of non-current asset items used (with order)
    - non_current_liabilities: List of non-current liability items used (with order)
    - non_current_assets_total: Sum of non-current assets
    - non_current_liabilities_total: Sum of non-current liabilities
    """
    if not balance_sheet or not balance_sheet.line_items:
        return None

    non_current_assets_operating = Decimal("0")
    non_current_liabilities_operating = Decimal("0")
    non_current_assets_items = []
    non_current_liabilities_items = []

    for item in balance_sheet.line_items:
        # Skip calculated totals (use is_calculated field instead of name matching)
        if item.is_calculated is True:
            continue

        # Strict check for Non-Current Assets/Liabilities using explicit category tokens
        # Note: Transformer output usually uses underscores (non_current_asserts) or joined words

        if item.line_category == "noncurrent_assets":
            if item.is_operating is True:
                non_current_assets_operating += item.line_value
                non_current_assets_items.append({"name": item.line_name, "order": item.line_order})

        elif item.line_category == "noncurrent_liabilities":
            if item.is_operating is True:
                non_current_liabilities_operating += item.line_value
                non_current_liabilities_items.append(
                    {"name": item.line_name, "order": item.line_order}
                )

    net_long_term = non_current_assets_operating - non_current_liabilities_operating

    return {
        "total": float(net_long_term.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "non_current_assets": non_current_assets_items,
        "non_current_liabilities": non_current_liabilities_items,
        "non_current_assets_total": float(
            non_current_assets_operating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "non_current_liabilities_total": float(
            non_current_liabilities_operating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
    }


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


def get_interest_expense(income_statement: IncomeStatement) -> Decimal | None:
    """
    Extract interest expense from the income statement.
    Standardized name is "Interest Expense" or similar.
    """
    if not income_statement or not income_statement.line_items:
        return None

    # First, try to find standardized "Interest Expense" name
    for item in income_statement.line_items:
        if "Interest Expense (" in item.line_name:
            return item.line_value

    # Fallback to loose matching
    for item in income_statement.line_items:
        name_lower = item.line_name.lower()
        if any(
            term in name_lower
            for term in ["interest expense", "interest and other expense", "interest expense net"]
        ):
            # Interest expense is usually a positive number in financial tables but an expense.
            # However, in our system, we store values AS EXTRACTED.
            # If it's labeled as expense, we return the value.
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


def get_operating_income_line_item(
    income_statement: IncomeStatement, llm_insights: dict[str, Any] | None = None
) -> IncomeStatementLineItem | None:
    """
    Extract the operating income line item from the income statement.
    Uses standardized name "operating_income".
    """
    # First, try to find standardized "operating_income" key (Highest Confidence)
    for item in income_statement.line_items:
        if hasattr(item, "standardized_name") and item.standardized_name == "operating_income":
            if item.line_value is not None:
                return item

    return None


def get_income_before_taxes_line_item(
    income_statement: IncomeStatement,
) -> IncomeStatementLineItem | None:
    """
    Extract the income before taxes line item from the income statement.
    Uses standardized name "income_before_taxes".
    """
    if not income_statement or not income_statement.line_items:
        return None

    for item in income_statement.line_items:
        if getattr(item, "standardized_name", None) == "income_before_taxes":
            if item.line_value is not None:
                return item

    return None


def calculate_ebita(
    income_statement: IncomeStatement,
    non_gaap_items: list[Any] | None = None,
) -> dict[str, Any] | None:
    """
    Calculate EBITA by taking Operating Income and adding non-operating items
    from the Non-GAAP reconciliation table.

    Fallback: If Operating Income is not found, use Income Before Taxes as the starting point.

    Returns a dictionary with:
    - total: The calculated EBITA value
    - operating_income: The operating income value used (or income_before_taxes if used as fallback)
    - adjustments: List of adjustment items used
    - used_fallback: Boolean indicating if income_before_taxes was used instead of operating_income
    - starting_value_label: Label for the starting profit figure
    """
    op_income_item = get_operating_income_line_item(income_statement)
    starting_item = op_income_item
    used_fallback = False
    starting_value_label = "Operating Income"

    if starting_item is None or starting_item.line_value is None:
        # Fallback 1: Use Income Before Taxes
        ibt_item = get_income_before_taxes_line_item(income_statement)
        if ibt_item and ibt_item.line_value is not None:
            starting_item = ibt_item
            used_fallback = True
            starting_value_label = "Income Before Taxes"
        else:
            return None

    operating_income = starting_item.line_value
    starting_order = starting_item.line_order

    ebita = operating_income
    adjustments = []

    # 1. Process explicit Non-GAAP items (from separate table/extraction)
    if non_gaap_items:
        for item in non_gaap_items:
            # Check if it's non-operating
            is_operating = getattr(item, "is_operating", None)
            if is_operating is None and isinstance(item, dict):
                is_operating = item.get("is_operating")

            # Skip if operating (we only want non-operating addbacks)
            if is_operating is not False:
                continue

            # Check for totals
            line_name = getattr(item, "line_name", "")
            if not line_name and isinstance(item, dict):
                line_name = item.get("line_name", "")

            name_lower = line_name.lower()
            if "total" in name_lower or "subtotal" in name_lower:
                continue

            # Get value
            line_value = getattr(item, "line_value", 0)
            if isinstance(item, dict):
                line_value = item.get("line_value", 0)

            # Add to EBITA
            ebita += Decimal(str(line_value))

            # Get category
            category = getattr(item, "category", None)
            if not category and isinstance(item, dict):
                category = item.get("line_category") or item.get("category")

            adjustments.append(
                {
                    "line_name": line_name,
                    "line_value": float(line_value),
                    "is_operating": False,
                    "category": category,
                }
            )

    # 2. Process Income Statement "Non-Operating" items
    # Logic: Items marked is_operating=False explicitly in the main IS table.
    # Constraint: Must be BEFORE the starting anchor line (Operating Income or IBT).
    # We do this regardless of whether Non-GAAP items were provided, to ensure completeness.
    if starting_order is not None:
        sorted_items = sorted(income_statement.line_items, key=lambda x: x.line_order)

        for item in sorted_items:
            # Must be before the starting line
            if item.line_order >= starting_order:
                continue

            # Must be explicitly non-operating
            if item.is_operating is not False:
                continue

            # Skip if already captured in explicit non-gaap items (prevent double counting)
            if any(adj["line_name"] == item.line_name for adj in adjustments):
                continue

            # Skip totals
            name_lower = item.line_name.lower()
            if "total" in name_lower or "subtotal" in name_lower:
                continue

            # Reverse sign for IS items (expenses usually negative -100).
            # To "Add Back", we negate the value.
            val_decimal = Decimal(str(item.line_value))
            adjustment_val = -val_decimal

            ebita += adjustment_val

            adjustments.append(
                {
                    "line_name": item.line_name,
                    "line_value": float(adjustment_val),
                    "is_operating": False,
                    "category": item.line_category,
                }
            )

    return {
        "total": ebita.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "operating_income": float(operating_income),
        "adjustments": adjustments,
        "used_fallback": used_fallback,
        "starting_value_label": starting_value_label,
    }


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

    # Try to use standardized names
    for item in income_statement.line_items:
        std_name = getattr(item, "standardized_name", None)
        if std_name:
            if std_name == "income_before_taxes":
                income_before_taxes = item.line_value
            elif std_name == "income_tax_provision":
                income_tax_expense = item.line_value
            elif std_name == "net_income":
                net_income = item.line_value

    if income_tax_expense is None and provision_for_income_taxes is not None:
        income_tax_expense = provision_for_income_taxes

    return {
        "income_before_taxes": income_before_taxes,
        "income_tax_expense": income_tax_expense,
        "net_income": net_income,
    }


def get_tax_expense_line_item(
    income_statement: IncomeStatement,
) -> IncomeStatementLineItem | None:
    """
    Extract the income tax expense line item.
    """
    if not income_statement or not income_statement.line_items:
        return None

    # Use standardized name "income_tax_provision"
    for item in income_statement.line_items:
        if getattr(item, "standardized_name", None) == "income_tax_provision":
            return item

    return None


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
            # Negate because income_tax_expense is stored as a negative expense
            # (e.g., -250 / 1000 = -0.25, we want 0.25)
            tax_rate = -(income_tax_expense / income_before_taxes)
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        if net_income is not None:
            # IBT - NI = Profit lost to tax.
            # (1000 - 750) / 1000 = 0.25. (Correct sign)
            tax_rate = (income_before_taxes - net_income) / income_before_taxes
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return None


def calculate_adjusted_tax_rate(
    income_statement: IncomeStatement,
    ebita: Decimal | None,
    non_gaap_items: list[Any] | None = None,
) -> dict[str, Any] | None:
    """
    Calculate Adjusted Tax Rate based on the formula:
    Adjusted Tax = Reported Tax + Tax Effect of Adjustments
    Adjusted Tax Rate = Adjusted Tax / EBITA

    Tax Effect = (Deductible Adjustments) * Marginal Tax Rate (25%)

    Adjustments include:
    1. Intermediate items between Operating Income and Tax Expense (excluded from EBITA)
    2. Non-GAAP reconciliation items (added back to EBITA)
    """
    if not income_statement or ebita is None or ebita == 0:
        return None

    tax_inputs = extract_tax_inputs(income_statement)
    reported_tax_expense = tax_inputs.get("income_tax_expense")

    if reported_tax_expense is None:
        return None

    marginal_tax_rate = Decimal("0.25")

    # 1. Intermediate and Pre-Anchor items
    anchor_item = get_operating_income_line_item(income_statement)
    if not anchor_item:
        anchor_item = get_income_before_taxes_line_item(income_statement)

    tax_item = get_tax_expense_line_item(income_statement)

    intermediate_items = []

    if anchor_item and tax_item:
        sorted_items = sorted(income_statement.line_items, key=lambda x: x.line_order)
        # Scan from the very top down to the tax line
        # Logic: We want to tax-effect any non-operating item that was excluded/added back to reach EBITA
        # If it's above the Profit Anchor, it was an "Add back".
        # If it's between Profit Anchor and Tax, it's an "Intermediate item".
        # In both cases, if it's is_operating=False, it contributes to the gap between EBITA and Taxable Income.

        # We define relevant range as [0, tax_item.line_order]
        target_limit_order = tax_item.line_order

        for item in sorted_items:
            # Must be above the tax line
            if item.line_order >= target_limit_order:
                continue

            # Skip the anchor itself
            if item.id == anchor_item.id:
                continue

            # Check if non-operating
            if item.is_operating is False:
                name_lower = item.line_name.lower()
                if item.is_calculated is True or "total" in name_lower or "subtotal" in name_lower:
                    continue

                intermediate_items.append(item)

    # 2. Non-GAAP items
    non_gaap_adjustments = []
    if non_gaap_items:
        for item in non_gaap_items:
            # Similar filtering as EBITA
            is_operating = getattr(item, "is_operating", None)
            if is_operating is None and isinstance(item, dict):
                is_operating = item.get("is_operating")

            if is_operating is not False:
                continue

            line_name = getattr(item, "line_name", "")
            if not line_name and isinstance(item, dict):
                line_name = item.get("line_name", "")

            name_lower = line_name.lower()
            if "total" in name_lower or "subtotal" in name_lower:
                continue

            non_gaap_adjustments.append(item)

    # Calculate Tax Effects
    adjustments_breakdown = []
    total_tax_adjustment = Decimal("0")

    # For intermediate items (usually expenses/other income excluded from EBITA)
    # If Expense (-100): We removed it. Taxable income +100. Tax +25.
    # So we negate the value.
    for item in intermediate_items:
        val = item.line_value
        name_lower = item.line_name.lower()

        # Specific tax rate: 0% for impairment, amortization, and equity items
        item_marginal_rate = marginal_tax_rate
        if any(term in name_lower for term in ["impairment", "amortization", "equity"]):
            item_marginal_rate = Decimal("0")

        # Effect on taxable income if we ADD BACK this item (or rather, ignore its deduction)
        # If it was -100 (deducted). Ignoring it means Income is +100 higher.
        effect_on_taxable_income = -val
        tax_effect = effect_on_taxable_income * item_marginal_rate

        total_tax_adjustment += tax_effect
        adjustments_breakdown.append(
            {
                "line_name": item.line_name,
                "line_value": float(val),
                "tax_effect": float(tax_effect),
                "source": "Intermediate",
                "marginal_rate": float(item_marginal_rate),
            }
        )

    # For Non-GAAP items (Addbacks)
    # These are added to Op Income to get EBITA.
    # If we add back 50. Taxable income +50. Tax +12.5.
    for item in non_gaap_adjustments:
        val = getattr(item, "line_value", 0)
        if isinstance(item, dict):
            val = item.get("line_value", 0)

        line_name = getattr(item, "line_name", "") or (
            item.get("line_name") if isinstance(item, dict) else ""
        )
        name_lower = line_name.lower()

        # Specific tax rate: 0% for impairment, amortization, and equity items
        item_marginal_rate = marginal_tax_rate
        if any(term in name_lower for term in ["impairment", "amortization", "equity"]):
            item_marginal_rate = Decimal("0")

        val_decimal = Decimal(str(val))
        tax_effect = val_decimal * item_marginal_rate

        total_tax_adjustment += tax_effect
        adjustments_breakdown.append(
            {
                "line_name": line_name,
                "line_value": float(val_decimal),
                "tax_effect": float(tax_effect),
                "source": "Non-GAAP",
                "marginal_rate": float(item_marginal_rate),
            }
        )

    adjusted_tax = reported_tax_expense + total_tax_adjustment

    # Calculate Rate
    # Adjusted Tax Rate = Adjusted Tax / EBITA
    # Negate because adjusted_tax contains negative expense values.
    adjusted_rate = -(adjusted_tax / ebita)

    return {
        "adjusted_tax_rate": adjusted_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "reported_tax_expense": float(reported_tax_expense),
        "adjusted_tax_expense": float(
            adjusted_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "adjustments": adjustments_breakdown,
        "marginal_rate": 0.25,
        "ebita": float(ebita),
    }


def calculate_all_historical_metrics(
    balance_sheet: BalanceSheet,
    income_statement: IncomeStatement,
    non_gaap_items: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Calculate all historical financial metrics for a document.
    Returns a dictionary with all calculated values and any notes.
    Note: Line items should already be standardized during extraction, so no LLM calls are needed here.
    """
    notes = []

    # Get basic values
    revenue = get_revenue(income_statement)

    # Calculate metrics
    net_working_capital_result = calculate_net_working_capital(balance_sheet)
    net_working_capital = (
        Decimal(str(net_working_capital_result["total"])) if net_working_capital_result else None
    )
    net_long_term_result = calculate_net_long_term_operating_assets(balance_sheet)
    net_long_term = Decimal(str(net_long_term_result["total"])) if net_long_term_result else None
    invested_capital = calculate_invested_capital(net_working_capital, net_long_term)
    capital_turnover = calculate_capital_turnover(
        revenue, invested_capital, income_statement.time_period if income_statement else None
    )

    ebita_result = calculate_ebita(income_statement, non_gaap_items)
    ebita = Decimal(str(ebita_result["total"])) if ebita_result else None

    ebita_margin = calculate_ebita_margin(ebita, revenue)

    tax_inputs = extract_tax_inputs(income_statement, None)
    effective_tax_rate = calculate_effective_tax_rate_from_inputs(
        tax_inputs.get("income_before_taxes"),
        tax_inputs.get("income_tax_expense"),
        tax_inputs.get("net_income"),
    )

    adjusted_tax_rate_result = calculate_adjusted_tax_rate(income_statement, ebita, non_gaap_items)
    adjusted_tax_rate = (
        Decimal(str(adjusted_tax_rate_result["adjusted_tax_rate"]))
        if adjusted_tax_rate_result
        else None
    )

    # Calculate NOPAT
    # NOPAT = EBITA * (1 - Adjusted Tax Rate)
    # If Adjusted Tax Rate is missing, fall back to Effective Tax Rate
    tax_rate_for_nopat = adjusted_tax_rate if adjusted_tax_rate is not None else effective_tax_rate
    nopat = None
    if ebita is not None and tax_rate_for_nopat is not None:
        nopat = ebita * (Decimal("1") - tax_rate_for_nopat)
        nopat = nopat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Calculate ROIC
    # ROIC = Annualized NOPAT / Invested Capital
    roic = None
    if nopat is not None and invested_capital and invested_capital != 0:
        annualized_nopat = nopat
        time_period = income_statement.time_period if income_statement else None

        # Check if quarterly
        if time_period:
            time_period_upper = time_period.upper().strip()
            is_quarterly = (
                bool(re.match(r"^Q[1-4]\s", time_period_upper))
                or bool(re.match(r"^Q[1-4]$", time_period_upper))
                or bool(re.search(r"[Q][1-4][\s-]?", time_period_upper))
            )
            if is_quarterly and not time_period_upper.startswith("FY"):
                annualized_nopat = nopat * Decimal("4")

        roic = annualized_nopat / invested_capital
        roic = roic.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # Add notes for missing data
    if revenue is None:
        notes.append("Revenue not found in income statement")
    if ebita is None:
        notes.append("EBITA could not be calculated (missing operating income)")
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

    interest_expense = get_interest_expense(income_statement)

    return {
        "net_working_capital": net_working_capital,
        "net_working_capital_breakdown": net_working_capital_result,
        "net_long_term_operating_assets": net_long_term,
        "net_long_term_operating_assets_breakdown": net_long_term_result,
        "invested_capital": invested_capital,
        "capital_turnover": capital_turnover,
        "ebita": ebita,
        "ebita_breakdown": ebita_result,
        "ebita_margin": ebita_margin,
        "effective_tax_rate": effective_tax_rate,
        "adjusted_tax_rate": adjusted_tax_rate,
        "adjusted_tax_rate_breakdown": adjusted_tax_rate_result,
        "nopat": nopat,
        "roic": roic,
        "interest_expense": interest_expense,
        "calculation_notes": notes,
    }

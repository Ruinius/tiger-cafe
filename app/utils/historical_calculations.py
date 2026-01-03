"""
Historical calculations utility for computing financial metrics
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.models.balance_sheet import BalanceSheet
from app.models.income_statement import IncomeStatement


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
    revenue: Decimal | None, invested_capital: Decimal | None
) -> Decimal | None:
    """
    Calculate capital turnover by dividing revenue by invested capital.
    """
    if revenue is None or invested_capital is None or invested_capital == 0:
        return None

    turnover = revenue / invested_capital
    return turnover.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def get_revenue(income_statement: IncomeStatement) -> Decimal | None:
    """
    Extract revenue from income statement line items.
    """
    if not income_statement or not income_statement.line_items:
        return None

    for item in income_statement.line_items:
        # Look for revenue line item
        name_lower = item.line_name.lower()
        category_lower = item.line_category.lower() if item.line_category else ""

        if (
            "revenue" in name_lower
            or "revenue" in category_lower
            or "sales" in name_lower
            or "net sales" in name_lower
        ):
            if item.line_value > 0:  # Revenue should be positive
                return item.line_value

    return None


def get_operating_income(income_statement: IncomeStatement) -> Decimal | None:
    """
    Extract operating income from income statement line items.
    Operating income might be called: Operating Income, Income from Operations, etc.
    """
    if not income_statement or not income_statement.line_items:
        return None

    for item in income_statement.line_items:
        name_lower = item.line_name.lower()

        # Look for operating income by various names
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
            # Make sure it's not a total or subtotal
            if "total" not in name_lower and "subtotal" not in name_lower:
                return item.line_value

    return None


def get_non_operating_items_between_revenue_and_operating_income(
    income_statement: IncomeStatement,
) -> Decimal:
    """
    Get sum of all non-operating items between Revenue and Operating Income.
    These need to be subtracted from Operating Income to get EBITA.
    """
    if not income_statement or not income_statement.line_items:
        return Decimal("0")

    # Sort items by line_order to maintain statement order
    sorted_items = sorted(income_statement.line_items, key=lambda x: x.line_order)

    revenue_found = False
    operating_income_found = False
    non_operating_sum = Decimal("0")

    for item in sorted_items:
        name_lower = item.line_name.lower()

        # Check if we've reached revenue
        if not revenue_found:
            if any(term in name_lower for term in ["revenue", "sales", "net sales"]):
                revenue_found = True
            continue

        # If we've passed revenue, check if we've reached operating income
        if any(
            term in name_lower
            for term in ["operating income", "income from operations", "operating profit"]
        ):
            operating_income_found = True
            break

        # If item is labeled as non-operating and we're between revenue and operating income
        # Non-operating expenses (negative values) reduce operating income, so we add them back
        # Non-operating income (positive values) increase operating income, so we subtract them
        if item.is_operating is False:
            # If it's an expense (negative), we add it back (subtract negative = add)
            # If it's income (positive), we subtract it
            non_operating_sum -= item.line_value

    # Only return sum if we found both revenue and operating income
    if revenue_found and operating_income_found:
        return non_operating_sum
    else:
        return Decimal("0")


def calculate_ebita(
    income_statement: IncomeStatement, amortization: Decimal | None = None
) -> Decimal | None:
    """
    Calculate EBITA by taking Operating Income, subtracting non-operating items
    between Revenue and Operating Income, and subtracting Amortization if available.
    """
    operating_income = get_operating_income(income_statement)
    if operating_income is None:
        return None

    # Subtract non-operating items between revenue and operating income
    non_operating_items = get_non_operating_items_between_revenue_and_operating_income(
        income_statement
    )
    ebita = operating_income - non_operating_items

    # Subtract amortization if available and not already subtracted
    if amortization is not None:
        ebita = ebita - amortization

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


def calculate_effective_tax_rate(income_statement: IncomeStatement) -> Decimal | None:
    """
    Calculate effective tax rate using multiple methods depending on what's available.
    Returns as decimal (e.g., 0.25 for 25%).
    """
    if not income_statement or not income_statement.line_items:
        return None

    # Try to find income before taxes and income tax expense
    income_before_taxes = None
    income_tax_expense = None
    provision_for_income_taxes = None
    net_income = None

    for item in income_statement.line_items:
        name_lower = item.line_name.lower()

        # Look for income before taxes
        if any(
            term in name_lower
            for term in [
                "income before taxes",
                "income before income taxes",
                "earnings before income taxes",
                "profit before tax",
                "income before income tax expense",
                "pre-tax income",
            ]
        ):
            income_before_taxes = item.line_value

        # Look for income tax expense
        elif any(
            term in name_lower
            for term in ["income tax expense", "income taxes", "provision for income taxes"]
        ):
            if "provision" in name_lower:
                provision_for_income_taxes = abs(
                    item.line_value
                )  # Usually negative in income statement
            else:
                income_tax_expense = abs(item.line_value)

        # Look for net income
        elif any(term in name_lower for term in ["net income", "net earnings", "profit after tax"]):
            if "total" not in name_lower:
                net_income = item.line_value

    # Method 1: Income tax expense / Income before taxes
    if income_before_taxes and income_before_taxes != 0:
        if income_tax_expense is not None:
            tax_rate = income_tax_expense / abs(income_before_taxes)
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif provision_for_income_taxes is not None:
            tax_rate = provision_for_income_taxes / abs(income_before_taxes)
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # Method 2: (Income before taxes - Net income) / Income before taxes
    if income_before_taxes and income_before_taxes != 0 and net_income is not None:
        taxes_paid = abs(income_before_taxes) - abs(net_income)
        if taxes_paid > 0:
            tax_rate = taxes_paid / abs(income_before_taxes)
            return tax_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return None


def calculate_all_historical_metrics(
    balance_sheet: BalanceSheet, income_statement: IncomeStatement
) -> dict[str, Any]:
    """
    Calculate all historical financial metrics for a document.
    Returns a dictionary with all calculated values and any notes.
    """
    notes = []

    # Get basic values
    revenue = get_revenue(income_statement)
    amortization = income_statement.amortization if income_statement else None

    # Calculate metrics
    net_working_capital = calculate_net_working_capital(balance_sheet)
    net_long_term = calculate_net_long_term_operating_assets(balance_sheet)
    invested_capital = calculate_invested_capital(net_working_capital, net_long_term)
    capital_turnover = calculate_capital_turnover(revenue, invested_capital)
    ebita = calculate_ebita(income_statement, amortization)
    ebita_margin = calculate_ebita_margin(ebita, revenue)
    effective_tax_rate = calculate_effective_tax_rate(income_statement)

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

    # Check for unusual tax rates (but don't adjust - that's a future enhancement)
    if effective_tax_rate:
        if effective_tax_rate > Decimal("0.35"):
            notes.append(
                f"Effective tax rate ({effective_tax_rate * 100:.1f}%) appears high (>35%)"
            )
        elif effective_tax_rate < Decimal("0.10"):
            notes.append(f"Effective tax rate ({effective_tax_rate * 100:.1f}%) appears low (<10%)")

    return {
        "net_working_capital": net_working_capital,
        "net_long_term_operating_assets": net_long_term,
        "invested_capital": invested_capital,
        "capital_turnover": capital_turnover,
        "ebita": ebita,
        "ebita_margin": ebita_margin,
        "effective_tax_rate": effective_tax_rate,
        "calculation_notes": notes,
    }

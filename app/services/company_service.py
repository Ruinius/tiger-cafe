import re
from collections import Counter

from sqlalchemy.orm import Session, selectinload

from app.models.balance_sheet import BalanceSheet
from app.models.company import Company
from app.models.document import Document, DocumentType
from app.models.financial_assumption import FinancialAssumption
from app.models.income_statement import IncomeStatement
from app.models.non_operating_classification import (
    NonOperatingClassification,
    NonOperatingClassificationItem,
)
from app.models.qualitative_assessment import QualitativeAssessment
from app.utils.historical_calculations import get_interest_expense, get_revenue
from app.utils.line_item_utils import convert_from_ones, convert_to_ones
from app.utils.market_data import (
    get_beta,
    get_currency_rate,
    get_market_cap,
)

ELIGIBLE_DOCUMENT_TYPES = {
    DocumentType.EARNINGS_ANNOUNCEMENT,
    DocumentType.QUARTERLY_FILING,
    DocumentType.ANNUAL_FILING,
}


def time_period_sort_key(time_period: str) -> tuple[int, int, str]:
    if not time_period:
        return (0, 0, "")

    quarter_match = re.match(r"^Q([1-4])\s+(\d{4})$", time_period.strip(), re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        return (year, quarter, time_period)

    fy_match = re.match(r"^FY\s*(\d{4})$", time_period.strip(), re.IGNORECASE)
    if fy_match:
        year = int(fy_match.group(1))
        return (year, 5, time_period)

    year_match = re.search(r"(20\d{2})", time_period)
    if year_match:
        return (int(year_match.group(1)), 0, time_period)

    return (0, 0, time_period)


def get_company_historical_data(db: Session, company_id: str) -> dict:
    """
    Orchestrate fetching, assembling, and normalizing historical financial data
    for a given company.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return None  # Or raise, but usually services return None and router raises 404

    documents = (
        db.query(Document)
        .filter(Document.company_id == company_id)
        .filter(Document.document_type.in_(ELIGIBLE_DOCUMENT_TYPES))
        .options(
            selectinload(Document.historical_calculation),
            selectinload(Document.organic_growth),
            selectinload(Document.shares_outstanding),
            selectinload(Document.income_statement).selectinload(IncomeStatement.line_items),
        )
        .all()
    )

    entries_by_period: dict[str, dict] = {}
    currency_values: set[str] = set()
    all_units: list[str] = []

    for document in documents:
        calc = document.historical_calculation
        if not calc:
            continue

        time_period = (
            calc.time_period
            or (document.income_statement.time_period if document.income_statement else None)
            or document.time_period
            or "Unknown"
        )

        revenue = get_revenue(document.income_statement) if document.income_statement else None

        # Helper to safely convert Decimal to float
        def to_float(val):
            return float(val) if val is not None else None

        entry = {
            "time_period": time_period,
            "period_end_date": document.period_end_date,
            "revenue": to_float(revenue),
            "revenue_growth_yoy": to_float(document.income_statement.revenue_growth_yoy)
            if document.income_statement
            else None,
            "ebita": to_float(calc.ebita),
            "ebita_margin": to_float(calc.ebita_margin),
            "effective_tax_rate": to_float(calc.effective_tax_rate),
            "adjusted_tax_rate": to_float(calc.adjusted_tax_rate),
            "net_working_capital": to_float(calc.net_working_capital),
            "net_long_term_operating_assets": to_float(calc.net_long_term_operating_assets),
            "invested_capital": to_float(calc.invested_capital),
            "capital_turnover": to_float(calc.capital_turnover),
            "nopat": to_float(calc.nopat),
            "roic": to_float(calc.roic),
            "organic_revenue_growth": to_float(document.organic_growth.organic_revenue_growth)
            if document.organic_growth
            else None,
            "calculated_at": calc.calculated_at,
            "diluted_shares_outstanding": to_float(
                document.shares_outstanding.diluted_shares_outstanding
            )
            if document.shares_outstanding
            else None,
            "basic_shares_outstanding": to_float(
                document.shares_outstanding.basic_shares_outstanding
            )
            if document.shares_outstanding
            else None,
            "interest_expense": to_float(get_interest_expense(document.income_statement))
            if document.income_statement
            else None,
            "simple_revenue_growth": to_float(document.organic_growth.simple_revenue_growth)
            if document.organic_growth
            else None,
            # Temporarily store unit/currency for normalization
            "_unit": calc.unit,
            "_currency": calc.currency,
        }

        if calc.currency:
            currency_values.add(calc.currency)
        if calc.unit:
            all_units.append(calc.unit)

        period_key = document.period_end_date or time_period
        existing = entries_by_period.get(period_key)
        if existing is None or entry["calculated_at"] > existing["calculated_at"]:
            entries_by_period[period_key] = entry

    # Sort by period_end_date (most reliable), fallback to time_period_sort_key
    def sort_key(item):
        if item.get("period_end_date"):
            # Use period_end_date as primary sort key (convert to timestamp)
            from datetime import datetime

            return (datetime.fromisoformat(str(item["period_end_date"])).timestamp(), 0, "")
        else:
            # Fallback to time_period parsing
            return time_period_sort_key(item["time_period"])

    sorted_entries = sorted(entries_by_period.values(), key=sort_key)

    # Unit Normalization Logic
    # 1. Determine predominate unit
    target_unit = None
    if all_units:
        # Most common unit wins
        target_unit, _ = Counter(all_units).most_common(1)[0]

    # 2. Normalize values if they differ from predominate unit
    fields_to_convert = [
        "revenue",
        "ebita",
        "net_working_capital",
        "net_long_term_operating_assets",
        "invested_capital",
        "nopat",
        "interest_expense",
        "diluted_shares_outstanding",
        "basic_shares_outstanding",
    ]

    for entry in sorted_entries:
        entry_unit = entry.pop("_unit", None)
        entry.pop("_currency", None)  # Clean up

        if target_unit and entry_unit and entry_unit.lower().strip() != target_unit.lower().strip():
            for field in fields_to_convert:
                val = entry.get(field)
                if val is not None:
                    # Convert to ones then to target
                    try:
                        val_float = float(val)
                        val_ones = convert_to_ones(val_float, entry_unit)
                        val_converted = convert_from_ones(val_ones, target_unit)
                        entry[field] = val_converted
                    except (ValueError, TypeError):
                        pass

    # Calculate YOY Marginal Capital Turnover
    # Marginal Capital Turnover = Change in Revenue / Change in Invested Capital
    for i in range(1, len(sorted_entries)):
        current_entry = sorted_entries[i]
        prev_entry = sorted_entries[i - 1]

        if (
            current_entry["revenue"] is not None
            and prev_entry["revenue"] is not None
            and current_entry["invested_capital"] is not None
            and prev_entry["invested_capital"] is not None
        ):
            delta_revenue = current_entry["revenue"] - prev_entry["revenue"]
            delta_ic = current_entry["invested_capital"] - prev_entry["invested_capital"]

            # Avoid division by zero
            if delta_ic != 0:
                current_entry["marginal_capital_turnover"] = delta_revenue / delta_ic
            else:
                current_entry["marginal_capital_turnover"] = None
        else:
            current_entry["marginal_capital_turnover"] = None

    currency = None
    unit = None
    if len(currency_values) == 1:
        currency = next(iter(currency_values))
    elif len(currency_values) > 1:
        currency = "Multiple"

    # Use the target unit as the single unit for the response
    if target_unit:
        unit = target_unit
    elif len(set(all_units)) > 1:
        unit = "Multiple"

    return {
        "company_id": company_id,
        "currency": currency,
        "unit": unit,
        "entries": [
            {key: value for key, value in entry.items() if key != "calculated_at"}
            for entry in sorted_entries
        ],
    }


def get_or_create_assumptions(db: Session, company_id: str) -> FinancialAssumption:
    """
    Get existing financial assumptions or create new ones with defaults
    derived from historical data and qualitative assessments.
    Enriches the result with dynamic market data (Beta, WACC components).
    """
    assumption = (
        db.query(FinancialAssumption).filter(FinancialAssumption.company_id == company_id).first()
    )

    # Fetch historical data (needed for defaults AND dynamic cost of debt)
    historical_data = get_company_historical_data(db, company_id)
    historical_entries = historical_data.get("entries", []) if historical_data else []

    # 1. Beta: Fetch from Yahoo Finance
    company = db.query(Company).filter(Company.id == company_id).first()
    beta = 1.0
    if company and company.ticker:
        raw_beta = float(get_beta(company.ticker))
        # Blume's Adjustment: Modified Beta = (2/3) * Raw Beta + (1/3) * 1.0
        beta = (2.0 / 3.0) * raw_beta + (1.0 / 3.0)

    # 2. WACC Components
    market_cap = float(get_market_cap(company.ticker)) if company and company.ticker else 0.0

    # We need bridge items for Debt
    non_op_classifications = (
        db.query(NonOperatingClassification)
        .join(Document)
        .filter(Document.company_id == company_id)
        .options(
            selectinload(NonOperatingClassification.document)
            .selectinload(Document.balance_sheet)
            .selectinload(BalanceSheet.line_items)
        )
        .all()
    )

    non_op_classification = None
    if non_op_classifications:
        non_op_classifications.sort(
            key=lambda x: time_period_sort_key(x.document.time_period) if x.document else (0, 0, "")
        )
        non_op_classification = non_op_classifications[-1]

    debt = 0.0
    bs_unit = "millions"
    if non_op_classification:
        # Create lookup map from balance sheet
        bs_values = {}
        if non_op_classification.document and non_op_classification.document.balance_sheet:
            bs_unit = non_op_classification.document.balance_sheet.unit or "millions"
            for bsi in non_op_classification.document.balance_sheet.line_items:
                bs_values[bsi.line_name] = bsi.line_value

        items = (
            db.query(NonOperatingClassificationItem)
            .filter(NonOperatingClassificationItem.classification_id == non_op_classification.id)
            .all()
        )
        for item in items:
            if item.category == "debt":
                val = bs_values.get(item.line_name) or 0
                debt += float(val)

    # Convert debt to absolute dollars (ones) - this is in LOCAL CURRENCY
    debt_local_ones = convert_to_ones(debt, bs_unit)

    # debt_dollars will be in USD for WACC weight calculation
    debt_dollars = debt_local_ones

    # Convert debt to USD if balance sheet is in different currency
    # Market cap from Yahoo is typically in USD for US-listed tickers
    if (
        non_op_classification
        and non_op_classification.document
        and non_op_classification.document.balance_sheet
    ):
        bs_currency = non_op_classification.document.balance_sheet.currency
        if bs_currency and bs_currency != "USD":
            # Convert debt from local currency to USD
            conversion_rate = float(get_currency_rate(bs_currency, "USD"))
            debt_dollars = debt_local_ones * conversion_rate

    weight_of_equity = 1.0
    if (market_cap + debt_dollars) > 0:
        weight_of_equity = market_cap / (market_cap + debt_dollars)

    # Cost of Debt - Calculate in LOCAL CURRENCY
    interest_expense_annualized_ones = 0.0
    if historical_entries:
        latest = historical_entries[-1]
        ie = latest.get("interest_expense")
        if ie is not None:
            # ie is in historical_data["unit"]
            hist_unit = historical_data.get("unit")
            ie_ones = convert_to_ones(float(ie), hist_unit)
            interest_expense_annualized_ones = abs(ie_ones) * 4.0

    cost_of_debt = 0.05
    # Use debt_local_ones (local currency) for Cost of Debt calculation
    if debt_local_ones > 0:
        calculated_cod = interest_expense_annualized_ones / debt_local_ones
        cost_of_debt = max(calculated_cod, 0.05)  # Minimum 5%

    # Cost of Equity
    risk_free_rate = 0.042
    market_risk_premium = 0.05
    cost_of_equity = risk_free_rate + (beta * market_risk_premium)

    # Calculated WACC
    marginal_tax_rate = 0.25
    calculated_wacc = (cost_of_equity * weight_of_equity) + (
        cost_of_debt * (1 - marginal_tax_rate) * (1 - weight_of_equity)
    )

    # Bound calculated WACC to 7-11% for default value
    bounded_wacc = max(0.07, min(0.11, calculated_wacc))

    # IF NO ASSUMPTION: Create with defaults
    if not assumption:
        # Calculate defaults from L4Q historical data
        quarterly_entries = [e for e in historical_entries if "Q" in e.get("time_period", "")]
        l4q_list = quarterly_entries[-4:] if len(quarterly_entries) >= 4 else quarterly_entries

        def l4q_avg(field):
            vals = [e.get(field) for e in l4q_list if e.get(field) is not None]
            return sum(vals) / len(vals) if vals else None

        # --- QUALITATIVE ASSESSMENT OVERRIDES ---
        qualitative = (
            db.query(QualitativeAssessment)
            .filter(QualitativeAssessment.company_id == company_id)
            .first()
        )

        # 1. Stage 1 Revenue Growth: L4Q Average Organic Growth
        organic_growth = l4q_avg("organic_revenue_growth")
        stage1_growth = float(organic_growth) / 100 if organic_growth else 0.05

        # Apply Logic: Faster -> +2%, Slower -> -2%
        if qualitative:
            if qualitative.near_term_growth_label == "Faster":
                stage1_growth += 0.02
            elif qualitative.near_term_growth_label == "Slower":
                stage1_growth -= 0.02

        # 2. Terminal Growth
        terminal_growth = 0.03
        if qualitative:
            if qualitative.economic_moat_label == "Wide":
                terminal_growth = 0.04
            elif qualitative.economic_moat_label == "Narrow":
                terminal_growth = 0.035
            # Else None/other -> 0.03

        stage2_growth = (stage1_growth + terminal_growth) / 2

        # 3. EBITA Margin
        ebita_margin_avg = l4q_avg("ebita_margin")
        ebita_margin = float(ebita_margin_avg) if ebita_margin_avg else 0.20

        # 4. Capital Turnover
        capital_turnover_avg = l4q_avg("capital_turnover")
        if capital_turnover_avg and 0 < capital_turnover_avg < 100:
            mct = float(capital_turnover_avg)
        else:
            mct = 100.0

        # 5. Tax Rate - Use Median of Historical Data
        all_tax_rates = sorted(
            [
                float(e.get("adjusted_tax_rate"))
                for e in historical_entries
                if e.get("adjusted_tax_rate") is not None
            ]
        )
        if all_tax_rates:
            mid = len(all_tax_rates) // 2
            if len(all_tax_rates) % 2 == 0:
                tax_rate = (all_tax_rates[mid - 1] + all_tax_rates[mid]) / 2.0
            else:
                tax_rate = all_tax_rates[mid]
        else:
            tax_rate = 0.25

        # 6. Shares
        diluted_shares = None
        if historical_entries:
            # 1. Try Latest
            latest = historical_entries[-1]
            diluted_shares = latest.get("diluted_shares_outstanding") or latest.get(
                "basic_shares_outstanding"
            )

            # 2. Fallback: L4Q Average
            if not diluted_shares and l4q_list:
                diluted_shares = l4q_avg("diluted_shares_outstanding")

            # 3. Fallback: Median of all history
            if not diluted_shares:
                all_shares = sorted(
                    [
                        float(e.get("diluted_shares_outstanding"))
                        for e in historical_entries
                        if e.get("diluted_shares_outstanding") is not None
                    ]
                )
                if all_shares:
                    mid = len(all_shares) // 2
                    if len(all_shares) % 2 == 0:
                        diluted_shares = (all_shares[mid - 1] + all_shares[mid]) / 2.0
                    else:
                        diluted_shares = all_shares[mid]

        # 7. Base Revenue
        base_revenue = None
        if l4q_list:
            revenue_values = [e.get("revenue") for e in l4q_list if e.get("revenue") is not None]
            if revenue_values:
                base_revenue = (sum(revenue_values) / len(revenue_values)) * 4

        # 8. Currency & ADR
        currency_conversion_rate = 1.0
        latest_currency = "USD"

        # Query the most recent balance sheet for this company
        latest_balance_sheet = (
            db.query(BalanceSheet)
            .join(Document)
            .filter(Document.company_id == company_id)
            .order_by(BalanceSheet.extraction_date.desc())
            .first()
        )

        if latest_balance_sheet and latest_balance_sheet.currency:
            latest_currency = latest_balance_sheet.currency

        if latest_currency and latest_currency != "USD":
            currency_conversion_rate = float(get_currency_rate(latest_currency, "USD"))

        assumption = FinancialAssumption(
            company_id=company_id,
            revenue_growth_stage1=stage1_growth,
            revenue_growth_stage2=stage2_growth,
            revenue_growth_terminal=terminal_growth,
            ebita_margin_stage1=ebita_margin,
            ebita_margin_stage2=ebita_margin,
            ebita_margin_terminal=ebita_margin,
            marginal_capital_turnover_stage1=mct,
            marginal_capital_turnover_stage2=mct,
            marginal_capital_turnover_terminal=mct,
            beta=beta,
            adjusted_tax_rate=tax_rate,
            wacc=bounded_wacc,
            diluted_shares_outstanding=diluted_shares,
            base_revenue=base_revenue,
            currency_conversion_rate=currency_conversion_rate,
            adr_conversion_factor=1.0,
        )
        db.add(assumption)
        db.commit()
        db.refresh(assumption)

    # Attach dynamic fields for display
    assumption.weight_of_equity = weight_of_equity
    assumption.cost_of_debt = cost_of_debt
    assumption.calculated_wacc = calculated_wacc
    assumption.market_cap = market_cap
    assumption.beta = beta

    return assumption

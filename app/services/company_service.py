import re
from collections import Counter

from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.document import Document, DocumentType
from app.models.income_statement import IncomeStatement
from app.utils.historical_calculations import get_interest_expense, get_revenue
from app.utils.line_item_utils import convert_from_ones, convert_to_ones

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

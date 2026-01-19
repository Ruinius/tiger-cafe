"""
Company routes
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.balance_sheet import BalanceSheet
from app.models.company import Company
from app.models.document import Document, DocumentType
from app.models.financial_assumption import FinancialAssumption
from app.models.income_statement import IncomeStatement
from app.models.non_operating_classification import (
    NonOperatingClassification,
    NonOperatingClassificationItem,
)
from app.models.user import User
from app.models.valuation import Valuation
from app.routers.auth import get_current_user
from app.schemas.company import Company as CompanySchema
from app.schemas.company import CompanyCreate
from app.schemas.company_historical_calculations import CompanyHistoricalCalculations
from app.schemas.financial_assumption import FinancialAssumption as FinancialAssumptionSchema
from app.schemas.financial_assumption import FinancialAssumptionCreate
from app.schemas.valuation import Valuation as ValuationSchema
from app.schemas.valuation import ValuationCreate
from app.utils.financial_modeling import calculate_dcf
from app.utils.historical_calculations import get_interest_expense, get_revenue
from app.utils.market_data import get_beta, get_latest_share_price, get_market_cap

router = APIRouter()


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


@router.get("/", response_model=list[CompanySchema])
async def list_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all companies with document counts"""
    # Query companies with document counts
    companies = (
        db.query(Company, func.count(Document.id).label("document_count"))
        .outerjoin(Document, Company.id == Document.company_id)
        .group_by(Company.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Convert to schema format with document counts
    result = []
    for company, doc_count in companies:
        # Filter out placeholder "Processing..." companies that have no documents
        # These are temporary placeholders created during upload
        if company.name == "Processing..." and (doc_count or 0) == 0:
            continue  # Skip placeholder companies with no documents

        company_dict = {
            "id": company.id,
            "name": company.name,
            "ticker": company.ticker,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "document_count": doc_count or 0,
        }
        result.append(company_dict)

    return result


@router.get("/{company_id}", response_model=CompanySchema)
async def get_company(
    company_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get a specific company by ID"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/", response_model=CompanySchema)
async def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new company"""
    ticker = company.ticker.strip().upper() if company.ticker else None
    name = company.name.strip() if company.name else "Unknown"

    # If ticker is provided, check if it already exists
    if ticker:
        existing = db.query(Company).filter(Company.ticker == ticker).first()
        if existing:
            # If the existing company has a placeholder name, update it
            if existing.name == "Processing..." and name and name != "Processing...":
                existing.name = name
                db.commit()
                db.refresh(existing)
            return existing

    # Otherwise create new
    db_company = Company(id=str(uuid.uuid4()), name=name, ticker=ticker)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


@router.get("/{company_id}/historical-calculations", response_model=CompanyHistoricalCalculations)
async def get_company_historical_calculations(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get historical calculations for a company across eligible documents."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    documents = (
        db.query(Document)
        .filter(Document.company_id == company_id)
        .filter(Document.document_type.in_(ELIGIBLE_DOCUMENT_TYPES))
        .options(
            selectinload(Document.historical_calculation),
            selectinload(Document.organic_growth),
            selectinload(Document.income_statement).selectinload(IncomeStatement.line_items),
        )
        .all()
    )

    entries_by_period: dict[str, dict] = {}
    currency_values: set[str] = set()
    unit_values: set[str] = set()

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
        entry = {
            "time_period": time_period,
            "revenue": revenue,
            "revenue_growth_yoy": document.income_statement.revenue_growth_yoy
            if document.income_statement
            else None,
            "ebita": calc.ebita,
            "ebita_margin": calc.ebita_margin,
            "effective_tax_rate": calc.effective_tax_rate,
            "adjusted_tax_rate": calc.adjusted_tax_rate,
            "net_working_capital": calc.net_working_capital,
            "net_long_term_operating_assets": calc.net_long_term_operating_assets,
            "invested_capital": calc.invested_capital,
            "capital_turnover": calc.capital_turnover,
            "nopat": calc.nopat,
            "roic": calc.roic,
            "organic_revenue_growth": document.organic_growth.organic_revenue_growth
            if document.organic_growth
            else None,
            "calculated_at": calc.calculated_at,
            "diluted_shares_outstanding": document.income_statement.diluted_shares_outstanding
            if document.income_statement
            else None,
            "basic_shares_outstanding": document.income_statement.basic_shares_outstanding
            if document.income_statement
            else None,
            "interest_expense": get_interest_expense(document.income_statement)
            if document.income_statement
            else None,
            "simple_revenue_growth": document.organic_growth.simple_revenue_growth
            if document.organic_growth
            else None,
        }

        if calc.currency:
            currency_values.add(calc.currency)
        if calc.unit:
            unit_values.add(calc.unit)

        existing = entries_by_period.get(time_period)
        if existing is None or entry["calculated_at"] > existing["calculated_at"]:
            entries_by_period[time_period] = entry

    sorted_entries = sorted(
        entries_by_period.values(), key=lambda item: time_period_sort_key(item["time_period"])
    )

    # Calculate YOY Marginal Capital Turnover
    # Marginal Capital Turnover = Change in Revenue / Change in Invested Capital
    for i in range(1, len(sorted_entries)):
        current_entry = sorted_entries[i]
        prev_entry = sorted_entries[i - 1]

        # Ensure entries have necessary data and are consecutive (optional check, but logic applies regardless)
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

    if len(unit_values) == 1:
        unit = next(iter(unit_values))
    elif len(unit_values) > 1:
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


@router.get(
    "/{company_id}/historical-calculations/test", response_model=CompanyHistoricalCalculations
)
async def get_company_historical_calculations_test(company_id: str, db: Session = Depends(get_db)):
    """Test endpoint for company historical calculations (no auth required)."""
    return await get_company_historical_calculations(company_id, db, current_user=None)


@router.get("/{company_id}/assumptions", response_model=FinancialAssumptionSchema)
async def get_financial_assumptions(
    company_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get financial assumptions for a company"""
    assumption = (
        db.query(FinancialAssumption).filter(FinancialAssumption.company_id == company_id).first()
    )

    # We always need to calculate dynamic fields (WACC components)
    historical_data = await get_company_historical_calculations(company_id, db, current_user)
    historical_entries = historical_data.get("entries", [])

    # 1. Beta: Fetch from Yahoo Finance
    company = db.query(Company).filter(Company.id == company_id).first()
    beta = 1.0
    if company and company.ticker:
        beta = float(get_beta(company.ticker))

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
    if non_op_classification:
        # Create lookup map from balance sheet
        bs_values = {}
        if non_op_classification.document and non_op_classification.document.balance_sheet:
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

    # Weight of Equity
    # Market Cap is in absolute dollars (e.g., 135,000,000,000)
    # Debt is in millions (e.g., 31,000 means 31,000,000,000)
    debt_dollars = debt * 1_000_000

    weight_of_equity = 1.0
    if (market_cap + debt_dollars) > 0:
        weight_of_equity = market_cap / (market_cap + debt_dollars)

    # Cost of Debt
    interest_expense_annualized = 0.0
    if historical_entries:
        latest = historical_entries[-1]
        ie = latest.get("interest_expense")
        if ie is not None:
            interest_expense_annualized = abs(float(ie)) * 4.0

    cost_of_debt = 0.05
    if debt > 0:
        calculated_cod = interest_expense_annualized / debt
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

    if not assumption:
        # Calculate defaults from L4Q historical data
        quarterly_entries = [e for e in historical_entries if "Q" in e.get("time_period", "")]
        l4q_list = quarterly_entries[-4:] if len(quarterly_entries) >= 4 else quarterly_entries

        def l4q_avg(field):
            vals = [e.get(field) for e in l4q_list if e.get(field) is not None]
            return sum(vals) / len(vals) if vals else None

        # 1. Stage 1 Revenue Growth: L4Q Average Organic Growth
        organic_growth = l4q_avg("organic_revenue_growth")
        stage1_growth = float(organic_growth) / 100 if organic_growth else 0.05
        terminal_growth = 0.03
        stage2_growth = (stage1_growth + terminal_growth) / 2

        # 2. EBITA Margin
        ebita_margin_avg = l4q_avg("ebita_margin")
        ebita_margin = float(ebita_margin_avg) if ebita_margin_avg else 0.20

        # 3. Capital Turnover
        capital_turnover_avg = l4q_avg("capital_turnover")
        if capital_turnover_avg and 0 < capital_turnover_avg < 100:
            mct = float(capital_turnover_avg)
        else:
            mct = 100.0

        # 4. Tax Rate
        tax_rate_avg = l4q_avg("adjusted_tax_rate")
        tax_rate = float(tax_rate_avg) if tax_rate_avg else 0.25

        # 5. Shares
        diluted_shares = None
        if historical_entries:
            latest = historical_entries[-1]
            diluted_shares = latest.get("diluted_shares_outstanding") or latest.get(
                "basic_shares_outstanding"
            )

        # 6. Base Revenue
        base_revenue = None
        if l4q_list:
            revenue_values = [e.get("revenue") for e in l4q_list if e.get("revenue") is not None]
            if revenue_values:
                base_revenue = (sum(revenue_values) / len(revenue_values)) * 4

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
            wacc=calculated_wacc,
            diluted_shares_outstanding=diluted_shares,
            base_revenue=base_revenue,
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


@router.post("/{company_id}/assumptions", response_model=FinancialAssumptionSchema)
async def update_financial_assumptions(
    company_id: str,
    assumption_data: FinancialAssumptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update financial assumptions for a company"""
    assumption = (
        db.query(FinancialAssumption).filter(FinancialAssumption.company_id == company_id).first()
    )
    if not assumption:
        assumption = FinancialAssumption(company_id=company_id)
        db.add(assumption)

    for key, value in assumption_data.dict(exclude_unset=True).items():
        setattr(assumption, key, value)

    db.commit()
    db.refresh(assumption)
    return assumption


@router.delete("/{company_id}/assumptions", response_model=FinancialAssumptionSchema)
async def reset_financial_assumptions(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset financial assumptions to L4Q-based defaults"""
    # Delete existing assumption
    assumption = (
        db.query(FinancialAssumption).filter(FinancialAssumption.company_id == company_id).first()
    )
    if assumption:
        db.delete(assumption)
        db.commit()

    # Get will recreate with defaults
    return await get_financial_assumptions(company_id, db, current_user)


@router.get("/{company_id}/financial-model")
async def get_financial_model(
    company_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get financial model (DCF) for a company"""

    # 1. Fetch historical data
    # We re-use the logic from get_company_historical_calculations, but we call it internally
    # Note: Depends(get_current_user) works in the route handler, but if we call the function directly we need to handle it.
    # Since we are in the same file, we can refactor or call it. Calling async function is fine.

    historical_data = await get_company_historical_calculations(company_id, db, current_user)
    historical_entries = historical_data.get("entries", [])

    # 2. Fetch assumptions
    assumption = (
        db.query(FinancialAssumption).filter(FinancialAssumption.company_id == company_id).first()
    )
    assumptions_dict = {}
    if assumption:
        assumptions_dict = {
            "revenue_growth_stage1": assumption.revenue_growth_stage1,
            "revenue_growth_stage2": assumption.revenue_growth_stage2,
            "revenue_growth_terminal": assumption.revenue_growth_terminal,
            "ebita_margin_stage1": assumption.ebita_margin_stage1,
            "ebita_margin_stage2": assumption.ebita_margin_stage2,
            "ebita_margin_terminal": assumption.ebita_margin_terminal,
            "marginal_capital_turnover_stage1": assumption.marginal_capital_turnover_stage1,
            "marginal_capital_turnover_stage2": assumption.marginal_capital_turnover_stage2,
            "marginal_capital_turnover_terminal": assumption.marginal_capital_turnover_terminal,
            "adjusted_tax_rate": assumption.adjusted_tax_rate,
            "wacc": assumption.wacc,
            "base_revenue": assumption.base_revenue,
        }

    # 3. Calculate Model
    result = calculate_dcf(historical_entries, assumptions_dict)

    # 4. Fetch share price
    company = db.query(Company).filter(Company.id == company_id).first()
    if company:
        share_price = get_latest_share_price(company.ticker)
        result["current_share_price"] = share_price

    # 5. Fetch non-operating items (Bridge from Enterprise Value to Equity Value)
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

    # Sort by time period to get the most recent one
    non_op_classification = None
    if non_op_classifications:
        # Use existing helper to sort
        # We need to rely on the document's time period

        # Sort key wrapper
        def sort_key(nop):
            tp = nop.document.time_period if nop.document else ""
            return time_period_sort_key(tp)

        non_op_classifications.sort(key=sort_key)
        non_op_classification = non_op_classifications[-1]

    bridge_items = {
        "cash": 0.0,
        "short_term_investments": 0.0,
        "other_financial_physical_assets": 0.0,
        "debt": 0.0,
        "other_financial_liabilities": 0.0,
        "preferred_equity": 0.0,
        "minority_interest": 0.0,
    }

    if non_op_classification:
        # Create lookup map
        bs_values = {}
        if non_op_classification.document and non_op_classification.document.balance_sheet:
            for bsi in non_op_classification.document.balance_sheet.line_items:
                bs_values[bsi.line_name] = bsi.line_value

        # Load items
        items = (
            db.query(NonOperatingClassificationItem)
            .filter(NonOperatingClassificationItem.classification_id == non_op_classification.id)
            .all()
        )
        for item in items:
            cat = item.category
            val = float(bs_values.get(item.line_name) or 0)
            if cat in bridge_items:
                bridge_items[cat] += val

    # Calculate Equity Value
    # Equity Value = Enterprise Value + Cash + STI + OtherAssets - Debt - OtherLiabilities - Preferred - Minority
    enterprise_value = float(result.get("enterprise_value", 0))

    equity_value = (
        enterprise_value
        + bridge_items["cash"]
        + bridge_items["short_term_investments"]
        + bridge_items["other_financial_physical_assets"]
        - bridge_items["debt"]
        - bridge_items["other_financial_liabilities"]
        - bridge_items["preferred_equity"]
        - bridge_items["minority_interest"]
    )

    # Get Diluted Shares Outstanding from assumptions first, then fall back to historical entry
    diluted_shares = 0.0
    if assumption and assumption.diluted_shares_outstanding:
        diluted_shares = float(assumption.diluted_shares_outstanding)
    elif historical_entries:
        latest = historical_entries[-1]
        diluted_shares = float(latest.get("diluted_shares_outstanding") or 0)

    fair_value = 0.0
    if diluted_shares > 0:
        fair_value = equity_value / diluted_shares

    percent_undervalued = 0.0
    current_share_price = result.get("current_share_price")
    if current_share_price and float(current_share_price) > 0:
        cp = float(current_share_price)
        # Undervalued = (Fair - Current) / Current  ?? Or just (Fair / Current) - 1
        # "Percent Undervalued": if Fair=150, Current=100 -> 50% Undervalued.
        # if Fair=80, Current=100 -> -20% Undervalued (or 20% Overvalued).
        percent_undervalued = (fair_value - cp) / cp

    result["bridge_items"] = bridge_items
    result["equity_value"] = equity_value
    result["diluted_shares_outstanding"] = diluted_shares
    result["fair_value_per_share"] = fair_value
    result["percent_undervalued"] = percent_undervalued

    return result


@router.post("/{company_id}/valuations", response_model=ValuationSchema)
async def save_valuation(
    company_id: str,
    valuation_data: ValuationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a valuation snapshot"""
    valuation = Valuation(
        id=str(uuid.uuid4()),
        company_id=company_id,
        user_id=current_user.id,
        fair_value=valuation_data.fair_value,
        share_price_at_time=valuation_data.share_price_at_time,
        percent_undervalued=valuation_data.percent_undervalued,
    )
    db.add(valuation)
    db.commit()
    db.refresh(valuation)

    # Enrich response with user email and name
    result = valuation.__dict__
    result["user_email"] = current_user.email
    result["user_name"] = f"{current_user.first_name} {current_user.last_name}".strip()
    return result


@router.get("/{company_id}/valuations", response_model=list[ValuationSchema])
async def list_valuations(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List saved valuations for a company"""
    valuations = (
        db.query(Valuation)
        .filter(Valuation.company_id == company_id)
        .options(selectinload(Valuation.user))
        .order_by(Valuation.date.desc())
        .all()
    )

    results = []
    for v in valuations:
        res = v.__dict__
        if v.user:
            res["user_email"] = v.user.email
            res["user_name"] = f"{v.user.first_name} {v.user.last_name}".strip()
        results.append(res)
    return results


@router.delete("/{company_id}/valuations/{valuation_id}")
async def delete_valuation(
    company_id: str,
    valuation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a saved valuation"""
    valuation = (
        db.query(Valuation)
        .filter(Valuation.id == valuation_id, Valuation.company_id == company_id)
        .first()
    )
    if not valuation:
        raise HTTPException(status_code=404, detail="Valuation not found")

    db.delete(valuation)
    db.commit()
    return {"ok": True}

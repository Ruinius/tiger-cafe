"""
Dashboard routes for visualizing global analysis
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.models.document import Document
from app.models.historical_calculation import HistoricalCalculation
from app.models.organic_growth import OrganicGrowth
from app.models.valuation import Valuation

router = APIRouter()

# Maximum number of historical periods to fetch for L4Q calculation
MAX_PERIODS_FOR_L4Q = 5


def _extract_growth_rate(organic_growth: OrganicGrowth | None) -> float | None:
    """Extract growth rate from OrganicGrowth, preferring organic over simple."""
    if not organic_growth:
        return None

    if organic_growth.organic_revenue_growth is not None:
        return float(organic_growth.organic_revenue_growth)
    elif organic_growth.simple_revenue_growth is not None:
        return float(organic_growth.simple_revenue_growth)

    return None


def _is_annual_period(doc: Document) -> bool:
    """Check if a document represents an annual/FY period."""
    if doc.time_period and doc.time_period.upper().startswith("FY"):
        return True
    if doc.document_type and "ANNUAL" in str(doc.document_type).upper():
        return True
    return False


@router.get("/charts")
async def get_dashboard_charts(db: Session = Depends(get_db)):
    """
    Get data for global dashboard charts:
    1. Valuation History (scatter plot of valuations over time)
    2. Rule of 40 (scatter plot of Growth vs Margin) - Uses L4Q (Last 4 Quarters) arithmetic mean
    """

    # 1. Valuation History
    valuations = (
        db.query(Valuation.date, Valuation.percent_undervalued, Company.ticker, Company.name)
        .join(Company)
        .filter(Valuation.percent_undervalued.isnot(None))
        .order_by(Valuation.date.asc())
        .all()
    )

    valuation_history = [
        {
            "date": v.date.isoformat() if v.date else None,
            "percent_undervalued": float(v.percent_undervalued),
            "ticker": v.ticker or v.name,
            "name": v.name,
        }
        for v in valuations
    ]

    # 2. Rule of 40 Data (L4Q Calculation)
    # Fetch all companies
    companies = db.query(Company).filter(Company.name != "Processing...").all()

    # Pre-fetch latest valuations for all companies to avoid N+1 queries
    latest_valuations = {}
    for val in (
        db.query(Valuation)
        .filter(Valuation.company_id.in_([c.id for c in companies]))
        .order_by(Valuation.company_id, Valuation.date.desc())
        .all()
    ):
        if val.company_id not in latest_valuations:
            latest_valuations[val.company_id] = val

    rule_of_40_data = []

    for company in companies:
        # Fetch recent documents with both profit and growth data
        data_rows = (
            db.query(Document, OrganicGrowth, HistoricalCalculation)
            .join(OrganicGrowth, Document.id == OrganicGrowth.document_id)
            .join(HistoricalCalculation, Document.id == HistoricalCalculation.document_id)
            .filter(Document.company_id == company.id)
            .filter(Document.period_end_date.isnot(None))
            .order_by(Document.period_end_date.desc())
            .limit(MAX_PERIODS_FOR_L4Q)
            .all()
        )

        if not data_rows:
            continue

        # Collect margins and growth rates (L4Q Average = arithmetic mean)
        margins = []
        growths = []
        using_fy = False
        latest_period_label = ""

        for i, (doc, og, hc) in enumerate(data_rows):
            if i == 0:
                latest_period_label = doc.period_end_date or doc.time_period or ""

            is_fy = _is_annual_period(doc)

            if is_fy:
                # Use FY data directly if it's the first record
                if not margins and not growths:
                    if hc and hc.ebita_margin is not None:
                        margins.append(float(hc.ebita_margin))

                    growth = _extract_growth_rate(og)
                    if growth is not None:
                        growths.append(growth)

                    using_fy = True
                    latest_period_label = doc.period_end_date or doc.time_period
                    break
                else:
                    # Don't mix FY with quarterly data
                    break
            else:
                # Collect up to 4 quarterly periods
                if len(margins) < 4 and hc and hc.ebita_margin is not None:
                    margins.append(float(hc.ebita_margin))

                if len(growths) < 4:
                    growth = _extract_growth_rate(og)
                    if growth is not None:
                        growths.append(growth)

                # Stop once we have 4 complete quarters
                if len(margins) >= 4 and len(growths) >= 4:
                    break

        # Skip if no valid data
        if not margins and not growths:
            continue

        # Calculate arithmetic means
        # IMPORTANT: Different storage formats!
        # - Margins are stored as decimals (0.15 = 15%) -> need * 100
        # - Growth rates are already stored as percentages (-2.1 = -2.1%) -> no conversion needed
        margin_pct = (sum(margins) / len(margins)) * 100 if margins else 0.0
        growth_pct = sum(growths) / len(growths) if growths else 0.0

        # Get valuation for color coding
        latest_val = latest_valuations.get(company.id)
        undervalued = (
            float(latest_val.percent_undervalued)
            if latest_val and latest_val.percent_undervalued is not None
            else 0.0
        )

        # Add suffix to indicate L4Q average (only for multiple quarters)
        period_suffix = (
            " (L4Q Avg)" if not using_fy and (len(margins) > 1 or len(growths) > 1) else ""
        )

        rule_of_40_data.append(
            {
                "ticker": company.ticker or company.name,
                "name": company.name,
                "margin": margin_pct,
                "growth": growth_pct,
                "undervalued": undervalued,
                "period": latest_period_label + period_suffix,
            }
        )

    return {"valuation_history": valuation_history, "rule_of_40": rule_of_40_data}

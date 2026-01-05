"""
Company routes
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.company import Company
from app.models.document import Document, DocumentType
from app.models.historical_calculation import HistoricalCalculation
from app.models.income_statement import IncomeStatement
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.company import Company as CompanySchema
from app.schemas.company import CompanyCreate
from app.schemas.company_historical_calculations import CompanyHistoricalCalculations
from app.utils.historical_calculations import get_revenue

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
    db_company = Company(id=str(uuid.uuid4()), name=company.name, ticker=company.ticker)
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

        revenue = (
            get_revenue(document.income_statement) if document.income_statement else None
        )
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
            "calculated_at": calc.calculated_at,
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
async def get_company_historical_calculations_test(
    company_id: str, db: Session = Depends(get_db)
):
    """Test endpoint for company historical calculations (no auth required)."""
    return await get_company_historical_calculations(company_id, db, current_user=None)

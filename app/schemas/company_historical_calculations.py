"""
Company-level historical calculations schemas
"""

from decimal import Decimal

from pydantic import BaseModel


class CompanyHistoricalCalculationEntry(BaseModel):
    time_period: str
    revenue: Decimal | None = None
    revenue_growth_yoy: Decimal | None = None
    ebita: Decimal | None = None
    ebita_margin: Decimal | None = None
    effective_tax_rate: Decimal | None = None
    adjusted_tax_rate: Decimal | None = None
    net_working_capital: Decimal | None = None
    net_long_term_operating_assets: Decimal | None = None
    invested_capital: Decimal | None = None
    capital_turnover: Decimal | None = None


class CompanyHistoricalCalculations(BaseModel):
    company_id: str
    currency: str | None = None
    unit: str | None = None
    entries: list[CompanyHistoricalCalculationEntry]

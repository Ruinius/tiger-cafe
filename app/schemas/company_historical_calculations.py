"""
Company-level historical calculations schemas
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CompanyHistoricalCalculationEntry(BaseModel):
    time_period: str
    period_end_date: date | None = None
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
    nopat: Decimal | None = None
    roic: Decimal | None = None
    organic_revenue_growth: Decimal | None = None
    marginal_capital_turnover: Decimal | None = None
    diluted_shares_outstanding: Decimal | None = None
    basic_shares_outstanding: Decimal | None = None
    simple_revenue_growth: Decimal | None = None


class CompanyHistoricalCalculations(BaseModel):
    company_id: str
    currency: str | None = None
    unit: str | None = None
    entries: list[CompanyHistoricalCalculationEntry]

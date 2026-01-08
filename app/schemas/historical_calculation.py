"""
Historical calculation schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class HistoricalCalculationBase(BaseModel):
    time_period: str | None = None
    currency: str | None = None
    unit: str | None = None  # "ones", "thousands", "millions", "billions", or "ten_thousands"
    net_working_capital: Decimal | None = None
    net_working_capital_breakdown: dict | None = None  # Breakdown of current assets and liabilities
    net_long_term_operating_assets: Decimal | None = None
    net_long_term_operating_assets_breakdown: dict | None = (
        None  # Breakdown of non-current assets and liabilities
    )
    invested_capital: Decimal | None = None
    capital_turnover: Decimal | None = None
    ebita: Decimal | None = None
    ebita_breakdown: dict | None = None  # Breakdown of EBITA calculation
    ebita_margin: Decimal | None = None
    effective_tax_rate: Decimal | None = None
    adjusted_tax_rate: Decimal | None = None
    adjusted_tax_rate_breakdown: dict | None = None  # Breakdown of Adjusted Tax Rate calculation
    nopat: Decimal | None = None
    roic: Decimal | None = None
    calculation_notes: str | None = None


class HistoricalCalculationCreate(HistoricalCalculationBase):
    document_id: str


class HistoricalCalculation(HistoricalCalculationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    calculated_at: datetime

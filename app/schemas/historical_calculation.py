"""
Historical calculation schemas
"""

from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class HistoricalCalculationBase(BaseModel):
    time_period: Optional[str] = None
    currency: Optional[str] = None
    unit: Optional[str] = None  # "ones", "thousands", "millions", "billions", or "ten_thousands"
    net_working_capital: Optional[Decimal] = None
    net_long_term_operating_assets: Optional[Decimal] = None
    invested_capital: Optional[Decimal] = None
    capital_turnover: Optional[Decimal] = None
    ebita: Optional[Decimal] = None
    ebita_margin: Optional[Decimal] = None
    effective_tax_rate: Optional[Decimal] = None
    calculation_notes: Optional[str] = None


class HistoricalCalculationCreate(HistoricalCalculationBase):
    document_id: str


class HistoricalCalculation(HistoricalCalculationBase):
    id: str
    document_id: str
    calculated_at: datetime
    
    class Config:
        from_attributes = True


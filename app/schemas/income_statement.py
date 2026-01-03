"""
Income statement schemas
"""

from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


class IncomeStatementLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    line_category: Optional[str] = None
    is_operating: Optional[bool] = None
    line_order: int


class IncomeStatementLineItemCreate(IncomeStatementLineItemBase):
    pass


class IncomeStatementLineItem(IncomeStatementLineItemBase):
    id: str
    income_statement_id: str
    
    class Config:
        from_attributes = True


class IncomeStatementBase(BaseModel):
    time_period: Optional[str] = None
    currency: Optional[str] = None


class IncomeStatementCreate(IncomeStatementBase):
    document_id: str
    line_items: List[IncomeStatementLineItemCreate]


class IncomeStatement(IncomeStatementBase):
    id: str
    document_id: str
    revenue_prior_year: Optional[Decimal] = None
    revenue_growth_yoy: Optional[Decimal] = None
    basic_shares_outstanding: Optional[Decimal] = None
    diluted_shares_outstanding: Optional[Decimal] = None
    amortization: Optional[Decimal] = None
    is_valid: bool
    validation_errors: Optional[str] = None
    extraction_date: datetime
    line_items: List[IncomeStatementLineItem] = []
    
    class Config:
        from_attributes = True


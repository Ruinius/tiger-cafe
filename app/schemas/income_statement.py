"""
Income statement schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class IncomeStatementLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    line_category: str | None = None
    is_operating: bool | None = None
    line_order: int


class IncomeStatementLineItemCreate(IncomeStatementLineItemBase):
    pass


class IncomeStatementLineItem(IncomeStatementLineItemBase):
    id: str
    income_statement_id: str

    class Config:
        from_attributes = True


class IncomeStatementBase(BaseModel):
    time_period: str | None = None
    currency: str | None = None
    unit: str | None = None  # "ones", "thousands", "millions", "billions", or "ten_thousands"


class IncomeStatementCreate(IncomeStatementBase):
    document_id: str
    line_items: list[IncomeStatementLineItemCreate]


class IncomeStatement(IncomeStatementBase):
    id: str
    document_id: str
    revenue_prior_year: Decimal | None = None
    revenue_prior_year_unit: str | None = None
    revenue_growth_yoy: Decimal | None = None
    basic_shares_outstanding: Decimal | None = None
    basic_shares_outstanding_unit: str | None = None
    diluted_shares_outstanding: Decimal | None = None
    diluted_shares_outstanding_unit: str | None = None
    amortization: Decimal | None = None
    amortization_unit: str | None = None
    is_valid: bool
    validation_errors: str | None = None
    extraction_date: datetime
    line_items: list[IncomeStatementLineItem] = []

    class Config:
        from_attributes = True

"""
Balance sheet schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BalanceSheetLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    line_category: str | None = None
    standardized_name: str | None = None
    is_calculated: bool | None = None
    is_operating: bool | None = None
    line_order: int


class BalanceSheetLineItemCreate(BalanceSheetLineItemBase):
    pass


class BalanceSheetLineItem(BalanceSheetLineItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    balance_sheet_id: str


class BalanceSheetBase(BaseModel):
    time_period: str | None = None
    currency: str | None = None
    unit: str | None = None  # "ones", "thousands", "millions", "billions", or "ten_thousands"


class BalanceSheetCreate(BalanceSheetBase):
    document_id: str
    line_items: list[BalanceSheetLineItemCreate]


class BalanceSheet(BalanceSheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    is_valid: bool
    validation_errors: str | None = None
    extraction_date: datetime
    line_items: list[BalanceSheetLineItem] = []

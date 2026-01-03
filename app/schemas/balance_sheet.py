"""
Balance sheet schemas
"""

from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


class BalanceSheetLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    line_category: Optional[str] = None
    is_operating: Optional[bool] = None
    line_order: int


class BalanceSheetLineItemCreate(BalanceSheetLineItemBase):
    pass


class BalanceSheetLineItem(BalanceSheetLineItemBase):
    id: str
    balance_sheet_id: str
    
    class Config:
        from_attributes = True


class BalanceSheetBase(BaseModel):
    time_period: Optional[str] = None
    currency: Optional[str] = None
    unit: Optional[str] = None  # "ones", "thousands", "millions", "billions", or "ten_thousands"


class BalanceSheetCreate(BalanceSheetBase):
    document_id: str
    line_items: List[BalanceSheetLineItemCreate]


class BalanceSheet(BalanceSheetBase):
    id: str
    document_id: str
    is_valid: bool
    validation_errors: Optional[str] = None
    extraction_date: datetime
    line_items: List[BalanceSheetLineItem] = []
    
    class Config:
        from_attributes = True


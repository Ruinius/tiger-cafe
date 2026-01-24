"""
Amortization schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AmortizationLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    unit: str | None = None
    is_operating: bool | None = None
    category: str | None = None
    line_order: int


class AmortizationLineItemCreate(AmortizationLineItemBase):
    pass


class AmortizationLineItem(AmortizationLineItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amortization_id: str


class AmortizationBase(BaseModel):
    time_period: str | None = None
    period_end_date: str | None = None
    currency: str | None = None
    chunk_index: int | None = None
    is_valid: bool = False
    validation_errors: str | None = None


class AmortizationCreate(AmortizationBase):
    document_id: str
    line_items: list[AmortizationLineItemCreate]


class Amortization(AmortizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime | None = None
    line_items: list[AmortizationLineItem] = []

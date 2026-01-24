"""
GAAP Reconciliation schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class GAAPReconciliationLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    unit: str | None = None
    is_operating: bool | None = None
    category: str | None = None
    line_order: int


class GAAPReconciliationLineItemCreate(GAAPReconciliationLineItemBase):
    pass


class GAAPReconciliationLineItem(GAAPReconciliationLineItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gaap_reconciliation_id: str


class GAAPReconciliationBase(BaseModel):
    time_period: str | None = None
    period_end_date: str | None = None
    currency: str | None = None
    chunk_index: int | None = None
    is_valid: bool = False
    validation_errors: str | None = None


class GAAPReconciliationCreate(GAAPReconciliationBase):
    document_id: str
    line_items: list[GAAPReconciliationLineItemCreate]


class GAAPReconciliation(GAAPReconciliationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime | None = None
    line_items: list[GAAPReconciliationLineItem] = []

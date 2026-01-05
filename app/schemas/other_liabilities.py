"""
Other liabilities schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OtherLiabilitiesLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    unit: str | None = None
    is_operating: bool | None = None
    category: str | None = None
    line_order: int


class OtherLiabilitiesLineItemCreate(OtherLiabilitiesLineItemBase):
    pass


class OtherLiabilitiesLineItem(OtherLiabilitiesLineItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    other_liabilities_id: str


class OtherLiabilitiesBase(BaseModel):
    time_period: str | None = None
    currency: str | None = None
    chunk_index: int | None = None
    is_valid: bool = False
    validation_errors: str | None = None


class OtherLiabilitiesCreate(OtherLiabilitiesBase):
    document_id: str
    line_items: list[OtherLiabilitiesLineItemCreate]


class OtherLiabilities(OtherLiabilitiesBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime
    line_items: list[OtherLiabilitiesLineItem] = []

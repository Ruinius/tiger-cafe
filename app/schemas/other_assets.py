"""
Other assets schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OtherAssetsLineItemBase(BaseModel):
    line_name: str
    line_value: Decimal
    unit: str | None = None
    is_operating: bool | None = None
    category: str | None = None
    line_order: int


class OtherAssetsLineItemCreate(OtherAssetsLineItemBase):
    pass


class OtherAssetsLineItem(OtherAssetsLineItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    other_assets_id: str


class OtherAssetsBase(BaseModel):
    time_period: str | None = None
    period_end_date: str | None = None
    currency: str | None = None
    chunk_index: int | None = None
    is_valid: bool = False
    validation_errors: str | None = None


class OtherAssetsCreate(OtherAssetsBase):
    document_id: str
    line_items: list[OtherAssetsLineItemCreate]


class OtherAssets(OtherAssetsBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime | None = None
    line_items: list[OtherAssetsLineItem] = []

"""
Non-operating classification schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NonOperatingClassificationItemBase(BaseModel):
    line_name: str
    category: str | None = None
    source: str | None = None
    line_order: int


class NonOperatingClassificationItemCreate(NonOperatingClassificationItemBase):
    pass


class NonOperatingClassificationItem(NonOperatingClassificationItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    classification_id: str


class NonOperatingClassificationBase(BaseModel):
    time_period: str | None = None


class NonOperatingClassificationCreate(NonOperatingClassificationBase):
    document_id: str
    line_items: list[NonOperatingClassificationItemCreate]


class NonOperatingClassification(NonOperatingClassificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime
    line_items: list[NonOperatingClassificationItem] = []

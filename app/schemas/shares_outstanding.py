"""
Shares Outstanding schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SharesOutstandingBase(BaseModel):
    time_period: str | None = None
    period_end_date: str | None = None
    basic_shares_outstanding: Decimal | None = None
    basic_shares_outstanding_unit: str | None = None
    diluted_shares_outstanding: Decimal | None = None
    diluted_shares_outstanding_unit: str | None = None


class SharesOutstandingCreate(SharesOutstandingBase):
    document_id: str


class SharesOutstanding(SharesOutstandingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime | None = None

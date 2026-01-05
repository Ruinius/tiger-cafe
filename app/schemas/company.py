"""
Company schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    name: str
    ticker: str | None = None


class CompanyCreate(CompanyBase):
    pass


class Company(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime | None = None
    document_count: int | None = None  # Number of documents for this company

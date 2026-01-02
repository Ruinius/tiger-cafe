"""
Company schemas
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CompanyBase(BaseModel):
    name: str
    ticker: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class Company(CompanyBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    document_count: Optional[int] = None  # Number of documents for this company

    class Config:
        from_attributes = True


"""
Financial Metric schemas
"""

from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional


class FinancialMetricBase(BaseModel):
    metric_name: str
    period: str
    period_date: Optional[date] = None
    value: float
    unit: Optional[str] = None


class FinancialMetricCreate(FinancialMetricBase):
    company_id: str
    source_document_id: Optional[str] = None


class FinancialMetric(FinancialMetricBase):
    id: str
    company_id: str
    source_document_id: Optional[str] = None
    calculated_at: datetime

    class Config:
        from_attributes = True


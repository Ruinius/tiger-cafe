"""
Financial Metric schemas
"""

from datetime import date, datetime

from pydantic import BaseModel


class FinancialMetricBase(BaseModel):
    metric_name: str
    period: str
    period_date: date | None = None
    value: float
    unit: str | None = None


class FinancialMetricCreate(FinancialMetricBase):
    company_id: str
    source_document_id: str | None = None


class FinancialMetric(FinancialMetricBase):
    id: str
    company_id: str
    source_document_id: str | None = None
    calculated_at: datetime

    class Config:
        from_attributes = True

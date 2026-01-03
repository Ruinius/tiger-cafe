"""
Analysis Result schemas
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AnalysisResultBase(BaseModel):
    analysis_type: str
    assumptions: dict[str, Any] | None = None
    results: dict[str, Any]
    summary: str | None = None


class AnalysisResultCreate(AnalysisResultBase):
    company_id: str


class AnalysisResult(AnalysisResultBase):
    id: str
    company_id: str
    completed_at: datetime

    class Config:
        from_attributes = True

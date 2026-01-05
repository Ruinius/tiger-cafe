"""
Analysis Result schemas
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisResultBase(BaseModel):
    analysis_type: str
    assumptions: dict[str, Any] | None = None
    results: dict[str, Any]
    summary: str | None = None


class AnalysisResultCreate(AnalysisResultBase):
    company_id: str


class AnalysisResult(AnalysisResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    completed_at: datetime

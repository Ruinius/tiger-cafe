"""
Analysis Result schemas
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class AnalysisResultBase(BaseModel):
    analysis_type: str
    assumptions: Optional[Dict[str, Any]] = None
    results: Dict[str, Any]
    summary: Optional[str] = None


class AnalysisResultCreate(AnalysisResultBase):
    company_id: str


class AnalysisResult(AnalysisResultBase):
    id: str
    company_id: str
    completed_at: datetime

    class Config:
        from_attributes = True


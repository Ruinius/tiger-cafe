"""
Qualitative assessment schemas
"""

from datetime import datetime

from pydantic import BaseModel


class QualitativeAssessmentBase(BaseModel):
    economic_moat_label: str | None = None
    economic_moat_rationale: str | None = None
    near_term_growth_label: str | None = None
    near_term_growth_rationale: str | None = None
    revenue_predictability_label: str | None = None
    revenue_predictability_rationale: str | None = None


class QualitativeAssessmentCreate(QualitativeAssessmentBase):
    pass


class QualitativeAssessment(QualitativeAssessmentBase):
    id: str
    company_id: str
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

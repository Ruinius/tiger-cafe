"""
Qualitative assessment API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.qualitative_assessment import QualitativeAssessment
from app.services.qualitative_service import get_qualitative_assessment, run_qualitative_assessment

router = APIRouter()


@router.get("/{company_id}/qualitative-assessment", response_model=QualitativeAssessment | None)
async def get_assessment(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the qualitative assessment for a company.
    """
    return get_qualitative_assessment(db, company_id)


@router.post("/{company_id}/qualitative-assessment/rerun", response_model=QualitativeAssessment)
async def rerun_assessment(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a re-run of the qualitative assessment agent.
    """
    try:
        return run_qualitative_assessment(db, company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

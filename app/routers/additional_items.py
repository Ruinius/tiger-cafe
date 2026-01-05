"""
Additional financial items routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.amortization import Amortization
from app.models.document import Document
from app.models.non_operating_classification import NonOperatingClassification
from app.models.organic_growth import OrganicGrowth
from app.models.other_assets import OtherAssets
from app.models.other_liabilities import OtherLiabilities
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.amortization import Amortization as AmortizationSchema
from app.schemas.non_operating_classification import (
    NonOperatingClassification as NonOperatingClassificationSchema,
)
from app.schemas.organic_growth import OrganicGrowth as OrganicGrowthSchema
from app.schemas.other_assets import OtherAssets as OtherAssetsSchema
from app.schemas.other_liabilities import OtherLiabilities as OtherLiabilitiesSchema

router = APIRouter()


def _get_document_or_404(document_id: str, db: Session) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/amortization")
async def get_amortization(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_document_or_404(document_id, db)
    amortization = (
        db.query(Amortization).filter(Amortization.document_id == document_id).first()
    )
    if not amortization:
        raise HTTPException(status_code=404, detail="Amortization not found for this document")

    amortization_schema = AmortizationSchema.model_validate(amortization)
    return {"status": "exists", "data": amortization_schema.model_dump()}


@router.get("/{document_id}/organic-growth")
async def get_organic_growth(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_document_or_404(document_id, db)
    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if not organic_growth:
        raise HTTPException(status_code=404, detail="Organic growth data not found")

    organic_growth_schema = OrganicGrowthSchema.model_validate(organic_growth)
    return {"status": "exists", "data": organic_growth_schema.model_dump()}


@router.get("/{document_id}/other-assets")
async def get_other_assets(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_document_or_404(document_id, db)
    other_assets = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    if not other_assets:
        raise HTTPException(status_code=404, detail="Other assets not found for this document")

    other_assets_schema = OtherAssetsSchema.model_validate(other_assets)
    return {"status": "exists", "data": other_assets_schema.model_dump()}


@router.get("/{document_id}/other-liabilities")
async def get_other_liabilities(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_document_or_404(document_id, db)
    other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if not other_liabilities:
        raise HTTPException(
            status_code=404, detail="Other liabilities not found for this document"
        )

    other_liabilities_schema = OtherLiabilitiesSchema.model_validate(other_liabilities)
    return {"status": "exists", "data": other_liabilities_schema.model_dump()}


@router.get("/{document_id}/non-operating-classification")
async def get_non_operating_classification(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    _get_document_or_404(document_id, db)
    classification = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if not classification:
        raise HTTPException(
            status_code=404, detail="Non-operating classification not found for this document"
        )

    classification_schema = NonOperatingClassificationSchema.model_validate(classification)
    return {"status": "exists", "data": classification_schema.model_dump()}

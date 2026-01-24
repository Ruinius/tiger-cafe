"""
Additional financial items routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.amortization import Amortization
from app.models.document import Document
from app.models.gaap_reconciliation import GAAPReconciliation
from app.models.non_operating_classification import NonOperatingClassification
from app.models.organic_growth import OrganicGrowth
from app.models.other_assets import OtherAssets
from app.models.other_liabilities import OtherLiabilities
from app.models.shares_outstanding import SharesOutstanding
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.amortization import Amortization as AmortizationSchema
from app.schemas.gaap_reconciliation import GAAPReconciliation as GAAPReconciliationSchema
from app.schemas.organic_growth import OrganicGrowth as OrganicGrowthSchema
from app.schemas.other_assets import OtherAssets as OtherAssetsSchema
from app.schemas.other_liabilities import OtherLiabilities as OtherLiabilitiesSchema
from app.schemas.shares_outstanding import SharesOutstanding as SharesOutstandingSchema

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
    amortization = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    if not amortization:
        raise HTTPException(status_code=404, detail="Amortization not found for this document")

    amortization_schema = AmortizationSchema.model_validate(amortization)
    return {"status": "exists", "data": amortization_schema.model_dump()}


@router.get("/{document_id}/organic-growth")
async def get_organic_growth(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    print(f"[DEBUG] Fetching Organic Growth for doc: {document_id}")
    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if not organic_growth:
        print(f"[DEBUG] Organic Growth NOT found for doc: {document_id}")
        raise HTTPException(status_code=404, detail=f"DEBUG_OG_NOT_FOUND_FOR_{document_id}")
    print(f"[DEBUG] Organic Growth FOUND for doc: {document_id}")

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
        raise HTTPException(status_code=404, detail="Other liabilities not found for this document")

    other_liabilities_schema = OtherLiabilitiesSchema.model_validate(other_liabilities)
    return {"status": "exists", "data": other_liabilities_schema.model_dump()}


@router.get("/{document_id}/non-operating-classification")
async def get_non_operating_classification(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    from app.models.balance_sheet import BalanceSheet

    _get_document_or_404(document_id, db)

    # Get the classification
    print(f"[DEBUG] Fetching classification for doc: {document_id}")
    classification = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if not classification:
        print(f"[DEBUG] Classification NOT found for doc: {document_id}")
        raise HTTPException(
            status_code=404, detail="Non-operating classification not found for this document"
        )
    print(f"[DEBUG] Classification FOUND for doc: {document_id}")

    # Get the balance sheet to join with
    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()

    if not balance_sheet:
        raise HTTPException(status_code=404, detail="Balance sheet not found for this document")

    # Create a lookup map of balance sheet items by line_name
    bs_items_map = {item.line_name: item for item in balance_sheet.line_items}

    # Enrich classification items with balance sheet data
    enriched_items = []
    for class_item in classification.line_items:
        bs_item = bs_items_map.get(class_item.line_name)
        if bs_item:
            enriched_items.append(
                {
                    "line_name": class_item.line_name,
                    "standardized_name": bs_item.standardized_name,
                    "line_value": float(bs_item.line_value) if bs_item.line_value else None,
                    "unit": balance_sheet.unit,
                    "category": class_item.category,
                    "is_calculated": bs_item.is_calculated,
                    "is_operating": bs_item.is_operating,
                    "source": class_item.source,
                    "line_order": class_item.line_order,
                }
            )

    return {
        "status": "exists",
        "data": {
            "id": classification.id,
            "document_id": classification.document_id,
            "time_period": classification.time_period,
            "period_end_date": classification.period_end_date,
            "currency": balance_sheet.currency,
            "unit": balance_sheet.unit,
            "extraction_date": classification.extraction_date.isoformat()
            if classification.extraction_date
            else None,
            "line_items": enriched_items,
        },
    }


@router.get("/{document_id}/shares")
async def get_shares_outstanding(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get shares outstanding data for a document."""
    print(f"[DEBUG] Fetching Shares for doc: {document_id}")
    shares = (
        db.query(SharesOutstanding).filter(SharesOutstanding.document_id == document_id).first()
    )

    if not shares:
        print(f"[DEBUG] Shares NOT found for doc: {document_id}")
        raise HTTPException(status_code=404, detail=f"DEBUG_SHARES_NOT_FOUND_FOR_{document_id}")
    print(f"[DEBUG] Shares FOUND for doc: {document_id}")

    shares_schema = SharesOutstandingSchema.model_validate(shares)
    return {"status": "exists", "data": shares_schema.model_dump()}


@router.get("/{document_id}/gaap-reconciliation")
async def get_gaap_reconciliation(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get GAAP reconciliation data for a document (earnings announcements only)."""
    _get_document_or_404(document_id, db)

    print(f"[DEBUG] Fetching GAAP recon for doc: {document_id}")
    gaap_recon = (
        db.query(GAAPReconciliation).filter(GAAPReconciliation.document_id == document_id).first()
    )

    if not gaap_recon:
        print(f"[DEBUG] GAAP recon NOT found for doc: {document_id}")
        raise HTTPException(status_code=404, detail=f"DEBUG_GAAP_NOT_FOUND_FOR_{document_id}")
    print(f"[DEBUG] GAAP recon FOUND for doc: {document_id}")

    gaap_recon_schema = GAAPReconciliationSchema.model_validate(gaap_recon)
    return {"status": "exists", "data": gaap_recon_schema.model_dump()}

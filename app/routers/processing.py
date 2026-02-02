"""
Processing Router

Orchestrates the extraction pipeline (HTTP layer only).
Receives HTTP requests and delegates to the service layer.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.extraction_orchestrator import (
    retry_milestone,
    run_analysis_pipeline,
    run_full_extraction_pipeline,
    run_ingestion_pipeline,
)
from app.utils.financial_statement_progress import get_progress

router = APIRouter()


@router.post("/documents/{document_id}/ingest")
async def trigger_ingestion(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers Phase 1 (Classify → Index) after upload.

    This endpoint is called by the frontend after a successful file upload.
    """
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Trigger ingestion in background
    background_tasks.add_task(run_ingestion_pipeline, document_id, db)

    return {
        "status": "started",
        "document_id": document_id,
        "message": "Ingestion pipeline started",
    }


@router.post("/documents/{document_id}/extract")
async def trigger_extraction(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers Phases 2-3 (Balance Sheet → Income Statement → Additional Items → Classification).

    This can be called manually to re-run extraction without re-ingesting.
    """
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Trigger extraction in background
    background_tasks.add_task(run_full_extraction_pipeline, document_id, db)

    return {
        "status": "started",
        "document_id": document_id,
        "message": "Extraction pipeline started",
    }


@router.post("/documents/{document_id}/analyze")
async def trigger_analysis(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers Phase 4 (Analysis: Historical Data → Assumptions → Intrinsic Value).

    User-triggered analysis for company-level calculations.
    """
    # Verify document exists and get company_id
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.company_id:
        raise HTTPException(status_code=400, detail="Document has no associated company")

    # Trigger analysis in background
    background_tasks.add_task(run_analysis_pipeline, document.company_id, document_id, db)

    return {
        "status": "started",
        "document_id": document_id,
        "company_id": document.company_id,
        "message": "Analysis pipeline started",
    }


@router.post("/documents/{document_id}/rerun")
async def rerun_pipeline(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-runs the entire pipeline (clears existing data first).

    This is useful when extraction failed or needs to be redone.
    """
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clear existing extracted data
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem

    # Delete balance sheet
    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    if balance_sheet:
        db.query(BalanceSheetLineItem).filter(
            BalanceSheetLineItem.balance_sheet_id == balance_sheet.id
        ).delete()
        db.delete(balance_sheet)

    # Delete income statement
    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    if income_statement:
        db.query(IncomeStatementLineItem).filter(
            IncomeStatementLineItem.income_statement_id == income_statement.id
        ).delete()
        db.delete(income_statement)

    # Delete amortization
    amortization = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    if amortization:
        db.query(AmortizationLineItem).filter(
            AmortizationLineItem.amortization_id == amortization.id
        ).delete()
        db.delete(amortization)

    # Delete organic growth
    db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).delete()

    # Delete other assets
    other_assets = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    if other_assets:
        db.query(OtherAssetsLineItem).filter(
            OtherAssetsLineItem.other_assets_id == other_assets.id
        ).delete()
        db.delete(other_assets)

    # Delete other liabilities
    other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if other_liabilities:
        db.query(OtherLiabilitiesLineItem).filter(
            OtherLiabilitiesLineItem.other_liabilities_id == other_liabilities.id
        ).delete()
        db.delete(other_liabilities)

    # Delete classification
    classification = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if classification:
        db.query(NonOperatingClassificationItem).filter(
            NonOperatingClassificationItem.classification_id == classification.id
        ).delete()
        db.delete(classification)

    # Delete historical calculations
    db.query(HistoricalCalculation).filter(
        HistoricalCalculation.document_id == document_id
    ).delete()

    # Delete cached embeddings/index to force re-indexing
    from app.utils.document_indexer import delete_chunk_embeddings

    try:
        delete_chunk_embeddings(document_id)
    except Exception as e:
        print(f"Warning: Failed to delete chunk embeddings: {e}")

    db.commit()

    # Reset progress tracking
    from app.utils.financial_statement_progress import reset_all_milestones

    reset_all_milestones(document_id)

    # Update document status to indicate processing immediately
    from app.models.document import ProcessingStatus
    from app.models.document_status import DocumentStatus

    document.status = DocumentStatus.PENDING
    document.analysis_status = ProcessingStatus.PENDING
    document.indexing_status = ProcessingStatus.PENDING
    db.commit()

    # Trigger full pipeline (including ingestion)
    background_tasks.add_task(run_ingestion_pipeline, document_id, db)

    return {
        "status": "started",
        "document_id": document_id,
        "message": "Pipeline restarted (existing data cleared)",
    }


@router.post("/documents/{document_id}/retry/{milestone}")
async def retry_failed_milestone(
    document_id: str,
    milestone: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retries a specific failed milestone (e.g., GAAP_RECONCILIATION).
    """
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Trigger retry in background
    background_tasks.add_task(retry_milestone, document_id, milestone, db)

    return {
        "status": "started",
        "document_id": document_id,
        "milestone": milestone,
        "message": f"Retrying milestone: {milestone}",
    }


@router.get("/documents/{document_id}/status")
async def get_processing_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns current granular progress for a document.

    This provides a snapshot of the current processing state.
    For real-time updates, use the SSE stream endpoint.
    """
    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get progress from the progress tracking system
    progress = get_progress(document_id)

    if not progress:
        # Fallback: Check if data exists in DB (handling server restart case)
        # This ensures that documents processed before a server restart can still be viewed
        from app.models.balance_sheet import BalanceSheet
        from app.models.income_statement import IncomeStatement

        has_bs = (
            db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
            is not None
        )
        has_is = (
            db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
            is not None
        )

        if has_bs or has_is:
            # Reconstruct a "completed" progress state
            milestones = {}
            if has_bs:
                milestones["balance_sheet"] = {
                    "status": "completed",
                    "message": "Restored from database",
                    "logs": [],
                }
            if has_is:
                milestones["income_statement"] = {
                    "status": "completed",
                    "message": "Restored from database",
                    "logs": [],
                }
                # If we have IS, we typically also have shares, etc.
                # Mark them as completed so the frontend attempts to fetch them
                milestones["shares_outstanding"] = {"status": "completed"}
                milestones["organic_growth"] = {"status": "completed"}
                milestones["gaap_reconciliation"] = {"status": "completed"}
                milestones["amortization"] = {"status": "completed"}
                milestones["other_assets"] = {"status": "completed"}
                milestones["other_liabilities"] = {"status": "completed"}
                milestones["classifying_non_operating_items"] = {"status": "completed"}

            return {
                "document_id": document_id,
                "status": "completed",
                "milestones": milestones,
                "logs": [
                    {
                        "message": "Progress logic restored from existing database records",
                        "timestamp": None,
                    }
                ],
            }

        return {
            "document_id": document_id,
            "status": "not_started",
            "milestones": {},
        }

    return {
        "document_id": document_id,
        "status": "in_progress"
        if any(m.get("status") == "in_progress" for m in progress.get("milestones", {}).values())
        else "completed",
        "milestones": progress.get("milestones", {}),
        "logs": progress.get("logs", []),
    }

"""
Balance sheet CRUD routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
from app.models.document import Document, ProcessingStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.balance_sheet import BalanceSheet as BalanceSheetSchema

router = APIRouter()


@router.delete("/{document_id}/financial-statements")
async def delete_financial_statements(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Delete all financial statements (balance sheet and income statement) for a document"""
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
    from app.utils.financial_statement_progress import clear_progress

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete balance sheet and its line items
    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    if balance_sheet:
        # Delete line items (cascade should handle this, but being explicit)
        db.query(BalanceSheetLineItem).filter(
            BalanceSheetLineItem.balance_sheet_id == balance_sheet.id
        ).delete()
        db.delete(balance_sheet)

    # Delete income statement and its line items
    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    if income_statement:
        # Delete line items (cascade should handle this, but being explicit)
        db.query(IncomeStatementLineItem).filter(
            IncomeStatementLineItem.income_statement_id == income_statement.id
        ).delete()
        db.delete(income_statement)

    amortization = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    if amortization:
        db.query(AmortizationLineItem).filter(
            AmortizationLineItem.amortization_id == amortization.id
        ).delete()
        db.delete(amortization)

    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if organic_growth:
        db.delete(organic_growth)

    other_assets = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    if other_assets:
        db.query(OtherAssetsLineItem).filter(
            OtherAssetsLineItem.other_assets_id == other_assets.id
        ).delete()
        db.delete(other_assets)

    other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if other_liabilities:
        db.query(OtherLiabilitiesLineItem).filter(
            OtherLiabilitiesLineItem.other_liabilities_id == other_liabilities.id
        ).delete()
        db.delete(other_liabilities)

    non_operating = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if non_operating:
        db.query(NonOperatingClassificationItem).filter(
            NonOperatingClassificationItem.classification_id == non_operating.id
        ).delete()
        db.delete(non_operating)

    # Clear progress tracking
    clear_progress(document_id)

    # Reset document analysis status
    document.analysis_status = ProcessingStatus.PENDING
    document.processed_at = None

    db.commit()

    return {"message": "Financial statements deleted successfully", "document_id": document_id}


@router.delete("/{document_id}/financial-statements/test")
async def delete_financial_statements_test(document_id: str, db: Session = Depends(get_db)):
    """TEST ENDPOINT: Delete all financial statements without authentication"""
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
    from app.utils.financial_statement_progress import clear_progress

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete balance sheet and its line items
    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    if balance_sheet:
        # Delete line items (cascade should handle this, but being explicit)
        db.query(BalanceSheetLineItem).filter(
            BalanceSheetLineItem.balance_sheet_id == balance_sheet.id
        ).delete()
        db.delete(balance_sheet)

    # Delete income statement and its line items
    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    if income_statement:
        # Delete line items (cascade should handle this, but being explicit)
        db.query(IncomeStatementLineItem).filter(
            IncomeStatementLineItem.income_statement_id == income_statement.id
        ).delete()
        db.delete(income_statement)

    amortization = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    if amortization:
        db.query(AmortizationLineItem).filter(
            AmortizationLineItem.amortization_id == amortization.id
        ).delete()
        db.delete(amortization)

    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if organic_growth:
        db.delete(organic_growth)

    other_assets = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    if other_assets:
        db.query(OtherAssetsLineItem).filter(
            OtherAssetsLineItem.other_assets_id == other_assets.id
        ).delete()
        db.delete(other_assets)

    other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if other_liabilities:
        db.query(OtherLiabilitiesLineItem).filter(
            OtherLiabilitiesLineItem.other_liabilities_id == other_liabilities.id
        ).delete()
        db.delete(other_liabilities)

    non_operating = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if non_operating:
        db.query(NonOperatingClassificationItem).filter(
            NonOperatingClassificationItem.classification_id == non_operating.id
        ).delete()
        db.delete(non_operating)

    # Clear progress tracking
    clear_progress(document_id)

    # Reset document analysis status
    document.analysis_status = ProcessingStatus.PENDING
    document.processed_at = None

    db.commit()

    return {"message": "Financial statements deleted successfully", "document_id": document_id}


@router.get("/{document_id}/balance-sheet")
async def get_balance_sheet(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get balance sheet data for a document.
    Returns three possible states:
    1. Balance sheet exists - returns balance sheet data
    2. Processing - returns processing status with milestones
    3. Does not exist and not processing - returns 404
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()

    # State 1: Balance sheet exists
    if balance_sheet:
        # Convert to schema for proper serialization
        balance_sheet_schema = BalanceSheetSchema.model_validate(balance_sheet)
        return {"status": "exists", "data": balance_sheet_schema.model_dump()}

    # State 2: Processing
    if document.analysis_status == ProcessingStatus.PROCESSING:
        # Get processing milestones/logs (for now, return status)
        return {
            "status": "processing",
            "message": "Balance sheet processing in progress",
            "milestones": {"step": "extracting", "progress": "Processing balance sheet data..."},
        }

    # State 3: Does not exist and not processing
    raise HTTPException(status_code=404, detail=f"DEBUG_BS_NOT_FOUND_FOR_{document_id}")

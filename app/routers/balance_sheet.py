"""
Balance sheet processing routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
from app.schemas.balance_sheet import BalanceSheet as BalanceSheetSchema, BalanceSheetCreate
from app.routers.auth import get_current_user
from app.models.user import User
from agents.balance_sheet_extractor import extract_balance_sheet
import uuid
from datetime import datetime
import json

router = APIRouter()


def process_balance_sheet_async(
    document_id: str,
    db: Session
):
    """
    Background task to process balance sheet extraction.
    """
    from app.database import SessionLocal
    
    db_session = SessionLocal()
    
    try:
        # Get document
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"Document {document_id} not found")
            return
        
        # Check if document type is eligible
        eligible_types = [
            DocumentType.EARNINGS_ANNOUNCEMENT,
            DocumentType.QUARTERLY_FILING,
            DocumentType.ANNUAL_FILING
        ]
        
        if document.document_type not in eligible_types:
            print(f"Document type {document.document_type} is not eligible for balance sheet processing")
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return
        
        # Update status to processing
        document.analysis_status = ProcessingStatus.PROCESSING
        db_session.commit()
        
        # Extract balance sheet
        time_period = document.time_period or "Unknown"
        extracted_data = extract_balance_sheet(
            document_id=document_id,
            file_path=document.file_path,
            time_period=time_period,
            max_retries=3
        )
        
        # Check if balance sheet already exists
        existing_balance_sheet = db_session.query(BalanceSheet).filter(
            BalanceSheet.document_id == document_id
        ).first()
        
        if existing_balance_sheet:
            # Delete existing line items
            db_session.query(BalanceSheetLineItem).filter(
                BalanceSheetLineItem.balance_sheet_id == existing_balance_sheet.id
            ).delete()
            balance_sheet = existing_balance_sheet
        else:
            # Create new balance sheet
            balance_sheet = BalanceSheet(
                id=str(uuid.uuid4()),
                document_id=document_id,
                time_period=extracted_data.get('time_period'),
                is_valid=extracted_data.get('is_valid', False),
                validation_errors=json.dumps(extracted_data.get('validation_errors', [])) if extracted_data.get('validation_errors') else None,
                currency=extracted_data.get('currency')
            )
            db_session.add(balance_sheet)
            db_session.commit()
            db_session.refresh(balance_sheet)
        
        # Update balance sheet fields
        balance_sheet.time_period = extracted_data.get('time_period')
        balance_sheet.currency = extracted_data.get('currency')
        balance_sheet.is_valid = extracted_data.get('is_valid', False)
        balance_sheet.validation_errors = json.dumps(extracted_data.get('validation_errors', [])) if extracted_data.get('validation_errors') else None

        
        # Create line items
        for idx, item in enumerate(extracted_data.get('line_items', [])):
            line_item = BalanceSheetLineItem(
                id=str(uuid.uuid4()),
                balance_sheet_id=balance_sheet.id,
                line_name=item['line_name'],
                line_value=item['line_value'],
                line_category=item.get('line_category'),
                is_operating=item.get('is_operating'),
                line_order=idx
            )
            db_session.add(line_item)
        
        db_session.commit()
        
        # Update document status
        document.analysis_status = ProcessingStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        db_session.commit()
        
    except Exception as e:
        print(f"Error processing balance sheet for document {document_id}: {str(e)}")
        if document:
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
    finally:
        db_session.close()


@router.post("/{document_id}/process-balance-sheet")
async def trigger_balance_sheet_processing(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger balance sheet processing for a document.
    Only processes earnings announcements, quarterly filings, and annual reports.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if document type is eligible
    eligible_types = [
        DocumentType.EARNINGS_ANNOUNCEMENT,
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING
    ]
    
    if document.document_type not in eligible_types:
        raise HTTPException(
            status_code=400,
            detail=f"Document type {document.document_type} is not eligible for balance sheet processing. Only earnings announcements, quarterly filings, and annual reports are supported."
        )
    
    # Check if document is indexed
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before balance sheet processing can begin."
        )
    
    # Check if already processing or processed
    if document.analysis_status == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail="Balance sheet processing is already in progress for this document."
        )
    
    # Start background processing
    background_tasks.add_task(process_balance_sheet_async, document_id, db)
    
    # Update status to processing
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()
    
    return {"message": "Balance sheet processing started", "document_id": document_id}


@router.get("/{document_id}/balance-sheet", response_model=BalanceSheetSchema)
async def get_balance_sheet(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get balance sheet data for a document.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    balance_sheet = db.query(BalanceSheet).filter(
        BalanceSheet.document_id == document_id
    ).first()
    
    if not balance_sheet:
        raise HTTPException(status_code=404, detail="Balance sheet not found for this document")
    
    return balance_sheet


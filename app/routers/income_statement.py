"""
Income statement processing routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
from app.schemas.income_statement import IncomeStatement as IncomeStatementSchema, IncomeStatementCreate
from app.routers.auth import get_current_user
from app.models.user import User
from agents.income_statement_extractor import extract_income_statement
import uuid
from datetime import datetime
import json

router = APIRouter()


def process_income_statement_async(
    document_id: str,
    db: Session
):
    """
    Background task to process income statement extraction.
    """
    from app.database import SessionLocal
    from app.utils.financial_statement_progress import (
        update_milestone, get_progress,
        FinancialStatementMilestone, MilestoneStatus
    )
    
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
            print(f"Document type {document.document_type} is not eligible for income statement processing")
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return
        
        # Initialize or reset progress tracking
        # If progress doesn't exist, initialize it
        # If it exists, we're re-running, so reset only income statement milestones
        from app.utils.financial_statement_progress import initialize_progress, reset_income_statement_milestones
        if not get_progress(document_id):
            initialize_progress(document_id)
        else:
            # Re-running: reset only income statement milestones
            reset_income_statement_milestones(document_id)
        
        # Update status to processing
        document.analysis_status = ProcessingStatus.PROCESSING
        db_session.commit()
        
        # Update milestone: extracting income statement
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
            MilestoneStatus.IN_PROGRESS,
            "Extracting income statement data..."
        )
        
        # Extract income statement
        time_period = document.time_period or "Unknown"
        extracted_data = extract_income_statement(
            document_id=document_id,
            file_path=document.file_path,
            time_period=time_period,
            max_retries=3
        )
        
        # Check if extraction returned valid data with line items
        line_items = extracted_data.get('line_items', [])
        if not line_items or len(line_items) == 0:
            error_msg = "Income statement extraction returned no line items"
            print(f"Error: {error_msg}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                error_msg
            )
            # Mark additional items and classification milestones as ERROR as well since we can't proceed
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                MilestoneStatus.ERROR,
                "Cannot extract: income statement extraction failed"
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                "Cannot classify: extraction failed"
            )
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return
        
        # Update milestone: extracting income statement completed
        # Note: Even if validation fails, extraction is considered completed
        extraction_message = "Income statement extraction completed"
        if not extracted_data.get('is_valid', False):
            extraction_message += " (validation failed)"
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
            MilestoneStatus.COMPLETED,
            extraction_message
        )
        
        # Update milestone: extracting additional items (happens as part of extract_income_statement)
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
            MilestoneStatus.COMPLETED,
            "Additional items extraction completed"
        )
        
        # Update milestone: classifying income statement
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
            MilestoneStatus.IN_PROGRESS,
            "Classifying income statement line items..."
        )
        
        try:
            # Check if income statement already exists
            existing_income_statement = db_session.query(IncomeStatement).filter(
                IncomeStatement.document_id == document_id
            ).first()
            
            if existing_income_statement:
                # Delete existing line items
                db_session.query(IncomeStatementLineItem).filter(
                    IncomeStatementLineItem.income_statement_id == existing_income_statement.id
                ).delete()
                income_statement = existing_income_statement
            else:
                # Create new income statement
                income_statement = IncomeStatement(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=extracted_data.get('time_period'),
                    currency=extracted_data.get('currency'),
                    is_valid=extracted_data.get('is_valid', False),
                    validation_errors=json.dumps(extracted_data.get('validation_errors', [])) if extracted_data.get('validation_errors') else None,
                    revenue_prior_year=extracted_data.get('revenue_prior_year'),
                    revenue_growth_yoy=extracted_data.get('revenue_growth_yoy'),
                    basic_shares_outstanding=extracted_data.get('basic_shares_outstanding'),
                    diluted_shares_outstanding=extracted_data.get('diluted_shares_outstanding'),
                    amortization=extracted_data.get('amortization')
                )
                db_session.add(income_statement)
                db_session.commit()
                db_session.refresh(income_statement)
            
            # Update income statement fields
            income_statement.time_period = extracted_data.get('time_period')
            income_statement.currency = extracted_data.get('currency')
            income_statement.is_valid = extracted_data.get('is_valid', False)
            income_statement.validation_errors = json.dumps(extracted_data.get('validation_errors', [])) if extracted_data.get('validation_errors') else None
            income_statement.revenue_prior_year = extracted_data.get('revenue_prior_year')
            income_statement.revenue_growth_yoy = extracted_data.get('revenue_growth_yoy')
            income_statement.basic_shares_outstanding = extracted_data.get('basic_shares_outstanding')
            income_statement.diluted_shares_outstanding = extracted_data.get('diluted_shares_outstanding')
            income_statement.amortization = extracted_data.get('amortization')
            
            # Create line items
            for idx, item in enumerate(line_items):
                line_item = IncomeStatementLineItem(
                    id=str(uuid.uuid4()),
                    income_statement_id=income_statement.id,
                    line_name=item['line_name'],
                    line_value=item['line_value'],
                    line_category=item.get('line_category'),
                    is_operating=item.get('is_operating'),
                    line_order=idx
                )
                db_session.add(line_item)
            
            db_session.commit()
            
            # Update milestone: classifying income statement completed
            classification_message = "Income statement classification completed"
            if not extracted_data.get('is_valid', False):
                classification_message += " (data invalid but classified)"
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.COMPLETED,
                classification_message
            )
        except Exception as classification_error:
            # If classification/saving fails, mark it as error
            print(f"Error during income statement classification/saving: {str(classification_error)}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                f"Classification error: {str(classification_error)}"
            )
            raise  # Re-raise to be caught by outer exception handler
        
        # Update document status
        document.analysis_status = ProcessingStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        db_session.commit()
        
    except Exception as e:
        print(f"Error processing income statement for document {document_id}: {str(e)}")
        from app.utils.financial_statement_progress import (
            update_milestone, FinancialStatementMilestone, MilestoneStatus
        )
        # Update milestone to error
        current_progress = get_progress(document_id)
        if current_progress:
            # Find which milestone was in progress and mark it as error
            milestones = current_progress.get("milestones", {})
            for milestone_key, milestone_data in milestones.items():
                if milestone_data.get("status") == MilestoneStatus.IN_PROGRESS.value:
                    try:
                        milestone = FinancialStatementMilestone(milestone_key)
                        update_milestone(
                            document_id,
                            milestone,
                            MilestoneStatus.ERROR,
                            f"Error: {str(e)}"
                        )
                    except:
                        pass
                    break
        
        if document:
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
    finally:
        db_session.close()


@router.post("/{document_id}/process-income-statement")
async def trigger_income_statement_processing(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger income statement processing for a document.
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
            detail=f"Document type {document.document_type} is not eligible for income statement processing. Only earnings announcements, quarterly filings, and annual reports are supported."
        )
    
    # Check if document is indexed
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before income statement processing can begin."
        )
    
    # Check if already processing or processed
    if document.analysis_status == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail="Income statement processing is already in progress for this document."
        )
    
    # Start background processing
    background_tasks.add_task(process_income_statement_async, document_id, db)
    
    # Update status to processing
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()
    
    return {"message": "Income statement processing started", "document_id": document_id}


@router.post("/{document_id}/rerun-income-statement-extraction")
async def rerun_income_statement_extraction(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-run income statement extraction (extraction + additional items + classification)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before income statement processing can begin."
        )
    
    # Allow re-running even if already processed
    background_tasks.add_task(process_income_statement_async, document_id, db)
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()
    
    return {"message": "Income statement extraction re-run started", "document_id": document_id}


@router.get("/{document_id}/income-statement")
async def get_income_statement(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get income statement data for a document.
    Returns three possible states:
    1. Income statement exists - returns income statement data
    2. Processing - returns processing status with milestones
    3. Does not exist and not processing - returns 404
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    income_statement = db.query(IncomeStatement).filter(
        IncomeStatement.document_id == document_id
    ).first()
    
    # State 1: Income statement exists
    if income_statement:
        # Convert to schema for proper serialization
        income_statement_schema = IncomeStatementSchema.model_validate(income_statement)
        return {
            "status": "exists",
            "data": income_statement_schema.model_dump()
        }
    
    # State 2: Processing
    if document.analysis_status == ProcessingStatus.PROCESSING:
        return {
            "status": "processing",
            "message": "Income statement processing in progress",
            "milestones": {
                "step": "extracting",
                "progress": "Processing income statement data..."
            }
        }
    
    # State 3: Does not exist and not processing
    raise HTTPException(
        status_code=404,
        detail="Income statement not found for this document"
    )


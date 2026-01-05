"""
Income statement processing routes
"""

import json
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.amortization_extractor import extract_amortization
from agents.income_statement_extractor import extract_income_statement
from agents.organic_growth_extractor import extract_organic_growth
from agents.shares_outstanding_extractor import extract_shares_outstanding
from app.database import get_db
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.amortization import Amortization, AmortizationLineItem
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
from app.models.organic_growth import OrganicGrowth
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.historical_calculations import calculate_and_save_historical_calculations
from app.schemas.income_statement import IncomeStatement as IncomeStatementSchema

router = APIRouter()


def process_income_statement_async(document_id: str, db: Session):
    """
    Background task to process income statement extraction.
    """
    from app.database import SessionLocal
    from app.utils.financial_statement_progress import (
        FinancialStatementMilestone,
        MilestoneStatus,
        add_log,
        get_progress,
        update_milestone,
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
            DocumentType.ANNUAL_FILING,
        ]

        if document.document_type not in eligible_types:
            print(
                f"Document type {document.document_type} is not eligible for income statement processing"
            )
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return

        # Initialize or reset progress tracking
        # If progress doesn't exist, initialize it
        # If it exists, we're re-running, so reset only income statement milestones
        from app.utils.financial_statement_progress import (
            initialize_progress,
            reset_income_statement_milestones,
        )

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
            "Extracting income statement data...",
        )

        # Extract income statement
        time_period = document.time_period or "Unknown"

        # Try to get balance sheet chunk index from progress logs (stored when balance sheet extraction succeeded)
        balance_sheet_chunk_index = None
        progress = get_progress(document_id)
        if progress and "balance_sheet_chunk_index" in progress:
            balance_sheet_chunk_index = progress["balance_sheet_chunk_index"]

        extracted_data = extract_income_statement(
            document_id=document_id,
            file_path=document.file_path,
            time_period=time_period,
            max_retries=3,  # 3 attempts: before, after, 2 after balance sheet
            document_type=document.document_type,
            balance_sheet_chunk_index=balance_sheet_chunk_index,
        )

        # Check if extraction returned valid data with line items
        line_items = extracted_data.get("line_items", [])
        if not line_items or len(line_items) == 0:
            error_msg = "Income statement extraction returned no line items"
            print(f"Error: {error_msg}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                error_msg,
            )
            # Mark additional items and classification milestones as ERROR as well since we can't proceed
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING,
                MilestoneStatus.ERROR,
                "Cannot extract: income statement extraction failed",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_AMORTIZATION,
                MilestoneStatus.ERROR,
                "Cannot extract: income statement extraction failed",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH,
                MilestoneStatus.ERROR,
                "Cannot extract: income statement extraction failed",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                "Cannot classify: extraction failed",
            )
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return

        # Update milestone: extracting income statement completed
        # Note: Even if validation fails, extraction is considered completed
        if not extracted_data.get("is_valid", False):
            # Include validation errors in the message
            validation_errors = extracted_data.get("validation_errors", [])
            if validation_errors:
                # Show first 2-3 validation errors
                error_summary = "; ".join(validation_errors[:3])
                if len(validation_errors) > 3:
                    error_summary += f" (+{len(validation_errors) - 3} more)"
                extraction_message = f"Validation failed: {error_summary}"
            else:
                extraction_message = "Validation failed"
            # Set status to ERROR instead of COMPLETED when validation fails
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                extraction_message,
            )
        else:
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT,
                MilestoneStatus.COMPLETED,
                "Income statement extraction completed",
            )

        # Update milestone: classifying income statement
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
            MilestoneStatus.IN_PROGRESS,
            "Classifying income statement line items...",
        )

        try:
            # Check if income statement already exists
            existing_income_statement = (
                db_session.query(IncomeStatement)
                .filter(IncomeStatement.document_id == document_id)
                .first()
            )

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
                    time_period=extracted_data.get("time_period"),
                    currency=extracted_data.get("currency"),
                    unit=extracted_data.get("unit"),
                    is_valid=extracted_data.get("is_valid", False),
                    validation_errors=json.dumps(extracted_data.get("validation_errors", []))
                    if extracted_data.get("validation_errors")
                    else None,
                    chunk_index=extracted_data.get(
                        "chunk_index"
                    ),  # Persist chunk index for traceability
                    revenue_prior_year=extracted_data.get("revenue_prior_year"),
                    revenue_prior_year_unit=extracted_data.get("revenue_prior_year_unit"),
                    revenue_growth_yoy=extracted_data.get("revenue_growth_yoy"),
                    basic_shares_outstanding=None,
                    basic_shares_outstanding_unit=None,
                    diluted_shares_outstanding=None,
                    diluted_shares_outstanding_unit=None,
                    amortization=None,
                    amortization_unit=None,
                )
                db_session.add(income_statement)
                db_session.commit()
                db_session.refresh(income_statement)

            # Update income statement fields
            income_statement.time_period = extracted_data.get("time_period")
            income_statement.currency = extracted_data.get("currency")
            income_statement.unit = extracted_data.get("unit")
            income_statement.is_valid = extracted_data.get("is_valid", False)
            income_statement.validation_errors = (
                json.dumps(extracted_data.get("validation_errors", []))
                if extracted_data.get("validation_errors")
                else None
            )
            income_statement.revenue_prior_year = extracted_data.get("revenue_prior_year")
            income_statement.revenue_prior_year_unit = extracted_data.get("revenue_prior_year_unit")
            income_statement.revenue_growth_yoy = extracted_data.get("revenue_growth_yoy")
            income_statement.basic_shares_outstanding = None
            income_statement.basic_shares_outstanding_unit = None
            income_statement.diluted_shares_outstanding = None
            income_statement.diluted_shares_outstanding_unit = None
            income_statement.amortization = None
            income_statement.amortization_unit = None

            # Create line items
            for idx, item in enumerate(line_items):
                line_item = IncomeStatementLineItem(
                    id=str(uuid.uuid4()),
                    income_statement_id=income_statement.id,
                    line_name=item["line_name"],
                    line_value=item["line_value"],
                    line_category=item.get("line_category"),
                    is_operating=item.get("is_operating"),
                    line_order=idx,
                )
                db_session.add(line_item)

            db_session.commit()

            # Add log for classification completion
            classified_count = len(line_items)
            add_log(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                f"Classified {classified_count} line items as operating/non-operating",
            )

            # Update milestone: classifying income statement completed
            classification_message = "Income statement classification completed"
            if not extracted_data.get("is_valid", False):
                classification_message += " (data invalid but classified)"
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.COMPLETED,
                classification_message,
            )

            # Extract shares outstanding
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING,
                MilestoneStatus.IN_PROGRESS,
                "Extracting shares outstanding...",
            )
            try:
                shares_result = extract_shares_outstanding(
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=time_period,
                )
                if shares_result.get("is_valid"):
                    income_statement.basic_shares_outstanding = shares_result.get(
                        "basic_shares_outstanding"
                    )
                    income_statement.basic_shares_outstanding_unit = shares_result.get(
                        "basic_shares_outstanding_unit"
                    )
                    income_statement.diluted_shares_outstanding = shares_result.get(
                        "diluted_shares_outstanding"
                    )
                    income_statement.diluted_shares_outstanding_unit = shares_result.get(
                        "diluted_shares_outstanding_unit"
                    )
                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING,
                        MilestoneStatus.COMPLETED,
                        "Shares outstanding extracted",
                    )
                else:
                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING,
                        MilestoneStatus.ERROR,
                        "Shares outstanding extraction failed or not found",
                    )
            except Exception as shares_error:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING,
                    MilestoneStatus.ERROR,
                    f"Shares outstanding extraction failed: {str(shares_error)}",
                )

            db_session.commit()

            # Extract amortization
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_AMORTIZATION,
                MilestoneStatus.IN_PROGRESS,
                "Extracting amortization line items...",
            )
            try:
                amortization_result = extract_amortization(
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=time_period,
                )
                if amortization_result.get("line_items"):
                    existing_amortization = (
                        db_session.query(Amortization)
                        .filter(Amortization.document_id == document_id)
                        .first()
                    )
                    if existing_amortization:
                        db_session.query(AmortizationLineItem).filter(
                            AmortizationLineItem.amortization_id == existing_amortization.id
                        ).delete()
                        db_session.delete(existing_amortization)
                        db_session.commit()

                    amortization = Amortization(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        time_period=time_period,
                        currency=income_statement.currency,
                        chunk_index=amortization_result.get("chunk_index"),
                        is_valid=amortization_result.get("is_valid", False),
                        validation_errors=json.dumps(
                            amortization_result.get("validation_errors", [])
                        )
                        if amortization_result.get("validation_errors")
                        else None,
                    )
                    db_session.add(amortization)
                    db_session.commit()
                    db_session.refresh(amortization)

                    for idx, item in enumerate(amortization_result.get("line_items", [])):
                        db_session.add(
                            AmortizationLineItem(
                                id=str(uuid.uuid4()),
                                amortization_id=amortization.id,
                                line_name=item.get("line_name"),
                                line_value=item.get("line_value"),
                                unit=item.get("unit"),
                                is_operating=item.get("is_operating"),
                                category=item.get("category"),
                                line_order=idx,
                            )
                        )
                    db_session.commit()

                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_AMORTIZATION,
                        MilestoneStatus.COMPLETED,
                        "Amortization extraction completed",
                    )
                else:
                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_AMORTIZATION,
                        MilestoneStatus.ERROR,
                        "Amortization extraction failed or not found",
                    )
            except Exception as amortization_error:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_AMORTIZATION,
                    MilestoneStatus.ERROR,
                    f"Amortization extraction failed: {str(amortization_error)}",
                )

            # Extract organic growth
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH,
                MilestoneStatus.IN_PROGRESS,
                "Extracting organic growth signals...",
            )
            try:
                income_statement_data = {
                    "line_items": [
                        {
                            "line_name": item.line_name,
                            "line_value": item.line_value,
                        }
                        for item in income_statement.line_items
                    ],
                    "revenue_prior_year": income_statement.revenue_prior_year,
                }
                organic_growth_result = extract_organic_growth(
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=time_period,
                    income_statement_data=income_statement_data,
                )
                if organic_growth_result.get("current_period_revenue") is not None:
                    existing_growth = (
                        db_session.query(OrganicGrowth)
                        .filter(OrganicGrowth.document_id == document_id)
                        .first()
                    )
                    if existing_growth:
                        db_session.delete(existing_growth)
                        db_session.commit()

                    organic_growth = OrganicGrowth(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        time_period=time_period,
                        currency=income_statement.currency,
                        prior_period_revenue=organic_growth_result.get("prior_period_revenue"),
                        prior_period_revenue_unit=income_statement.revenue_prior_year_unit,
                        current_period_revenue=organic_growth_result.get("current_period_revenue"),
                        current_period_revenue_unit=income_statement.unit,
                        simple_revenue_growth=organic_growth_result.get("simple_revenue_growth"),
                        acquisition_revenue_impact=organic_growth_result.get(
                            "acquisition_revenue_impact"
                        ),
                        acquisition_revenue_impact_unit=organic_growth_result.get(
                            "acquisition_revenue_impact_unit"
                        ),
                        current_period_adjusted_revenue=organic_growth_result.get(
                            "current_period_adjusted_revenue"
                        ),
                        current_period_adjusted_revenue_unit=income_statement.unit,
                        organic_revenue_growth=organic_growth_result.get("organic_revenue_growth"),
                        chunk_index=organic_growth_result.get("chunk_index"),
                        is_valid=organic_growth_result.get("is_valid", False),
                        validation_errors=json.dumps(
                            organic_growth_result.get("validation_errors", [])
                        )
                        if organic_growth_result.get("validation_errors")
                        else None,
                    )
                    db_session.add(organic_growth)
                    db_session.commit()

                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH,
                        MilestoneStatus.COMPLETED,
                        "Organic growth extraction completed",
                    )
                else:
                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH,
                        MilestoneStatus.ERROR,
                        "Organic growth extraction failed or insufficient data",
                    )
            except Exception as organic_error:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH,
                    MilestoneStatus.ERROR,
                    f"Organic growth extraction failed: {str(organic_error)}",
                )

            # Automatically trigger historical calculations after income statement completes
            # Use a fresh database session to ensure we can see committed data
            try:
                from app.database import SessionLocal

                calc_db = SessionLocal()
                try:
                    calculate_and_save_historical_calculations(document_id, calc_db)
                    print(f"Historical calculations completed for document {document_id}")
                finally:
                    calc_db.close()
            except HTTPException as calc_error:
                # Don't fail the whole process if historical calculations fail (e.g., missing balance sheet)
                print(f"Warning: Failed to calculate historical calculations: {calc_error.detail}")
                # Continue without raising
            except Exception as calc_error:
                # Don't fail the whole process if historical calculations fail
                print(f"Warning: Failed to calculate historical calculations: {str(calc_error)}")
                print(traceback.format_exc())
                # Continue without raising
        except Exception as classification_error:
            # If classification/saving fails, mark it as error
            print(
                f"Error during income statement classification/saving: {str(classification_error)}"
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                f"Classification error: {str(classification_error)}",
            )
            raise  # Re-raise to be caught by outer exception handler

        # Update document status
        document.analysis_status = ProcessingStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        db_session.commit()

    except Exception as e:
        print(f"Error processing income statement for document {document_id}: {str(e)}")
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
                            document_id, milestone, MilestoneStatus.ERROR, f"Error: {str(e)}"
                        )
                    except Exception:
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
    current_user: User = Depends(get_current_user),
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
        DocumentType.ANNUAL_FILING,
    ]

    if document.document_type not in eligible_types:
        raise HTTPException(
            status_code=400,
            detail=f"Document type {document.document_type} is not eligible for income statement processing. Only earnings announcements, quarterly filings, and annual reports are supported.",
        )

    # Check if document is indexed
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before income statement processing can begin.",
        )

    # Check if already processing or processed
    if document.analysis_status == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail="Income statement processing is already in progress for this document.",
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
    current_user: User = Depends(get_current_user),
):
    """Re-run income statement extraction (extraction + additional items + classification)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before income statement processing can begin.",
        )

    # Allow re-running even if already processed
    background_tasks.add_task(process_income_statement_async, document_id, db)
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()

    return {"message": "Income statement extraction re-run started", "document_id": document_id}


@router.get("/{document_id}/income-statement")
async def get_income_statement(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
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

    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )

    # State 1: Income statement exists
    if income_statement:
        # Convert to schema for proper serialization
        income_statement_schema = IncomeStatementSchema.model_validate(income_statement)
        return {"status": "exists", "data": income_statement_schema.model_dump()}

    # State 2: Processing
    if document.analysis_status == ProcessingStatus.PROCESSING:
        return {
            "status": "processing",
            "message": "Income statement processing in progress",
            "milestones": {"step": "extracting", "progress": "Processing income statement data..."},
        }

    # State 3: Does not exist and not processing
    raise HTTPException(status_code=404, detail="Income statement not found for this document")

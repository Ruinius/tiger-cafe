"""
Balance sheet processing routes
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.balance_sheet_extractor import extract_balance_sheet
from agents.non_operating_classifier import classify_non_operating_items
from agents.other_assets_extractor import (
    extract_original_name_from_standardized as extract_other_assets_label,
    extract_other_assets,
)
from agents.other_liabilities_extractor import (
    extract_original_name_from_standardized as extract_other_liabilities_label,
    extract_other_liabilities,
)
from app.database import get_db
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.non_operating_classification import (
    NonOperatingClassification,
    NonOperatingClassificationItem,
)
from app.models.other_assets import OtherAssets, OtherAssetsLineItem
from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.balance_sheet import BalanceSheet as BalanceSheetSchema

router = APIRouter()


def _find_standardized_line_item(line_items: list[BalanceSheetLineItem], label: str):
    for item in line_items:
        if label.lower() in (item.line_name or "").lower():
            return item
    return None


def _extract_balance_sheet_terms(
    balance_sheet: BalanceSheet,
    label: str,
) -> tuple[list[str], float | None]:
    item = _find_standardized_line_item(balance_sheet.line_items, label)
    if not item:
        return [], None

    original = extract_other_assets_label(item.line_name) or extract_other_liabilities_label(
        item.line_name
    )
    terms = [original] if original else [item.line_name]
    return terms, float(item.line_value) if item.line_value is not None else None


def process_balance_sheet_async(document_id: str, db: Session):
    """
    Background task to process balance sheet extraction.
    """
    from app.database import SessionLocal
    from app.utils.financial_statement_progress import (
        FinancialStatementMilestone,
        MilestoneStatus,
        add_log,
        get_progress,
        initialize_progress,
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
                f"Document type {document.document_type} is not eligible for balance sheet processing"
            )
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return

        # Initialize or reset progress tracking
        # If progress doesn't exist, initialize it
        # If it exists, we're re-running, so reset all milestones (full re-run)
        if not get_progress(document_id):
            initialize_progress(document_id)
        else:
            # Re-running: reset all milestones for full re-run
            from app.utils.financial_statement_progress import reset_all_milestones

            reset_all_milestones(document_id)

        # Update status to processing
        document.analysis_status = ProcessingStatus.PROCESSING
        db_session.commit()

        # Delete existing balance sheet BEFORE extraction to ensure fresh start
        existing_balance_sheet = (
            db_session.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
        )

        if existing_balance_sheet:
            # Delete existing line items first (foreign key constraint)
            db_session.query(BalanceSheetLineItem).filter(
                BalanceSheetLineItem.balance_sheet_id == existing_balance_sheet.id
            ).delete()
            # Delete the balance sheet itself
            db_session.delete(existing_balance_sheet)
            db_session.commit()
            print(f"Deleted existing balance sheet for document {document_id} before re-extraction")

        # Update milestone: extracting balance sheet
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
            MilestoneStatus.IN_PROGRESS,
            "Extracting balance sheet data...",
        )

        # Extract balance sheet
        time_period = document.time_period or "Unknown"
        extracted_data = extract_balance_sheet(
            document_id=document_id,
            file_path=document.file_path,
            time_period=time_period,
            max_retries=3,
            document_type=document.document_type,
        )

        # Store successful balance sheet chunk index in progress for income statement extraction
        balance_sheet_chunk_index = extracted_data.get("balance_sheet_chunk_index")
        if balance_sheet_chunk_index is not None:
            # Store in progress with thread safety
            from app.utils.financial_statement_progress import _progress_lock, _progress_store

            with _progress_lock:
                if document_id not in _progress_store:
                    from app.utils.financial_statement_progress import initialize_progress

                    initialize_progress(document_id)
                _progress_store[document_id]["balance_sheet_chunk_index"] = (
                    balance_sheet_chunk_index
                )

        # Check if extraction returned valid data with line items
        line_items = extracted_data.get("line_items", [])
        if not line_items or len(line_items) == 0:
            error_msg = "Balance sheet extraction returned no line items"
            print(f"Error: {error_msg}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                MilestoneStatus.ERROR,
                error_msg,
            )
            # Mark classification milestone as ERROR as well since we can't proceed
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET,
                MilestoneStatus.ERROR,
                "Cannot classify: extraction failed",
            )
            document.analysis_status = ProcessingStatus.ERROR
            db_session.commit()
            return

        # Update milestone: extracting balance sheet completed
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
                FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                MilestoneStatus.ERROR,
                extraction_message,
            )
        else:
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                MilestoneStatus.COMPLETED,
                "Balance sheet extraction completed",
            )

        # Update milestone: classifying balance sheet
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET,
            MilestoneStatus.IN_PROGRESS,
            "Classifying balance sheet line items...",
        )

        try:
            # Create new balance sheet (existing one was already deleted before extraction)
            balance_sheet = BalanceSheet(
                id=str(uuid.uuid4()),
                document_id=document_id,
                time_period=extracted_data.get("time_period"),
                is_valid=extracted_data.get("is_valid", False),
                validation_errors=json.dumps(extracted_data.get("validation_errors", []))
                if extracted_data.get("validation_errors")
                else None,
                currency=extracted_data.get("currency"),
                unit=extracted_data.get("unit"),
                chunk_index=extracted_data.get(
                    "chunk_index"
                ),  # Persist chunk index for traceability
            )
            db_session.add(balance_sheet)
            db_session.commit()
            db_session.refresh(balance_sheet)

            # Update balance sheet fields
            balance_sheet.time_period = extracted_data.get("time_period")
            balance_sheet.currency = extracted_data.get("currency")
            balance_sheet.unit = extracted_data.get("unit")
            balance_sheet.is_valid = extracted_data.get("is_valid", False)
            balance_sheet.validation_errors = (
                json.dumps(extracted_data.get("validation_errors", []))
                if extracted_data.get("validation_errors")
                else None
            )

            # Create line items
            for idx, item in enumerate(line_items):
                line_item = BalanceSheetLineItem(
                    id=str(uuid.uuid4()),
                    balance_sheet_id=balance_sheet.id,
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
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET,
                f"Classified {classified_count} line items as operating/non-operating",
            )

            # Update milestone: classifying balance sheet completed
            classification_message = "Balance sheet classification completed"
            if not extracted_data.get("is_valid", False):
                classification_message += " (data invalid but classified)"
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET,
                MilestoneStatus.COMPLETED,
                classification_message,
            )
        except Exception as classification_error:
            # If classification/saving fails, mark it as error
            print(f"Error during balance sheet classification/saving: {str(classification_error)}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET,
                MilestoneStatus.ERROR,
                f"Classification error: {str(classification_error)}",
            )
            raise  # Re-raise to be caught by outer exception handler

        # Extract other assets
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_OTHER_ASSETS,
            MilestoneStatus.IN_PROGRESS,
            "Extracting other assets line items...",
        )
        other_assets_result = None
        if balance_sheet and balance_sheet.line_items:
            current_terms, current_total = _extract_balance_sheet_terms(
                balance_sheet, "Other Current Assets"
            )
            non_current_terms, non_current_total = _extract_balance_sheet_terms(
                balance_sheet, "Other Non-Current Assets"
            )
            query_terms = current_terms + non_current_terms
            other_assets_result = extract_other_assets(
                document_id=document_id,
                file_path=document.file_path,
                time_period=time_period,
                query_terms=query_terms,
                expected_current_total=current_total,
                expected_non_current_total=non_current_total,
            )

        if other_assets_result and other_assets_result.get("line_items"):
            existing_other_assets = (
                db_session.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
            )
            if existing_other_assets:
                db_session.query(OtherAssetsLineItem).filter(
                    OtherAssetsLineItem.other_assets_id == existing_other_assets.id
                ).delete()
                db_session.delete(existing_other_assets)
                db_session.commit()

            other_assets = OtherAssets(
                id=str(uuid.uuid4()),
                document_id=document_id,
                time_period=time_period,
                currency=balance_sheet.currency,
                chunk_index=other_assets_result.get("chunk_index"),
                is_valid=other_assets_result.get("is_valid", False),
                validation_errors=json.dumps(other_assets_result.get("validation_errors", []))
                if other_assets_result.get("validation_errors")
                else None,
            )
            db_session.add(other_assets)
            db_session.commit()
            db_session.refresh(other_assets)

            for idx, item in enumerate(other_assets_result.get("line_items", [])):
                db_session.add(
                    OtherAssetsLineItem(
                        id=str(uuid.uuid4()),
                        other_assets_id=other_assets.id,
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
                FinancialStatementMilestone.EXTRACTING_OTHER_ASSETS,
                MilestoneStatus.COMPLETED,
                "Other assets extraction completed",
            )
        else:
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_OTHER_ASSETS,
                MilestoneStatus.ERROR,
                "Other assets extraction failed or no line items found",
            )

        # Extract other liabilities
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_OTHER_LIABILITIES,
            MilestoneStatus.IN_PROGRESS,
            "Extracting other liabilities line items...",
        )
        other_liabilities_result = None
        if balance_sheet and balance_sheet.line_items:
            current_terms, current_total = _extract_balance_sheet_terms(
                balance_sheet, "Other Current Liabilities"
            )
            non_current_terms, non_current_total = _extract_balance_sheet_terms(
                balance_sheet, "Other Non-Current Liabilities"
            )
            query_terms = current_terms + non_current_terms
            other_liabilities_result = extract_other_liabilities(
                document_id=document_id,
                file_path=document.file_path,
                time_period=time_period,
                query_terms=query_terms,
                expected_current_total=current_total,
                expected_non_current_total=non_current_total,
            )

        if other_liabilities_result and other_liabilities_result.get("line_items"):
            existing_other_liabilities = (
                db_session.query(OtherLiabilities)
                .filter(OtherLiabilities.document_id == document_id)
                .first()
            )
            if existing_other_liabilities:
                db_session.query(OtherLiabilitiesLineItem).filter(
                    OtherLiabilitiesLineItem.other_liabilities_id == existing_other_liabilities.id
                ).delete()
                db_session.delete(existing_other_liabilities)
                db_session.commit()

            other_liabilities = OtherLiabilities(
                id=str(uuid.uuid4()),
                document_id=document_id,
                time_period=time_period,
                currency=balance_sheet.currency,
                chunk_index=other_liabilities_result.get("chunk_index"),
                is_valid=other_liabilities_result.get("is_valid", False),
                validation_errors=json.dumps(other_liabilities_result.get("validation_errors", []))
                if other_liabilities_result.get("validation_errors")
                else None,
            )
            db_session.add(other_liabilities)
            db_session.commit()
            db_session.refresh(other_liabilities)

            for idx, item in enumerate(other_liabilities_result.get("line_items", [])):
                db_session.add(
                    OtherLiabilitiesLineItem(
                        id=str(uuid.uuid4()),
                        other_liabilities_id=other_liabilities.id,
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
                FinancialStatementMilestone.EXTRACTING_OTHER_LIABILITIES,
                MilestoneStatus.COMPLETED,
                "Other liabilities extraction completed",
            )
        else:
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_OTHER_LIABILITIES,
                MilestoneStatus.ERROR,
                "Other liabilities extraction failed or no line items found",
            )

        # Classify non-operating items
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            MilestoneStatus.IN_PROGRESS,
            "Classifying non-operating items...",
        )
        non_operating_items = []
        if balance_sheet and balance_sheet.line_items:
            for item in balance_sheet.line_items:
                if item.is_operating is False:
                    non_operating_items.append(
                        {
                            "line_name": item.line_name,
                            "line_value": float(item.line_value) if item.line_value is not None else None,
                            "unit": balance_sheet.unit,
                            "source": "balance_sheet",
                        }
                    )

        other_assets = (
            db_session.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
        )
        if other_assets and other_assets.line_items:
            for item in other_assets.line_items:
                if item.is_operating is False:
                    non_operating_items.append(
                        {
                            "line_name": item.line_name,
                            "line_value": float(item.line_value) if item.line_value is not None else None,
                            "unit": item.unit,
                            "source": "other_assets",
                        }
                    )

        other_liabilities = (
            db_session.query(OtherLiabilities)
            .filter(OtherLiabilities.document_id == document_id)
            .first()
        )
        if other_liabilities and other_liabilities.line_items:
            for item in other_liabilities.line_items:
                if item.is_operating is False:
                    non_operating_items.append(
                        {
                            "line_name": item.line_name,
                            "line_value": float(item.line_value) if item.line_value is not None else None,
                            "unit": item.unit,
                            "source": "other_liabilities",
                        }
                    )

        classified_items = classify_non_operating_items(non_operating_items)
        if classified_items:
            existing_classification = (
                db_session.query(NonOperatingClassification)
                .filter(NonOperatingClassification.document_id == document_id)
                .first()
            )
            if existing_classification:
                db_session.query(NonOperatingClassificationItem).filter(
                    NonOperatingClassificationItem.classification_id
                    == existing_classification.id
                ).delete()
                db_session.delete(existing_classification)
                db_session.commit()

            classification = NonOperatingClassification(
                id=str(uuid.uuid4()),
                document_id=document_id,
                time_period=time_period,
            )
            db_session.add(classification)
            db_session.commit()
            db_session.refresh(classification)

            for idx, item in enumerate(classified_items):
                db_session.add(
                    NonOperatingClassificationItem(
                        id=str(uuid.uuid4()),
                        classification_id=classification.id,
                        line_name=item.get("line_name"),
                        line_value=item.get("line_value"),
                        unit=item.get("unit"),
                        category=item.get("category"),
                        source=item.get("source"),
                        line_order=idx,
                    )
                )
            db_session.commit()

            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.COMPLETED,
                "Non-operating items classification completed",
            )
        else:
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.ERROR,
                "No non-operating items found to classify",
            )

        # Update document status
        document.analysis_status = ProcessingStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        db_session.commit()

    except Exception as e:
        print(f"Error processing balance sheet for document {document_id}: {str(e)}")
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


@router.post("/{document_id}/process-balance-sheet")
async def trigger_balance_sheet_processing(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        DocumentType.ANNUAL_FILING,
    ]

    if document.document_type not in eligible_types:
        raise HTTPException(
            status_code=400,
            detail=f"Document type {document.document_type} is not eligible for balance sheet processing. Only earnings announcements, quarterly filings, and annual reports are supported.",
        )

    # Check if document is indexed
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before balance sheet processing can begin.",
        )

    # Check if already processing or processed
    if document.analysis_status == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail="Balance sheet processing is already in progress for this document.",
        )

    # Start background processing
    background_tasks.add_task(process_balance_sheet_async, document_id, db)

    # Update status to processing
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()

    return {"message": "Balance sheet processing started", "document_id": document_id}


@router.post("/{document_id}/rerun-financial-statements")
async def rerun_financial_statements(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run entire financial statement pipeline (balance sheet then income statement sequentially)"""

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
            detail=f"Document type {document.document_type} is not eligible for financial statement processing.",
        )

    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before financial statement processing can begin.",
        )

    # Delete existing financial statements and historical calculations before re-run
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem

    # Delete existing balance sheet
    existing_balance_sheet = (
        db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    )
    if existing_balance_sheet:
        db.query(BalanceSheetLineItem).filter(
            BalanceSheetLineItem.balance_sheet_id == existing_balance_sheet.id
        ).delete()
        db.delete(existing_balance_sheet)

    # Delete existing income statement
    existing_income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    if existing_income_statement:
        db.query(IncomeStatementLineItem).filter(
            IncomeStatementLineItem.income_statement_id == existing_income_statement.id
        ).delete()
        db.delete(existing_income_statement)

    # Delete existing amortization
    existing_amortization = (
        db.query(Amortization).filter(Amortization.document_id == document_id).first()
    )
    if existing_amortization:
        db.query(AmortizationLineItem).filter(
            AmortizationLineItem.amortization_id == existing_amortization.id
        ).delete()
        db.delete(existing_amortization)

    # Delete existing organic growth
    existing_organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if existing_organic_growth:
        db.delete(existing_organic_growth)

    # Delete existing other assets
    existing_other_assets = (
        db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    )
    if existing_other_assets:
        db.query(OtherAssetsLineItem).filter(
            OtherAssetsLineItem.other_assets_id == existing_other_assets.id
        ).delete()
        db.delete(existing_other_assets)

    # Delete existing other liabilities
    existing_other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if existing_other_liabilities:
        db.query(OtherLiabilitiesLineItem).filter(
            OtherLiabilitiesLineItem.other_liabilities_id == existing_other_liabilities.id
        ).delete()
        db.delete(existing_other_liabilities)

    # Delete existing non-operating classification
    existing_non_operating = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if existing_non_operating:
        db.query(NonOperatingClassificationItem).filter(
            NonOperatingClassificationItem.classification_id == existing_non_operating.id
        ).delete()
        db.delete(existing_non_operating)

    # Delete existing historical calculations
    existing_historical_calc = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )
    if existing_historical_calc:
        db.delete(existing_historical_calc)

    db.commit()

    # Reset all milestones to pending
    from app.utils.financial_statement_progress import initialize_progress

    initialize_progress(document_id)

    # Queue document for financial statement processing (lower priority)
    from app.utils.document_processing_queue import queue_financial_statements_processing

    queue_financial_statements_processing(document_id)

    # Update status to processing
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()

    return {
        "message": "Financial statement extraction and classification re-run started",
        "document_id": document_id,
    }


@router.post("/{document_id}/rerun-financial-statements/test")
async def rerun_financial_statements_test(
    document_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """TEST ENDPOINT: Re-run entire financial statement pipeline without authentication"""

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
            detail=f"Document type {document.document_type} is not eligible for financial statement processing.",
        )

    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before financial statement processing can begin.",
        )

    # Delete existing financial statements and historical calculations before re-run
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem

    # Delete existing balance sheet
    existing_balance_sheet = (
        db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    )
    if existing_balance_sheet:
        db.query(BalanceSheetLineItem).filter(
            BalanceSheetLineItem.balance_sheet_id == existing_balance_sheet.id
        ).delete()
        db.delete(existing_balance_sheet)

    # Delete existing income statement
    existing_income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    if existing_income_statement:
        db.query(IncomeStatementLineItem).filter(
            IncomeStatementLineItem.income_statement_id == existing_income_statement.id
        ).delete()
        db.delete(existing_income_statement)

    # Delete existing amortization
    existing_amortization = (
        db.query(Amortization).filter(Amortization.document_id == document_id).first()
    )
    if existing_amortization:
        db.query(AmortizationLineItem).filter(
            AmortizationLineItem.amortization_id == existing_amortization.id
        ).delete()
        db.delete(existing_amortization)

    # Delete existing organic growth
    existing_organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    if existing_organic_growth:
        db.delete(existing_organic_growth)

    # Delete existing other assets
    existing_other_assets = (
        db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    )
    if existing_other_assets:
        db.query(OtherAssetsLineItem).filter(
            OtherAssetsLineItem.other_assets_id == existing_other_assets.id
        ).delete()
        db.delete(existing_other_assets)

    # Delete existing other liabilities
    existing_other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    if existing_other_liabilities:
        db.query(OtherLiabilitiesLineItem).filter(
            OtherLiabilitiesLineItem.other_liabilities_id == existing_other_liabilities.id
        ).delete()
        db.delete(existing_other_liabilities)

    # Delete existing non-operating classification
    existing_non_operating = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if existing_non_operating:
        db.query(NonOperatingClassificationItem).filter(
            NonOperatingClassificationItem.classification_id == existing_non_operating.id
        ).delete()
        db.delete(existing_non_operating)
    # Delete existing historical calculations
    existing_historical_calc = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )
    if existing_historical_calc:
        db.delete(existing_historical_calc)

    db.commit()

    # Reset all milestones to pending
    from app.utils.financial_statement_progress import initialize_progress

    initialize_progress(document_id)

    # Queue document for financial statement processing (lower priority)
    from app.utils.document_processing_queue import queue_financial_statements_processing

    queue_financial_statements_processing(document_id)

    # Update status to processing
    document.analysis_status = ProcessingStatus.PROCESSING
    db.commit()

    return {
        "message": "Financial statement extraction and classification re-run started",
        "document_id": document_id,
    }


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
    raise HTTPException(status_code=404, detail="Balance sheet not found for this document")

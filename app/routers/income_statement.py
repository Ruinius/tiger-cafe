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
from agents.gaap_reconciliation_extractor import extract_gaap_reconciliation
from agents.income_statement_extractor import extract_income_statement
from agents.non_operating_classifier import classify_non_operating_items
from agents.organic_growth_extractor import extract_organic_growth
from agents.other_assets_extractor import (
    extract_other_assets,
)
from agents.other_liabilities_extractor import (
    extract_other_liabilities,
)
from agents.shares_outstanding_extractor import extract_shares_outstanding
from app.database import get_db
from app.models.amortization import Amortization, AmortizationLineItem
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
from app.models.non_operating_classification import (
    NonOperatingClassification,
    NonOperatingClassificationItem,
)
from app.models.organic_growth import OrganicGrowth
from app.models.other_assets import OtherAssets, OtherAssetsLineItem
from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.historical_calculations import calculate_and_save_historical_calculations
from app.schemas.income_statement import IncomeStatement as IncomeStatementSchema
from app.utils.line_item_utils import (
    extract_original_name_from_standardized as extract_other_assets_label,
)
from app.utils.line_item_utils import (
    extract_original_name_from_standardized as extract_other_liabilities_label,
)

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

        # Update milestone: income statement processing
        update_milestone(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            MilestoneStatus.IN_PROGRESS,
            "Extracting income statement data...",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "Started income statement extraction",
        )

        # Extract income statement
        time_period = document.time_period or "Unknown"

        # Try to get balance sheet chunk index from progress logs (stored when balance sheet extraction succeeded)
        # If not in progress store, check the database (chunk_index is persisted even if validation fails)
        # IMPORTANT: All chunk indices are scoped to the specific document_id to avoid cross-document confusion.
        # The progress store is keyed by document_id, and database queries filter by document_id.
        balance_sheet_chunk_index = None
        progress = get_progress(document_id)  # Progress store is scoped by document_id
        if progress and "balance_sheet_chunk_index" in progress:
            balance_sheet_chunk_index = progress["balance_sheet_chunk_index"]
        else:
            # Fallback: get chunk_index from database (persisted after extraction, even if validation failed)
            # Database query is explicitly filtered by document_id to ensure we only get chunks for this document
            existing_balance_sheet = (
                db_session.query(BalanceSheet)
                .filter(BalanceSheet.document_id == document_id)
                .first()
            )
            if existing_balance_sheet and existing_balance_sheet.chunk_index is not None:
                balance_sheet_chunk_index = existing_balance_sheet.chunk_index

        extracted_data = extract_income_statement(
            document_id=document_id,
            file_path=document.file_path,
            time_period=time_period,
            max_retries=4,  # 4 attempts: same, before, after, full search
            document_type=document.document_type,
            balance_sheet_chunk_index=balance_sheet_chunk_index,
            period_end_date=document.period_end_date,
        )

        # Check if extraction returned valid data with line items
        line_items = extracted_data.get("line_items", [])
        if not line_items or len(line_items) == 0:
            error_msg = "Income statement extraction returned no line items"
            print(f"Error: {error_msg}")
            update_milestone(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                error_msg,
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                MilestoneStatus.ERROR,
                "Cannot extract additional items: income statement extraction failed",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.ERROR,
                "Cannot classify non-operating items: income statement extraction failed",
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
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"Validation failed: {extraction_message}",
            )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                "Income statement extraction completed",
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
                # Skip items with no value (prevents database integrity errors)
                if item.get("line_value") is None:
                    continue

                line_item = IncomeStatementLineItem(
                    id=str(uuid.uuid4()),
                    income_statement_id=income_statement.id,
                    line_name=item["line_name"],
                    line_value=item["line_value"],
                    line_category=item.get("line_category"),
                    standardized_name=item.get("standardized_name"),
                    is_calculated=item.get("is_calculated"),
                    is_expense=item.get("is_expense"),
                    is_operating=item.get("is_operating"),
                    line_order=idx,
                )
                db_session.add(line_item)

            db_session.commit()

            classified_count = len(line_items)
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"Classified {classified_count} line items as operating/non-operating",
            )

            if not extracted_data.get("is_valid", False):
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    MilestoneStatus.ERROR,
                    "Income statement processed with validation errors",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.INCOME_STATEMENT,
                    MilestoneStatus.COMPLETED,
                    "Income statement processing completed",
                )

            additional_item_errors = []
            update_milestone(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                MilestoneStatus.IN_PROGRESS,
                "Extracting additional items...",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                "Starting additional item extraction",
            )

            # Extract shares outstanding
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                "Extracting shares outstanding",
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
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Shares outstanding extracted",
                    )
                else:
                    additional_item_errors.append("shares outstanding")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Shares outstanding not found",
                    )
            except Exception as shares_error:
                additional_item_errors.append("shares outstanding")
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    f"Shares outstanding extraction failed: {str(shares_error)}",
                )

            db_session.commit()

            # Extract amortization (or GAAP reconciliation for earnings announcements)
            if document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT:
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Extracting GAAP/EBITDA reconciliation line items",
                )
                try:
                    amortization_result = extract_gaap_reconciliation(
                        document_id=document_id,
                        file_path=document.file_path,
                        time_period=time_period,
                        document_type=document.document_type,
                        period_end_date=document.period_end_date,
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
                            if item.get("line_value") is None:
                                continue
                            db_session.add(
                                AmortizationLineItem(
                                    id=str(uuid.uuid4()),
                                    amortization_id=amortization.id,
                                    line_name=item.get("line_name"),
                                    line_value=item.get("line_value"),
                                    unit=item.get("unit"),
                                    is_operating=item.get("is_operating"),
                                    category=item.get("category") or item.get("line_category"),
                                    line_order=idx,
                                )
                            )
                        db_session.commit()

                        add_log(
                            document_id,
                            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                            "GAAP/EBITDA reconciliation extraction completed",
                        )
                    else:
                        additional_item_errors.append("GAAP reconciliation")
                        add_log(
                            document_id,
                            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                            "GAAP/EBITDA reconciliation extraction failed or not found",
                        )
                except Exception as extraction_error:
                    additional_item_errors.append("GAAP reconciliation")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        f"GAAP/EBITDA reconciliation extraction failed: {str(extraction_error)}",
                    )
            else:
                # For quarterly/annual filings, use amortization extractor
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Extracting amortization line items",
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
                            if item.get("line_value") is None:
                                continue
                            db_session.add(
                                AmortizationLineItem(
                                    id=str(uuid.uuid4()),
                                    amortization_id=amortization.id,
                                    line_name=item.get("line_name"),
                                    line_value=item.get("line_value"),
                                    unit=item.get("unit"),
                                    is_operating=item.get("is_operating"),
                                    category=item.get("category") or item.get("line_category"),
                                    line_order=idx,
                                )
                            )
                        db_session.commit()

                        add_log(
                            document_id,
                            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                            "Amortization extraction completed",
                        )
                    else:
                        additional_item_errors.append("amortization")
                        add_log(
                            document_id,
                            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                            "Amortization extraction failed or not found",
                        )
                except Exception as extraction_error:
                    additional_item_errors.append("amortization")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        f"Amortization extraction failed: {str(extraction_error)}",
                    )

            # Extract organic growth
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                "Extracting organic growth signals",
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

                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Organic growth extraction completed",
                    )
                else:
                    additional_item_errors.append("organic growth")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Organic growth extraction failed or insufficient data",
                    )
            except Exception as organic_error:
                additional_item_errors.append("organic growth")
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    f"Organic growth extraction failed: {str(organic_error)}",
                )

            # Query balance sheet once (needed for both earnings and non-earnings announcements)
            balance_sheet = (
                db_session.query(BalanceSheet)
                .filter(BalanceSheet.document_id == document_id)
                .first()
            )

            # Extract other assets (skip for earnings announcements)
            if document.document_type != DocumentType.EARNINGS_ANNOUNCEMENT:
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Extracting other assets line items",
                )
                other_assets_result = None

                # For non-earnings announcements, use the extractor
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
                        db_session.query(OtherAssets)
                        .filter(OtherAssets.document_id == document_id)
                        .first()
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
                        currency=balance_sheet.currency if balance_sheet else None,
                        chunk_index=other_assets_result.get("chunk_index"),
                        is_valid=other_assets_result.get("is_valid", False),
                        validation_errors=json.dumps(
                            other_assets_result.get("validation_errors", [])
                        )
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
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Other assets extraction completed",
                    )
                else:
                    additional_item_errors.append("other assets")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Other assets extraction failed or no line items found",
                    )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Skipping other assets extraction for earnings announcement",
                )

            # Extract other liabilities (skip for earnings announcements)
            if document.document_type != DocumentType.EARNINGS_ANNOUNCEMENT:
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Extracting other liabilities line items",
                )
                other_liabilities_result = None

                # For non-earnings announcements, use the extractor
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
                            OtherLiabilitiesLineItem.other_liabilities_id
                            == existing_other_liabilities.id
                        ).delete()
                        db_session.delete(existing_other_liabilities)
                        db_session.commit()

                    other_liabilities = OtherLiabilities(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        time_period=time_period,
                        currency=balance_sheet.currency if balance_sheet else None,
                        chunk_index=other_liabilities_result.get("chunk_index"),
                        is_valid=other_liabilities_result.get("is_valid", False),
                        validation_errors=json.dumps(
                            other_liabilities_result.get("validation_errors", [])
                        )
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
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Other liabilities extraction completed",
                    )
                else:
                    additional_item_errors.append("other liabilities")
                    add_log(
                        document_id,
                        FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                        "Other liabilities extraction failed or no line items found",
                    )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    "Skipping other liabilities extraction for earnings announcement",
                )

            if additional_item_errors:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    MilestoneStatus.ERROR,
                    f"Additional items completed with errors: {', '.join(additional_item_errors)}",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    MilestoneStatus.COMPLETED,
                    "Additional items extraction completed",
                )

            # Classify non-operating items (balance sheet only for earnings announcements)
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.IN_PROGRESS,
                "Classifying non-operating items...",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                "Starting non-operating item classification",
            )

            # Only collect balance sheet items (earnings announcements don't have other assets/liabilities)
            non_operating_items = []
            if balance_sheet and balance_sheet.line_items:
                for item in balance_sheet.line_items:
                    non_operating_items.append(
                        {
                            "line_name": item.line_name,
                            "standardized_name": item.standardized_name,
                            "is_operating": item.is_operating,
                            "is_calculated": item.is_calculated,
                            "source": "balance_sheet",
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

                # Only save line_name, category, and source - everything else comes from balance sheet
                for idx, item in enumerate(classified_items):
                    db_session.add(
                        NonOperatingClassificationItem(
                            id=str(uuid.uuid4()),
                            classification_id=classification.id,
                            line_name=item.get("line_name"),
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
                FinancialStatementMilestone.INCOME_STATEMENT,
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
            # Find which milestones were in progress or pending and mark them as error
            milestones = current_progress.get("milestones", {})
            for milestone_key, milestone_data in milestones.items():
                if milestone_data.get("status") in [
                    MilestoneStatus.IN_PROGRESS.value,
                    MilestoneStatus.PENDING.value,
                ]:
                    try:
                        milestone = FinancialStatementMilestone(milestone_key)
                        update_milestone(
                            document_id,
                            milestone,
                            MilestoneStatus.ERROR,
                            f"Process failed: {str(e)}",
                        )
                    except Exception:
                        pass

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

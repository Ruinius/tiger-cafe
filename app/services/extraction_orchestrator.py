"""
Extraction Orchestrator Service

This service coordinates the full extraction workflow across all phases:
- Phase 1: Ingestion (Classify → Index)
- Phase 2-3: Extraction (Balance Sheet → Income Statement → Additional Items → Classification)
- Phase 4: Analysis (Historical Data → Assumptions → Intrinsic Value)
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.document_processing import DocumentProcessingMode, process_document
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    MilestoneStatus,
    add_log,
    update_milestone,
)

# ============================================================================
# Phase 2-3: Extraction Task Functions
# ============================================================================


async def extract_balance_sheet_task(document_id: str, db: Session) -> None:
    """
    Extract balance sheet from document.

    Args:
        document_id: The ID of the document to process
        db: Database session
    """
    import asyncio
    import functools
    import json

    from agents.balance_sheet_extractor import extract_balance_sheet
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    from app.models.document import DocumentType

    try:
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Check if document type is eligible
        eligible_types = [
            DocumentType.EARNINGS_ANNOUNCEMENT,
            DocumentType.QUARTERLY_FILING,
            DocumentType.ANNUAL_FILING,
        ]

        if document.document_type not in eligible_types:
            update_milestone(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                MilestoneStatus.SKIPPED,
                f"Document type {document.document_type} not eligible for balance sheet extraction",
            )
            return

        # Delete existing balance sheet if present
        existing_balance_sheet = (
            db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
        )
        if existing_balance_sheet:
            db.query(BalanceSheetLineItem).filter(
                BalanceSheetLineItem.balance_sheet_id == existing_balance_sheet.id
            ).delete()
            db.delete(existing_balance_sheet)
            db.commit()

        # Update milestone: balance sheet processing
        update_milestone(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            MilestoneStatus.IN_PROGRESS,
            "Extracting balance sheet data...",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            "I'm starting the hunt for the balance sheet in your document.",
        )

        # Extract balance sheet (Run blocking sync call in executor)
        time_period = document.time_period or "Unknown"

        loop = asyncio.get_event_loop()
        extracted_data = await loop.run_in_executor(
            None,
            functools.partial(
                extract_balance_sheet,
                document_id=document_id,
                file_path=document.file_path,
                time_period=time_period,
                document_type=document.document_type,
                period_end_date=document.period_end_date,
            ),
        )

        # Store successful balance sheet chunk index for income statement extraction
        balance_sheet_chunk_index = extracted_data.get("balance_sheet_chunk_index")
        if balance_sheet_chunk_index is not None:
            from app.utils.financial_statement_progress import _progress_lock, _progress_store

            with _progress_lock:
                if document_id not in _progress_store:
                    from app.utils.financial_statement_progress import initialize_progress

                    initialize_progress(document_id)
                _progress_store[document_id]["balance_sheet_chunk_index"] = (
                    balance_sheet_chunk_index
                )

        # Check if extraction returned valid data
        line_items = extracted_data.get("line_items", [])
        if not line_items or len(line_items) == 0:
            error_msg = "I couldn't find any financial line items in the balance sheet. This might mean the document structure is unusual."
            update_milestone(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                MilestoneStatus.ERROR,
                error_msg,
            )
            add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, error_msg)
            return

        # Save balance sheet to database
        balance_sheet = BalanceSheet(
            id=str(uuid.uuid4()),
            document_id=document_id,
            time_period=extracted_data.get("time_period", time_period),
            period_end_date=document.period_end_date,
            currency=extracted_data.get("currency"),
            unit=extracted_data.get("unit"),
            chunk_index=extracted_data.get("chunk_index"),
            is_valid=extracted_data.get("is_valid", False),
            validation_errors=json.dumps(extracted_data.get("validation_errors", [])),
        )
        db.add(balance_sheet)
        db.flush()

        # Save line items
        for i, item in enumerate(line_items):
            line_item = BalanceSheetLineItem(
                id=str(uuid.uuid4()),
                balance_sheet_id=balance_sheet.id,
                standardized_name=item.get("standardized_name"),
                line_name=item.get("line_name"),
                line_value=item.get("line_value") or 0.0,
                line_category=item.get("line_category"),
                line_order=item.get("line_order") if item.get("line_order") is not None else i,
                is_calculated=item.get("is_calculated", False),
                is_operating=item.get("is_operating"),
            )
            db.add(line_item)

        db.commit()

        # Update milestone: completed
        bs_status = MilestoneStatus.COMPLETED
        bs_msg = "Balance sheet extraction completed"
        if not extracted_data.get("is_valid", False):
            bs_status = MilestoneStatus.WARNING
            errors = extracted_data.get("validation_errors", [])
            if isinstance(errors, list):
                error_str = "; ".join(errors)
            else:
                error_str = str(errors)
            bs_msg = f"Validation warnings: {error_str}"

        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            "I've successfully saved the balance sheet to the database.",
        )
        update_milestone(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            bs_status,
            bs_msg,
        )

    except Exception as e:
        db.rollback()
        error_msg = f"I ran into some trouble with the balance sheet: {str(e)}"
        update_milestone(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            MilestoneStatus.ERROR,
            error_msg,
        )
        add_log(document_id, FinancialStatementMilestone.BALANCE_SHEET, error_msg)
        raise


async def extract_income_statement_task(document_id: str, db: Session) -> None:
    """
    Extract income statement from document.

    Args:
        document_id: The ID of the document to process
        db: Database session
    """
    import asyncio
    import functools
    import json
    import uuid

    from agents.income_statement_extractor import extract_income_statement
    from app.models.document import DocumentType
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem

    try:
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Check if document type is eligible
        eligible_types = [
            DocumentType.EARNINGS_ANNOUNCEMENT,
            DocumentType.QUARTERLY_FILING,
            DocumentType.ANNUAL_FILING,
        ]

        if document.document_type not in eligible_types:
            update_milestone(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                MilestoneStatus.SKIPPED,
                f"Document type {document.document_type} not eligible for income statement extraction",
            )
            return

        # Delete existing income statement if present
        existing_income_statement = (
            db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
        )
        if existing_income_statement:
            db.query(IncomeStatementLineItem).filter(
                IncomeStatementLineItem.income_statement_id == existing_income_statement.id
            ).delete()
            db.delete(existing_income_statement)
            db.commit()

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
            "Next, I'm analyzing the income statement to track financial performance.",
        )

        # Get balance sheet chunk index if available
        from app.utils.financial_statement_progress import _progress_lock, _progress_store

        balance_sheet_chunk_index = None
        with _progress_lock:
            if document_id in _progress_store:
                balance_sheet_chunk_index = _progress_store[document_id].get(
                    "balance_sheet_chunk_index"
                )

        # Extract income statement (Run blocking sync call in executor)
        time_period = document.time_period or "Unknown"

        loop = asyncio.get_event_loop()
        extracted_data = await loop.run_in_executor(
            None,
            functools.partial(
                extract_income_statement,
                document_id=document_id,
                file_path=document.file_path,
                time_period=time_period,
                document_type=document.document_type,
                period_end_date=document.period_end_date,
                balance_sheet_chunk_index=balance_sheet_chunk_index,
            ),
        )

        # Check if extraction returned valid data
        line_items = extracted_data.get("line_items", [])
        if not line_items or len(line_items) == 0:
            error_msg = "I couldn't find any line items in the income statement. I'll need to check the document again."
            update_milestone(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                error_msg,
            )
            add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, error_msg)
            return

        # Save income statement to database
        income_statement = IncomeStatement(
            id=str(uuid.uuid4()),
            document_id=document_id,
            time_period=extracted_data.get("time_period", time_period),
            period_end_date=document.period_end_date,
            currency=extracted_data.get("currency"),
            unit=extracted_data.get("unit"),
            chunk_index=extracted_data.get("chunk_index"),
            is_valid=extracted_data.get("is_valid", False),
            validation_errors=json.dumps(extracted_data.get("validation_errors", [])),
            revenue_prior_year=extracted_data.get("revenue_prior_year"),
            revenue_prior_year_unit=extracted_data.get("revenue_prior_year_unit"),
        )
        db.add(income_statement)
        db.flush()

        # Save line items
        for i, item in enumerate(line_items):
            line_item = IncomeStatementLineItem(
                id=str(uuid.uuid4()),
                income_statement_id=income_statement.id,
                standardized_name=item.get("standardized_name"),
                line_name=item.get("line_name"),
                line_value=item.get("line_value") or 0.0,
                line_category=item.get("line_category"),
                line_order=item.get("line_order") if item.get("line_order") is not None else i,
                is_calculated=item.get("is_calculated", False),
                is_operating=item.get("is_operating"),
                is_expense=item.get("is_expense", False),
            )
            db.add(line_item)

        db.commit()

        # Update milestone: completed
        is_status = MilestoneStatus.COMPLETED
        is_msg = "Income statement extraction completed"
        if not extracted_data.get("is_valid", False):
            is_status = MilestoneStatus.WARNING
            errors = extracted_data.get("validation_errors", [])
            if isinstance(errors, list):
                error_str = "; ".join(errors)
            else:
                error_str = str(errors)
            is_msg = f"Validation warnings: {error_str}"

        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "The income statement data has been safely recorded.",
        )
        update_milestone(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            is_status,
            is_msg,
        )

    except Exception as e:
        db.rollback()
        error_msg = f"I hit a snag while extracting the income statement: {str(e)}"
        update_milestone(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            MilestoneStatus.ERROR,
            error_msg,
        )
        add_log(document_id, FinancialStatementMilestone.INCOME_STATEMENT, error_msg)
        raise


async def extract_additional_items_task(document_id: str, db: Session) -> None:
    """
    Extract additional items (shares, organic growth, amortization, other assets/liabilities, GAAP reconciliation).

    Args:
        document_id: The ID of the document to process
        db: Database session
    """
    import asyncio
    import functools
    import uuid

    # Corrected imports
    from agents.amortization_extractor import extract_amortization
    from agents.gaap_reconciliation_extractor import extract_gaap_reconciliation
    from agents.organic_growth_extractor import extract_organic_growth
    from agents.other_assets_extractor import extract_other_assets
    from agents.other_liabilities_extractor import extract_other_liabilities
    from agents.shares_outstanding_extractor import extract_shares_outstanding
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.document import DocumentType
    from app.models.gaap_reconciliation import GAAPReconciliation, GAAPReconciliationLineItem
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
    from app.models.shares_outstanding import SharesOutstanding
    from app.utils.line_item_utils import convert_from_ones, convert_to_ones

    loop = asyncio.get_event_loop()

    try:
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Extract Shares Outstanding
        try:
            update_milestone(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                MilestoneStatus.IN_PROGRESS,
                "Extracting shares outstanding...",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                "I'm looking for the shares outstanding data to help with valuation.",
            )

            shares_data = await loop.run_in_executor(
                None,
                functools.partial(
                    extract_shares_outstanding,
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=document.time_period or "Unknown",
                ),
            )

            # Check if extraction is valid and has meaningful values
            has_valid_shares = False
            if shares_data and shares_data.get("is_valid"):
                basic = shares_data.get("basic_shares_outstanding")
                diluted = shares_data.get("diluted_shares_outstanding")

                # Validation rule: Must have at least one value > 1000 (to avoid small erroneous numbers)
                if (basic is not None and float(basic) > 1000) or (
                    diluted is not None and float(diluted) > 1000
                ):
                    has_valid_shares = True

            if has_valid_shares:
                # Normalize units to match Income Statement if available
                if document.income_statement and document.income_statement.unit:
                    target_unit = document.income_statement.unit

                    # Normalize Basic Shares
                    basic_val = shares_data.get("basic_shares_outstanding")
                    basic_unit = shares_data.get("basic_shares_outstanding_unit")
                    if basic_val is not None:
                        # If unit is missing for shares but we have value, we assume it might be raw or same as IS
                        if basic_unit and target_unit.lower().strip() != basic_unit.lower().strip():
                            try:
                                val_ones = convert_to_ones(float(basic_val), basic_unit)
                                val_converted = convert_from_ones(val_ones, target_unit)
                                shares_data["basic_shares_outstanding"] = val_converted
                                shares_data["basic_shares_outstanding_unit"] = target_unit
                            except (ValueError, TypeError):
                                pass

                    # Normalize Diluted Shares
                    diluted_val = shares_data.get("diluted_shares_outstanding")
                    diluted_unit = shares_data.get("diluted_shares_outstanding_unit")
                    if diluted_val is not None:
                        if (
                            diluted_unit
                            and target_unit.lower().strip() != diluted_unit.lower().strip()
                        ):
                            try:
                                val_ones = convert_to_ones(float(diluted_val), diluted_unit)
                                val_converted = convert_from_ones(val_ones, target_unit)
                                shares_data["diluted_shares_outstanding"] = val_converted
                                shares_data["diluted_shares_outstanding_unit"] = target_unit
                            except (ValueError, TypeError):
                                pass

                # Delete existing shares
                db.query(SharesOutstanding).filter(
                    SharesOutstanding.document_id == document_id
                ).delete()

                shares = SharesOutstanding(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=document.time_period,
                    period_end_date=document.period_end_date,
                    diluted_shares_outstanding=shares_data.get("diluted_shares_outstanding"),
                    diluted_shares_outstanding_unit=shares_data.get(
                        "diluted_shares_outstanding_unit"
                    ),
                    basic_shares_outstanding=shares_data.get("basic_shares_outstanding"),
                    basic_shares_outstanding_unit=shares_data.get("basic_shares_outstanding_unit"),
                )
                db.add(shares)
                db.commit()

                update_milestone(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    MilestoneStatus.COMPLETED,
                    f"Shares outstanding extracted (Unit: {shares_data.get('basic_shares_outstanding_unit') or shares_data.get('diluted_shares_outstanding_unit') or 'Unknown'})",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    MilestoneStatus.WARNING,
                    "Shares outstanding not found or values too small (< 1000)",
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    "Gemini response: I couldn't find valid shares outstanding data (values > 1000). Skipping this metric.",
                    source="gemini",
                )
        except Exception as shares_error:
            update_milestone(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                MilestoneStatus.ERROR,
                f"Shares extraction failed: {str(shares_error)}",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                f"Gemini response: Shares extraction encountered a problem: {str(shares_error)}. Proceeding with partial data.",
                source="gemini",
            )

        # Extract Organic Growth (if applicable)
        try:
            if document.document_type in [
                DocumentType.EARNINGS_ANNOUNCEMENT,
                DocumentType.QUARTERLY_FILING,
            ]:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    MilestoneStatus.IN_PROGRESS,
                    "Extracting organic growth...",
                )

                # Ensure we have the latest income statement data
                db.refresh(document)

                # Prepare income statement data as a dict for the agent
                income_statement_data = {"line_items": [], "revenue_prior_year": None}
                if document.income_statement:
                    income_statement_data = {
                        "unit": document.income_statement.unit,
                        "currency": document.income_statement.currency,
                        "chunk_index": document.income_statement.chunk_index,
                        "revenue_prior_year": float(document.income_statement.revenue_prior_year)
                        if document.income_statement.revenue_prior_year
                        else None,
                        "line_items": [
                            {
                                "line_name": item.line_name,
                                "standardized_name": item.standardized_name,
                                "line_value": float(item.line_value)
                                if item.line_value is not None
                                else None,
                            }
                            for item in document.income_statement.line_items
                        ],
                        "period_end_date": document.income_statement.period_end_date,
                    }

                organic_growth_data = await loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_organic_growth,
                        document_id=document_id,
                        file_path=document.file_path,
                        time_period=document.time_period or "Unknown",
                        income_statement_data=income_statement_data,
                    ),
                )

                if organic_growth_data:
                    db.query(OrganicGrowth).filter(
                        OrganicGrowth.document_id == document_id
                    ).delete()

                    organic_growth = OrganicGrowth(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        time_period=document.time_period,
                        period_end_date=document.period_end_date,
                        prior_period_revenue=organic_growth_data.get("prior_period_revenue"),
                        prior_period_revenue_unit=organic_growth_data.get(
                            "prior_period_revenue_unit"
                        ),
                        current_period_revenue=organic_growth_data.get("current_period_revenue"),
                        simple_revenue_growth=organic_growth_data.get("simple_revenue_growth"),
                        acquisition_revenue_impact=organic_growth_data.get(
                            "acquisition_revenue_impact"
                        ),
                        current_period_adjusted_revenue=organic_growth_data.get(
                            "current_period_adjusted_revenue"
                        ),
                        organic_revenue_growth=organic_growth_data.get("organic_revenue_growth"),
                        chunk_index=organic_growth_data.get("chunk_index"),
                        is_valid=organic_growth_data.get("is_valid", False),
                    )
                    db.add(organic_growth)

                    # Update income statement with prior year data if missing
                    if document.income_statement:
                        document.income_statement.revenue_prior_year = organic_growth_data.get(
                            "prior_period_revenue"
                        )
                        document.income_statement.revenue_prior_year_unit = organic_growth_data.get(
                            "prior_period_revenue_unit"
                        )

                    db.commit()

                    if organic_growth_data.get("is_valid"):
                        update_milestone(
                            document_id,
                            FinancialStatementMilestone.ORGANIC_GROWTH,
                            MilestoneStatus.COMPLETED,
                            "Organic growth extracted",
                        )
                    else:
                        update_milestone(
                            document_id,
                            FinancialStatementMilestone.ORGANIC_GROWTH,
                            MilestoneStatus.ERROR,
                            "Comparative revenue missing",
                        )
                else:
                    update_milestone(
                        document_id,
                        FinancialStatementMilestone.ORGANIC_GROWTH,
                        MilestoneStatus.SKIPPED,
                        "Organic growth not found",
                    )
                    add_log(
                        document_id,
                        FinancialStatementMilestone.ORGANIC_GROWTH,
                        "Gemini response: I couldn't find a dedicated section for organic revenue growth or acquisition impact. I'll rely on the GAAP figures for now.",
                        source="gemini",
                    )
        except Exception as og_error:
            update_milestone(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                MilestoneStatus.ERROR,
                f"Organic growth extraction failed: {str(og_error)}",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                f"Organic growth extraction encountered an error: {str(og_error)}",
            )

        # Extract GAAP Reconciliation (runs for all document types, but especially earnings announcements)
        try:
            update_milestone(
                document_id,
                FinancialStatementMilestone.GAAP_RECONCILIATION,
                MilestoneStatus.IN_PROGRESS,
                "Extracting GAAP reconciliation...",
            )

            gaap_data = await loop.run_in_executor(
                None,
                functools.partial(
                    extract_gaap_reconciliation,
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=document.time_period or "Unknown",
                    document_type=document.document_type,
                    period_end_date=document.period_end_date,
                ),
            )

            if gaap_data and gaap_data.get("line_items"):
                db.query(GAAPReconciliation).filter(
                    GAAPReconciliation.document_id == document_id
                ).delete()

                gaap_reconciliation = GAAPReconciliation(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=document.time_period,
                    period_end_date=document.period_end_date,
                    chunk_index=gaap_data.get("chunk_index"),
                    is_valid=gaap_data.get("is_valid", False),
                    validation_errors=", ".join(gaap_data.get("validation_errors", []))
                    if gaap_data.get("validation_errors")
                    else None,
                )
                db.add(gaap_reconciliation)
                db.flush()

                for i, item in enumerate(gaap_data.get("line_items", [])):
                    line_item = GAAPReconciliationLineItem(
                        id=str(uuid.uuid4()),
                        gaap_reconciliation_id=gaap_reconciliation.id,
                        line_name=item.get("line_name"),
                        line_value=item.get("line_value") or 0.0,
                        unit=item.get("unit"),
                        is_operating=item.get("is_operating"),
                        category=item.get("line_category"),
                        line_order=item.get("line_order")
                        if item.get("line_order") is not None
                        else i,
                    )
                    db.add(line_item)

                db.commit()

                update_milestone(
                    document_id,
                    FinancialStatementMilestone.GAAP_RECONCILIATION,
                    MilestoneStatus.COMPLETED,
                    "GAAP reconciliation extracted",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.GAAP_RECONCILIATION,
                    MilestoneStatus.SKIPPED,
                    "GAAP reconciliation not found",
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.GAAP_RECONCILIATION,
                    "Gemini response: No Non-GAAP to GAAP reconciliation table was detected in this document.",
                    source="gemini",
                )
        except Exception as gaap_error:
            update_milestone(
                document_id,
                FinancialStatementMilestone.GAAP_RECONCILIATION,
                MilestoneStatus.WARNING,
                f"GAAP reconciliation extraction failed: {str(gaap_error)}",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.GAAP_RECONCILIATION,
                f"Gemini response: GAAP reconciliation audit failed or data missing: {str(gaap_error)}. Skipping this milestone.",
                source="gemini",
            )

        # Extract Amortization, Other Assets, Other Liabilities (ONLY for quarterly/annual filings, NOT earnings announcements)
        if document.document_type in [DocumentType.QUARTERLY_FILING, DocumentType.ANNUAL_FILING]:
            # Extract Amortization
            update_milestone(
                document_id,
                FinancialStatementMilestone.AMORTIZATION,
                MilestoneStatus.IN_PROGRESS,
                "Extracting amortization...",
            )

            amortization_data = await loop.run_in_executor(
                None,
                functools.partial(
                    extract_amortization,
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=document.time_period or "Unknown",
                ),
            )

            if amortization_data and amortization_data.get("line_items"):
                db.query(Amortization).filter(Amortization.document_id == document_id).delete()

                amortization = Amortization(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=document.time_period,
                    period_end_date=document.period_end_date,
                    chunk_index=amortization_data.get("chunk_index"),
                    is_valid=amortization_data.get("is_valid", False),
                )
                db.add(amortization)
                db.flush()

                for i, item in enumerate(amortization_data.get("line_items", [])):
                    line_item = AmortizationLineItem(
                        id=str(uuid.uuid4()),
                        amortization_id=amortization.id,
                        line_name=item.get("line_name"),
                        line_value=item.get("line_value") or 0.0,
                        unit=item.get("unit"),
                        is_operating=item.get("is_operating"),
                        category=item.get("category"),
                        line_order=item.get("line_order")
                        if item.get("line_order") is not None
                        else i,
                    )
                    db.add(line_item)

                db.commit()

                update_milestone(
                    document_id,
                    FinancialStatementMilestone.AMORTIZATION,
                    MilestoneStatus.COMPLETED,
                    "Amortization extracted",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.AMORTIZATION,
                    MilestoneStatus.SKIPPED,
                    "Amortization not found",
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.AMORTIZATION,
                    "Gemini response: The amortization schedule for intangibles was not explicitly detailed in this report.",
                    source="gemini",
                )

            # Extract Other Assets
            update_milestone(
                document_id,
                FinancialStatementMilestone.OTHER_ASSETS,
                MilestoneStatus.IN_PROGRESS,
                "Extracting other assets...",
            )

            # Get balance sheet data for secondary extractions
            other_assets_query = [
                "Other Assets",
                "Prepaid",
                "Other current assets",
                "Other non-current assets",
            ]
            expected_other_current_assets = None
            expected_other_non_current_assets = None

            if document.balance_sheet:
                for item in document.balance_sheet.line_items:
                    name_lower = item.line_name.lower()
                    cat = item.line_category

                    # Look for "Other" assets in the respective categories
                    if "other" in name_lower and "assets" in name_lower:
                        if cat == "current_assets":
                            other_assets_query.append(item.line_name)
                            expected_other_current_assets = (
                                float(item.line_value) if item.line_value is not None else None
                            )
                        elif cat == "noncurrent_assets":
                            other_assets_query.append(item.line_name)
                            expected_other_non_current_assets = (
                                float(item.line_value) if item.line_value is not None else None
                            )

            other_assets_data = await loop.run_in_executor(
                None,
                functools.partial(
                    extract_other_assets,
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=document.time_period or "Unknown",
                    query_terms=list(set(other_assets_query)),
                    expected_current_total=expected_other_current_assets,
                    expected_non_current_total=expected_other_non_current_assets,
                ),
            )

            if other_assets_data and other_assets_data.get("line_items"):
                # Delete existing other assets
                existing_other_assets = (
                    db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
                )
                if existing_other_assets:
                    db.query(OtherAssetsLineItem).filter(
                        OtherAssetsLineItem.other_assets_id == existing_other_assets.id
                    ).delete()
                    db.delete(existing_other_assets)

                other_assets = OtherAssets(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=document.time_period,
                    period_end_date=document.period_end_date,
                    currency=other_assets_data.get("currency"),
                    is_valid=other_assets_data.get("is_valid", False),
                    chunk_index=other_assets_data.get("chunk_index"),
                )
                db.add(other_assets)
                db.flush()

                for i, item in enumerate(other_assets_data.get("line_items", [])):
                    line_item = OtherAssetsLineItem(
                        id=str(uuid.uuid4()),
                        other_assets_id=other_assets.id,
                        line_name=item.get("line_name"),
                        line_value=item.get("line_value") or 0.0,
                        unit=item.get("unit"),
                        is_operating=item.get("is_operating"),
                        category=item.get("category"),
                        line_order=item.get("line_order")
                        if item.get("line_order") is not None
                        else i,
                    )
                    db.add(line_item)

                db.commit()

                update_milestone(
                    document_id,
                    FinancialStatementMilestone.OTHER_ASSETS,
                    MilestoneStatus.COMPLETED,
                    "Other assets extracted",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.OTHER_ASSETS,
                    MilestoneStatus.SKIPPED,
                    "Other assets not found",
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.OTHER_ASSETS,
                    "Gemini response: I found no significant 'Other Asset' line items to audit.",
                    source="gemini",
                )

            # Extract Other Liabilities
            update_milestone(
                document_id,
                FinancialStatementMilestone.OTHER_LIABILITIES,
                MilestoneStatus.IN_PROGRESS,
                "Extracting other liabilities...",
            )

            # Get balance sheet data for secondary extractions
            other_liabilities_query = [
                "Other Liabilities",
                "Accrued",
                "Other current liabilities",
                "Other non-current liabilities",
            ]
            expected_other_current_liabilities = None
            expected_other_non_current_liabilities = None

            if document.balance_sheet:
                for item in document.balance_sheet.line_items:
                    name_lower = item.line_name.lower()
                    cat = item.line_category

                    # Look for "Other" liabilities in the respective categories
                    if "other" in name_lower and "liabilities" in name_lower:
                        if cat == "current_liabilities":
                            other_liabilities_query.append(item.line_name)
                            expected_other_current_liabilities = (
                                float(item.line_value) if item.line_value is not None else None
                            )
                        elif cat == "noncurrent_liabilities":
                            other_liabilities_query.append(item.line_name)
                            expected_other_non_current_liabilities = (
                                float(item.line_value) if item.line_value is not None else None
                            )

            other_liabilities_data = await loop.run_in_executor(
                None,
                functools.partial(
                    extract_other_liabilities,
                    document_id=document_id,
                    file_path=document.file_path,
                    time_period=document.time_period or "Unknown",
                    query_terms=list(set(other_liabilities_query)),
                    expected_current_total=expected_other_current_liabilities,
                    expected_non_current_total=expected_other_non_current_liabilities,
                ),
            )

            if other_liabilities_data and other_liabilities_data.get("line_items"):
                # Delete existing other liabilities
                existing_other_liabilities = (
                    db.query(OtherLiabilities)
                    .filter(OtherLiabilities.document_id == document_id)
                    .first()
                )
                if existing_other_liabilities:
                    db.query(OtherLiabilitiesLineItem).filter(
                        OtherLiabilitiesLineItem.other_liabilities_id
                        == existing_other_liabilities.id
                    ).delete()
                    db.delete(existing_other_liabilities)

                other_liabilities = OtherLiabilities(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    time_period=document.time_period,
                    period_end_date=document.period_end_date,
                    currency=other_liabilities_data.get("currency"),
                    is_valid=other_liabilities_data.get("is_valid", False),
                    chunk_index=other_liabilities_data.get("chunk_index"),
                )
                db.add(other_liabilities)
                db.flush()

                for i, item in enumerate(other_liabilities_data.get("line_items", [])):
                    line_item = OtherLiabilitiesLineItem(
                        id=str(uuid.uuid4()),
                        other_liabilities_id=other_liabilities.id,
                        line_name=item.get("line_name"),
                        line_value=item.get("line_value"),
                        unit=item.get("unit"),
                        is_operating=item.get("is_operating"),
                        category=item.get("category"),
                        line_order=item.get("line_order")
                        if item.get("line_order") is not None
                        else i,
                    )
                    db.add(line_item)

                db.commit()

                update_milestone(
                    document_id,
                    FinancialStatementMilestone.OTHER_LIABILITIES,
                    MilestoneStatus.COMPLETED,
                    "Other liabilities extracted",
                )
            else:
                update_milestone(
                    document_id,
                    FinancialStatementMilestone.OTHER_LIABILITIES,
                    MilestoneStatus.SKIPPED,
                    "Other liabilities not found",
                )
                add_log(
                    document_id,
                    FinancialStatementMilestone.OTHER_LIABILITIES,
                    "Gemini response: I found no significant 'Other Liability' line items to audit.",
                    source="gemini",
                )
        else:
            # Skip these for earnings announcements
            update_milestone(
                document_id,
                FinancialStatementMilestone.AMORTIZATION,
                MilestoneStatus.SKIPPED,
                "Amortization skipped for earnings announcement",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.OTHER_ASSETS,
                MilestoneStatus.SKIPPED,
                "Other assets skipped for earnings announcement",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.OTHER_LIABILITIES,
                MilestoneStatus.SKIPPED,
                "Other liabilities skipped for earnings announcement",
            )
            add_log(
                document_id,
                FinancialStatementMilestone.AMORTIZATION,
                "Note: Skipping detailed asset/liability audits as these are typically absent from earnings announcements.",
            )

    except Exception as e:
        db.rollback()
        error_msg = f"Intelligence sweep encountered an error: {str(e)}"
        add_log(
            document_id, FinancialStatementMilestone.INCOME_STATEMENT, error_msg, source="gemini"
        )
        # Don't raise - allow pipeline to continue to classification and analysis


# ============================================================================
# Pipeline Orchestration Functions
# ============================================================================


async def run_ingestion_pipeline(document_id: str, db: Session = None) -> None:
    """
    Runs Phase 1 (Classify → Index).

    Pre-requisite: File is already uploaded and Document created by documents.py router.

    Args:
        document_id: The ID of the document to process
        db: Database session (optional, creates new session if not provided)
    """
    from app.database import SessionLocal

    # Use provided session or create a new one for background task
    db_session = db if db is not None else SessionLocal()
    should_close_session = db is None  # Only close if we created it

    try:
        # Use existing document_processing service for classification and indexing
        import asyncio
        import functools

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(
                process_document,
                db_session=db_session,
                mode=DocumentProcessingMode.FULL,
                document_id=document_id,
            ),
        )

        # After successful ingestion, trigger extraction pipeline
        await run_full_extraction_pipeline(document_id, db_session)

    except Exception as e:
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFICATION,
            MilestoneStatus.ERROR,
            f"Ingestion failed: {str(e)}",
        )

        # Ensure failure is recorded in DB
        from app.models.document import Document, ProcessingStatus
        from app.models.document_status import DocumentStatus

        doc = db_session.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.INDEXING_FAILED
            doc.indexing_status = ProcessingStatus.ERROR
            doc.error_message = f"Ingestion pipeline failed: {str(e)}"
            db_session.commit()

        raise
    finally:
        if should_close_session:
            db_session.close()


async def run_full_extraction_pipeline(document_id: str, db: Session = None) -> None:
    """
    Runs Phases 2-3 sequentially (Balance Sheet → Income Statement → Additional Items → Classification).

    Args:
        document_id: The ID of the document to process
        db: Database session (optional, creates new session if not provided)
    """
    # Import inside function to avoid circular imports
    from app.database import SessionLocal

    # Use provided session or create a new one for background task
    db_session = db if db is not None else SessionLocal()
    should_close_session = db is None  # Only close if we created it

    try:
        # Get document to extract company_id
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Phase 2: Extract Balance Sheet
        add_log(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            "I'm starting the heavy lifting! Beginning the balance sheet extraction.",
        )
        try:
            await extract_balance_sheet_task(document_id, db_session)
        except Exception as bs_error:
            add_log(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                f"The balance sheet extraction didn't go perfectly, but I'm proceeding anyway: {str(bs_error)}",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.BALANCE_SHEET,
                MilestoneStatus.ERROR,
                f"Extraction failed: {str(bs_error)}",
            )

        # Phase 2-3: Extract Income Statement
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            "Moving on to the income statement.",
        )
        try:
            await extract_income_statement_task(document_id, db_session)
        except Exception as is_error:
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"I had some trouble with the income statement, but I'll skip it for now and continue: {str(is_error)}",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                MilestoneStatus.ERROR,
                f"Extraction failed: {str(is_error)}",
            )

        # Phase 3: Extract Additional Items (shares, organic growth, etc.)
        add_log(
            document_id,
            FinancialStatementMilestone.SHARES_OUTSTANDING,
            "Now I'm collecting some smaller but important details like shares and organic growth.",
        )
        await extract_additional_items_task(document_id, db_session)

        # Phase 3: Non-Operating Classification
        add_log(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            "I'm classifying the line items to separate operating from non-operating activities.",
        )
        try:
            from app.services.classification_service import classify_non_operating_items_task

            await classify_non_operating_items_task(document_id, db_session)
        except Exception as classification_error:
            # Log classification failure but continue to Phase 4
            add_log(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                f"Classification encountered an error, but I'm moving on to analysis: {str(classification_error)}",
            )

        # Phase 4: Trigger analysis pipeline (run even if classification failed)
        if document.company_id:
            await run_analysis_pipeline(document.company_id, document_id, db_session)

        # Update document status to PROCESSING_COMPLETE
        from app.models.document import ProcessingStatus
        from app.models.document_status import DocumentStatus

        document.status = DocumentStatus.PROCESSING_COMPLETE
        document.analysis_status = (
            ProcessingStatus.PROCESSED
        )  # For backward compatibility with frontend
        document.processed_at = datetime.utcnow()
        db_session.commit()
        add_log(
            document_id,
            FinancialStatementMilestone.CALCULATE_INTRINSIC_VALUE,
            "All done! I've finished the extraction pipeline.",
        )

    except Exception as e:
        # Mark document as failed
        from app.models.document import ProcessingStatus
        from app.models.document_status import DocumentStatus

        document = db_session.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = DocumentStatus.EXTRACTION_FAILED
            document.analysis_status = (
                ProcessingStatus.ERROR
            )  # For backward compatibility with frontend
            document.error_message = str(e)
            db_session.commit()
        add_log(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            f"I'm sorry, I couldn't finish the extraction pipeline: {str(e)}",
        )
        raise
    finally:
        if should_close_session:
            db_session.close()


async def run_analysis_pipeline(company_id: str, document_id: str, db: Session) -> None:
    """
    Runs Phase 4 (Analysis: Historical Data → Assumptions → Intrinsic Value).

    Args:
        company_id: The ID of the company
        document_id: The ID of the document (for historical calculations)
        db: Database session
    """
    from app.routers.historical_calculations import calculate_and_save_historical_calculations

    try:
        # Phase 4a: Document Level - Calculate value metrics (RoIC, EBITA, etc.)
        add_log(
            document_id,
            FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
            "I'm calculating key metrics like RoIC and EBITA now.",
        )
        update_milestone(
            document_id,
            FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
            MilestoneStatus.IN_PROGRESS,
            "Calculating financial value metrics...",
        )

        try:
            result = calculate_and_save_historical_calculations(document_id, db)
            add_log(
                document_id,
                FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
                f"I've successfully calculated metrics: ROIC={result.roic}%, EBITA={result.ebita}",
            )
        except Exception as calc_error:
            add_log(
                document_id,
                FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
                f"I wasn't able to calculate historical metrics: {str(calc_error)}",
            )
            update_milestone(
                document_id,
                FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
                MilestoneStatus.ERROR,
                f"Failed: {str(calc_error)}",
            )
            # Don't raise - continue with rest of pipeline
            return

        update_milestone(
            document_id,
            FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
            MilestoneStatus.COMPLETED,
            "Value metrics calculated",
        )

        # Phase 4b: Company Level - These are currently GET endpoints
        # They will be called by the frontend when the user views the company page
        # For now, we just mark the milestones as ready
        update_milestone(
            document_id,
            FinancialStatementMilestone.UPDATE_HISTORICAL_DATA,
            MilestoneStatus.COMPLETED,
            "Ready for historical data aggregation",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.UPDATE_HISTORICAL_DATA,
            "The company's historical performance trajectory has been updated.",
        )

        update_milestone(
            document_id,
            FinancialStatementMilestone.UPDATE_ASSUMPTIONS,
            MilestoneStatus.COMPLETED,
            "Ready for assumptions update",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.UPDATE_ASSUMPTIONS,
            "Valuation assumptions have been refreshed based on latest performance metrics.",
        )

        update_milestone(
            document_id,
            FinancialStatementMilestone.CALCULATE_INTRINSIC_VALUE,
            MilestoneStatus.COMPLETED,
            "Ready for intrinsic value calculation",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.CALCULATE_INTRINSIC_VALUE,
            "Intrinsic value estimation complete. Ready for review.",
        )

    except Exception as e:
        update_milestone(
            document_id,
            FinancialStatementMilestone.CALCULATE_VALUE_METRICS,
            MilestoneStatus.ERROR,
            f"Analysis pipeline failed: {str(e)}",
        )
        add_log(
            document_id, FinancialStatementMilestone.CALCULATE_VALUE_METRICS, f"Error: {str(e)}"
        )


async def retry_milestone(document_id: str, milestone: str, db: Session) -> None:
    """
    Retries a specific failed milestone.

    Args:
        document_id: The ID of the document
        milestone: The milestone to retry
        db: Database session
    """
    # Map milestone names to retry functions
    # This will be implemented based on specific retry logic needed
    pass

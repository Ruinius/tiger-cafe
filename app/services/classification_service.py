"""
Classification Service

Handles non-operating classification logic for balance sheet and income statement line items.
"""

from sqlalchemy.orm import Session

from app.models.document import Document
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    MilestoneStatus,
    add_log,
    update_milestone,
)


async def classify_non_operating_items_task(document_id: str, db: Session) -> None:
    """
    Runs the classification agent and saves results.

    This is a post-processing step that operates on already-extracted data.

    Args:
        document_id: The ID of the document
        db: Database session
    """
    # Import here to avoid circular dependencies
    import asyncio
    import functools
    import uuid

    from app.app_agents.non_operating_classifier import classify_non_operating_items
    from app.models.balance_sheet import BalanceSheet
    from app.models.income_statement import IncomeStatement
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )

    try:
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            MilestoneStatus.IN_PROGRESS,
            "Classifying non-operating items...",
        )

        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get balance sheet
        balance_sheet = (
            db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
        )
        if not balance_sheet:
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.WARNING,
                "No balance sheet found for classification",
            )
            return

        # Get income statement
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()

        # Prepare balance sheet data
        balance_sheet_data = {
            "line_items": [
                {
                    "line_name": item.line_name,
                    "line_value": item.line_value,
                    "standardized_name": item.standardized_name,
                    "is_operating": item.is_operating,
                    "is_calculated": item.is_calculated,
                }
                for item in balance_sheet.line_items
            ],
            "time_period": balance_sheet.time_period,
            "currency": balance_sheet.currency,
            "unit": balance_sheet.unit,
        }

        # Run classification (Run blocking sync call in executor)
        add_log(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            f"I'm now analyzing {len(balance_sheet_data['line_items'])} line items to separate core operations from other activities.",
        )

        loop = asyncio.get_event_loop()
        classification_result = await loop.run_in_executor(
            None,
            functools.partial(
                classify_non_operating_items,
                document_id=document_id,
                file_path=document.file_path,
                balance_sheet_data=balance_sheet_data,
                time_period=document.time_period,
            ),
        )

        add_log(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            f"Analysis complete! I've successfully categorized {len(classification_result.get('line_items', []))} items.",
        )

        if not classification_result or not classification_result.get("line_items"):
            update_milestone(
                document_id,
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
                MilestoneStatus.WARNING,
                "No classification results returned",
            )
            return

        # Delete existing classification if any
        existing = (
            db.query(NonOperatingClassification)
            .filter(NonOperatingClassification.document_id == document_id)
            .first()
        )
        if existing:
            db.query(NonOperatingClassificationItem).filter(
                NonOperatingClassificationItem.classification_id == existing.id
            ).delete()
            db.delete(existing)
            db.commit()

        # Create new classification
        classification = NonOperatingClassification(
            id=str(uuid.uuid4()),
            document_id=document_id,
            time_period=document.time_period,
            period_end_date=document.period_end_date,
        )
        db.add(classification)
        db.commit()
        db.refresh(classification)

        # Add classification items
        for idx, item in enumerate(classification_result.get("line_items", [])):
            classification_item = NonOperatingClassificationItem(
                id=str(uuid.uuid4()),
                classification_id=classification.id,
                line_name=item.get("line_name"),
                category=item.get("category"),
                source=item.get("source"),
                line_order=idx,
            )
            db.add(classification_item)

        db.commit()

        # Update balance sheet items with is_operating flag
        for item in balance_sheet.line_items:
            classification_item = next(
                (
                    ci
                    for ci in classification_result.get("line_items", [])
                    if ci.get("line_name") == item.line_name
                ),
                None,
            )
            if classification_item:
                item.is_operating = classification_item.get("category") == "operating"

        db.commit()

        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            MilestoneStatus.COMPLETED,
            f"Classified {len(classification_result.get('line_items', []))} items",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            "I've finished the non-operating classification process.",
        )

    except Exception as e:
        update_milestone(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            MilestoneStatus.ERROR,
            f"Classification failed: {str(e)}",
        )
        add_log(
            document_id,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            f"Error: {str(e)}",
        )
        raise

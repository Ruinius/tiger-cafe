"""
Progress tracking for financial statement processing
"""

import threading
from datetime import datetime
from enum import Enum


class MilestoneStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    WARNING = "warning"  # New status for non-fatal issues
    SKIPPED = "skipped"


class FinancialStatementMilestone(Enum):
    # Phase 1: Ingestion
    UPLOAD = "upload"
    CLASSIFICATION = "classification"
    INDEX = "index"
    # Phase 2: Core Extraction
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    SHARES_OUTSTANDING = "shares_outstanding"
    ORGANIC_GROWTH = "organic_growth"
    GAAP_RECONCILIATION = "gaap_reconciliation"
    # Phase 3: Additional Extraction
    AMORTIZATION = "amortization"
    OTHER_ASSETS = "other_assets"
    OTHER_LIABILITIES = "other_liabilities"
    CLASSIFYING_NON_OPERATING_ITEMS = "classifying_non_operating_items"
    # Phase 4: Analysis
    CALCULATE_VALUE_METRICS = "calculate_value_metrics"  # Document-level: RoIC, EBITA, etc.
    UPDATE_HISTORICAL_DATA = "update_historical_data"  # Company-level: Aggregation
    UPDATE_ASSUMPTIONS = "update_assumptions"
    CALCULATE_INTRINSIC_VALUE = "calculate_intrinsic_value"


# In-memory progress store (in production, use Redis or database)
_progress_store: dict[str, dict] = {}
_progress_lock = threading.Lock()


def update_milestone(
    document_id: str,
    milestone: FinancialStatementMilestone,
    status: MilestoneStatus,
    message: str | None = None,
    source: str = "system",
):
    """Update the status of a specific milestone"""
    with _progress_lock:
        if document_id not in _progress_store:
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

        milestone_data = _progress_store[document_id]["milestones"].get(milestone.value, {})

        # Preserve existing logs if they exist, otherwise initialize empty list
        logs = milestone_data.get("logs", [])

        # If message is provided, add it to logs
        if message:
            logs.append(
                {
                    "message": message,
                    "source": source,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            # Keep only last 20 logs to prevent unbounded growth
            logs = logs[-20:]

        _progress_store[document_id]["milestones"][milestone.value] = {
            "status": status.value,
            "message": message,  # Keep latest message for backward compatibility
            "logs": logs,  # Store all log messages
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()


def add_log(
    document_id: str,
    milestone: FinancialStatementMilestone,
    log_message: str,
    source: str = "system",
):
    """Add a log message to a milestone without changing its status"""
    # Print to terminal for visibility
    print(f"[{milestone.value}] {log_message}")

    with _progress_lock:
        if document_id not in _progress_store:
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

        milestone_data = _progress_store[document_id]["milestones"].get(
            milestone.value,
            {
                "status": MilestoneStatus.PENDING.value,
                "message": None,
                "logs": [],
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        logs = milestone_data.get("logs", [])
        logs.append(
            {
                "message": log_message,
                "source": source,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        # Keep only last 20 logs to prevent unbounded growth
        logs = logs[-20:]

        # Update the milestone with new log, preserving status and latest message
        _progress_store[document_id]["milestones"][milestone.value] = {
            "status": milestone_data.get("status", MilestoneStatus.PENDING.value),
            "message": log_message,  # Update latest message
            "logs": logs,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()


def get_progress(document_id: str) -> dict | None:
    """Get current progress for a document"""
    with _progress_lock:
        return _progress_store.get(document_id)


def clear_progress(document_id: str):
    """Clear progress for a document (e.g., when processing completes)"""
    with _progress_lock:
        if document_id in _progress_store:
            del _progress_store[document_id]


def initialize_progress(document_id: str, phase1_complete: bool = False):
    """
    Initialize progress tracking for a document with all 12 milestones.

    Args:
        document_id: The document ID
        phase1_complete: If True, marks Upload, Classification, and Index milestones as COMPLETED.
                        Useful for re-runs (memory loss) where we know Phase 1 is done.
    """
    with _progress_lock:
        milestones = {}
        # Initialize all 12 milestones
        for milestone in FinancialStatementMilestone:
            status = MilestoneStatus.PENDING.value

            # If phase1_complete is True, mark ingestion phase milestones as COMPLETED
            if phase1_complete and milestone in [
                FinancialStatementMilestone.UPLOAD,
                FinancialStatementMilestone.CLASSIFICATION,
                FinancialStatementMilestone.INDEX,
            ]:
                status = MilestoneStatus.COMPLETED.value

            milestones[milestone.value] = {
                "status": status,
                "message": None,
                "logs": [],
                "updated_at": datetime.utcnow().isoformat(),
            }

        _progress_store[document_id] = {
            "milestones": milestones,
            "last_updated": datetime.utcnow().isoformat(),
        }


def reset_balance_sheet_milestones(document_id: str):
    """Reset only balance sheet milestones to pending (for re-runs)"""
    with _progress_lock:
        if document_id not in _progress_store:
            # If no progress exists, create it with only balance sheet milestones
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

        # Only reset balance sheet milestones (don't touch income statement milestones)
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.BALANCE_SHEET.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()


def reset_income_statement_milestones(document_id: str):
    """Reset only income statement milestones to pending (for re-runs)"""
    with _progress_lock:
        if document_id not in _progress_store:
            # If no progress exists, create it with only income statement milestones
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

        # Reset income statement and all Phase 3 milestones (don't touch balance sheet)
        milestones_to_reset = [
            FinancialStatementMilestone.INCOME_STATEMENT,
            FinancialStatementMilestone.SHARES_OUTSTANDING,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            FinancialStatementMilestone.GAAP_RECONCILIATION,
            FinancialStatementMilestone.AMORTIZATION,
            FinancialStatementMilestone.OTHER_ASSETS,
            FinancialStatementMilestone.OTHER_LIABILITIES,
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS,
            FinancialStatementMilestone.UPDATE_HISTORICAL_DATA,
            FinancialStatementMilestone.UPDATE_ASSUMPTIONS,
            FinancialStatementMilestone.CALCULATE_INTRINSIC_VALUE,
        ]

        for milestone in milestones_to_reset:
            _progress_store[document_id]["milestones"][milestone.value] = {
                "status": MilestoneStatus.PENDING.value,
                "message": None,
                "logs": [],
                "updated_at": datetime.utcnow().isoformat(),
            }

        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()


def reset_all_milestones(document_id: str):
    """Reset all milestones to pending (for full re-runs)"""
    initialize_progress(document_id)
    # Mark Upload as completed since file exists
    update_milestone(
        document_id,
        FinancialStatementMilestone.UPLOAD,
        MilestoneStatus.COMPLETED,
        "Document already uploaded",
    )


def get_progress_with_db_fallback(document_id: str, db) -> dict | None:
    """
    Get progress from memory, falling back to DB check if memory is empty.
    Useful for multi-worker setups or server restarts.
    """
    # 1. Try memory first
    progress = get_progress(document_id)
    if progress:
        return progress

    # 2. Fallback: Check DB for existence of artifacts
    from app.models.amortization import Amortization
    from app.models.balance_sheet import BalanceSheet
    from app.models.gaap_reconciliation import GAAPReconciliation
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement
    from app.models.non_operating_classification import NonOperatingClassification
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets
    from app.models.other_liabilities import OtherLiabilities
    from app.models.shares_outstanding import SharesOutstanding

    milestones = {}

    # Helper to mark status based on object validity
    def mark_status(key, obj, is_valid_attr="is_valid", errors_attr="validation_errors"):
        status = MilestoneStatus.COMPLETED.value
        message = "Restored from database"

        if hasattr(obj, is_valid_attr):
            is_valid = getattr(obj, is_valid_attr)
            if is_valid is False:
                status = MilestoneStatus.WARNING.value
                if hasattr(obj, errors_attr):
                    errors_json = getattr(obj, errors_attr)
                    if errors_json:
                        import json

                        try:
                            errors = json.loads(errors_json)
                            if isinstance(errors, list):
                                message = f"Validation warnings: {'; '.join(errors)}"
                            else:
                                message = f"Validation warnings: {str(errors)}"
                        except Exception:
                            message = "Validation warnings (restored)"
                    else:
                        message = "Validation warnings (restored)"
                else:
                    message = "Validation warnings (restored)"

        milestones[key] = {"status": status, "message": message, "logs": []}

    # Balance Sheet
    bs = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    if bs:
        mark_status(FinancialStatementMilestone.BALANCE_SHEET.value, bs)

    # Income Statement
    is_obj = db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    if is_obj:
        mark_status(FinancialStatementMilestone.INCOME_STATEMENT.value, is_obj)

    # Shares Outstanding
    shares = (
        db.query(SharesOutstanding).filter(SharesOutstanding.document_id == document_id).first()
    )
    if shares:
        mark_status(FinancialStatementMilestone.SHARES_OUTSTANDING.value, shares)

    # Organic Growth
    og = db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    if og:
        mark_status(FinancialStatementMilestone.ORGANIC_GROWTH.value, og)

    # GAAP
    gaap = (
        db.query(GAAPReconciliation).filter(GAAPReconciliation.document_id == document_id).first()
    )
    if gaap:
        mark_status(FinancialStatementMilestone.GAAP_RECONCILIATION.value, gaap)

    # Amortization
    amort = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    if amort:
        mark_status(FinancialStatementMilestone.AMORTIZATION.value, amort)

    # Other Assets
    oa = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    if oa:
        mark_status(FinancialStatementMilestone.OTHER_ASSETS.value, oa)

    # Other Liabilities
    ol = db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    if ol:
        mark_status(FinancialStatementMilestone.OTHER_LIABILITIES.value, ol)

    # Classification
    noc = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )
    if noc:
        mark_status(FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS.value, noc)

    # Analysis
    hist = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )
    if hist:
        mark_status(FinancialStatementMilestone.UPDATE_HISTORICAL_DATA.value, hist)
        mark_status(FinancialStatementMilestone.UPDATE_ASSUMPTIONS.value, hist)
        mark_status(FinancialStatementMilestone.CALCULATE_INTRINSIC_VALUE.value, hist)
        mark_status(FinancialStatementMilestone.CALCULATE_VALUE_METRICS.value, hist)

    if not milestones:
        return None

    return {
        "document_id": document_id,
        "status": "completed",  # Estimate
        "milestones": milestones,
        "logs": [
            {"message": "Progress logic restored from existing database records", "timestamp": None}
        ],
    }

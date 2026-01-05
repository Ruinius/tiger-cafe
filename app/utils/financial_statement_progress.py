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


class FinancialStatementMilestone(Enum):
    EXTRACTING_BALANCE_SHEET = "extracting_balance_sheet"
    CLASSIFYING_BALANCE_SHEET = "classifying_balance_sheet"
    EXTRACTING_OTHER_ASSETS = "extracting_other_assets"
    EXTRACTING_OTHER_LIABILITIES = "extracting_other_liabilities"
    CLASSIFYING_NON_OPERATING_ITEMS = "classifying_non_operating_items"
    EXTRACTING_INCOME_STATEMENT = "extracting_income_statement"
    EXTRACTING_SHARES_OUTSTANDING = "extracting_shares_outstanding"
    EXTRACTING_AMORTIZATION = "extracting_amortization"
    EXTRACTING_ORGANIC_GROWTH = "extracting_organic_growth"
    CLASSIFYING_INCOME_STATEMENT = "classifying_income_statement"


# In-memory progress store (in production, use Redis or database)
_progress_store: dict[str, dict] = {}
_progress_lock = threading.Lock()


def update_milestone(
    document_id: str,
    milestone: FinancialStatementMilestone,
    status: MilestoneStatus,
    message: str | None = None,
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
):
    """Add a log message to a milestone without changing its status"""
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


def initialize_progress(document_id: str):
    """Initialize progress tracking for a document"""
    with _progress_lock:
        _progress_store[document_id] = {
            "milestones": {
                FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_OTHER_ASSETS.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_OTHER_LIABILITIES.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_AMORTIZATION.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "logs": [],
                    "updated_at": datetime.utcnow().isoformat(),
                },
            },
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
            FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_OTHER_ASSETS.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_OTHER_LIABILITIES.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS.value
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

        # Only reset income statement milestones (don't touch balance sheet milestones)
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_SHARES_OUTSTANDING.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_AMORTIZATION.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.EXTRACTING_ORGANIC_GROWTH.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["milestones"][
            FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT.value
        ] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "logs": [],
            "updated_at": datetime.utcnow().isoformat(),
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()


def reset_all_milestones(document_id: str):
    """Reset all milestones to pending (for full re-runs)"""
    initialize_progress(document_id)

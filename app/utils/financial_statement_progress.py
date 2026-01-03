"""
Progress tracking for financial statement processing
"""

from typing import Dict, Optional
from enum import Enum
from datetime import datetime
import threading

class MilestoneStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"

class FinancialStatementMilestone(Enum):
    EXTRACTING_BALANCE_SHEET = "extracting_balance_sheet"
    CLASSIFYING_BALANCE_SHEET = "classifying_balance_sheet"
    EXTRACTING_INCOME_STATEMENT = "extracting_income_statement"
    EXTRACTING_ADDITIONAL_ITEMS = "extracting_additional_items"
    CLASSIFYING_INCOME_STATEMENT = "classifying_income_statement"

# In-memory progress store (in production, use Redis or database)
_progress_store: Dict[str, Dict] = {}
_progress_lock = threading.Lock()

def update_milestone(document_id: str, milestone: FinancialStatementMilestone, status: MilestoneStatus, message: Optional[str] = None):
    """Update the status of a specific milestone"""
    with _progress_lock:
        if document_id not in _progress_store:
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat()
            }
        
        _progress_store[document_id]["milestones"][milestone.value] = {
            "status": status.value,
            "message": message,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()

def get_progress(document_id: str) -> Optional[Dict]:
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
                    "updated_at": datetime.utcnow().isoformat()
                },
                FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "updated_at": datetime.utcnow().isoformat()
                },
                FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "updated_at": datetime.utcnow().isoformat()
                },
                FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "updated_at": datetime.utcnow().isoformat()
                },
                FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT.value: {
                    "status": MilestoneStatus.PENDING.value,
                    "message": None,
                    "updated_at": datetime.utcnow().isoformat()
                }
            },
            "last_updated": datetime.utcnow().isoformat()
        }

def reset_balance_sheet_milestones(document_id: str):
    """Reset only balance sheet milestones to pending (for re-runs)"""
    with _progress_lock:
        if document_id not in _progress_store:
            # If no progress exists, create it with only balance sheet milestones
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat()
            }
        
        # Only reset balance sheet milestones (don't touch income statement milestones)
        _progress_store[document_id]["milestones"][FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET.value] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["milestones"][FinancialStatementMilestone.CLASSIFYING_BALANCE_SHEET.value] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()

def reset_income_statement_milestones(document_id: str):
    """Reset only income statement milestones to pending (for re-runs)"""
    with _progress_lock:
        if document_id not in _progress_store:
            # If no progress exists, create it with only income statement milestones
            _progress_store[document_id] = {
                "milestones": {},
                "last_updated": datetime.utcnow().isoformat()
            }
        
        # Only reset income statement milestones (don't touch balance sheet milestones)
        _progress_store[document_id]["milestones"][FinancialStatementMilestone.EXTRACTING_INCOME_STATEMENT.value] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["milestones"][FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS.value] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["milestones"][FinancialStatementMilestone.CLASSIFYING_INCOME_STATEMENT.value] = {
            "status": MilestoneStatus.PENDING.value,
            "message": None,
            "updated_at": datetime.utcnow().isoformat()
        }
        _progress_store[document_id]["last_updated"] = datetime.utcnow().isoformat()

def reset_all_milestones(document_id: str):
    """Reset all milestones to pending (for full re-runs)"""
    initialize_progress(document_id)


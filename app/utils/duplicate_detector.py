"""
Duplicate document detection utilities
"""

from sqlalchemy.orm import Session
from app.models.document import Document, DocumentType
from typing import Optional, Dict
from datetime import datetime


def check_duplicate_document(
    db: Session,
    company_id: str,
    document_type: DocumentType,
    time_period: Optional[str],
    filename: str,
    unique_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Check if a document is a duplicate based on company, type, and time period.
    For earnings, quarterly, and annual filings: checks company, type, and time period.
    For all other document types: checks unique_id if available.
    
    Args:
        db: Database session
        company_id: Company ID
        document_type: Type of document
        time_period: Time period string (e.g., "Q3 2024")
        filename: Original filename
        unique_id: Unique identifier for the document (URL, article ID, etc.)
    
    Returns:
        Dictionary with duplicate info if found, None otherwise:
        {
            "is_duplicate": True,
            "existing_document": Document object,
            "match_reason": "same_company_type_period", "same_filename", or "same_unique_id"
        }
    """
    
    # Check for duplicates based on company, type, and time period
    # For earnings, quarterly, and annual filings
    checkable_types = [
        DocumentType.EARNINGS_ANNOUNCEMENT,
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING
    ]
    
    if document_type in checkable_types:
        # First check: same company, type, and time period
        if time_period:
            existing = db.query(Document).filter(
                Document.company_id == company_id,
                Document.document_type == document_type,
                Document.time_period == time_period
            ).first()
            
            if existing:
                return {
                    "is_duplicate": True,
                    "existing_document": existing,
                    "match_reason": "same_company_type_period"
                }
        
        # Second check: same filename (case-insensitive)
        existing_by_filename = db.query(Document).filter(
            Document.company_id == company_id,
            Document.filename.ilike(filename)
        ).first()
        
        if existing_by_filename:
            return {
                "is_duplicate": True,
                "existing_document": existing_by_filename,
                "match_reason": "same_filename"
            }
    else:
        # For all other document types, check by unique_id
        if unique_id:
            existing_by_unique_id = db.query(Document).filter(
                Document.company_id == company_id,
                Document.unique_id == unique_id
            ).first()
            
            if existing_by_unique_id:
                return {
                    "is_duplicate": True,
                    "existing_document": existing_by_unique_id,
                    "match_reason": "same_unique_id"
                }
    
    return None


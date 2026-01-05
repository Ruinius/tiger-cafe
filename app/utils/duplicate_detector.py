"""
Duplicate document detection utilities
"""

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType, ProcessingStatus


def check_duplicate_document(
    db: Session,
    company_id: str,
    document_type: DocumentType,
    time_period: str | None,
    filename: str,
    unique_id: str | None = None,
    exclude_document_id: str | None = None,
) -> dict | None:
    """
    Check if a document is a duplicate based on company, type, and time period.
    For earnings announcements, quarterly filings, and annual filings: checks company, type, and time period (or filename).
    For all other document types (press releases, analyst reports, news articles, transcripts, etc.): checks unique_id if available.

    Note: Transcripts are treated like other event-based documents and use unique_id checking (document hash),
    not company+type+time_period checking, since multiple transcript versions of the same call may exist.

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
        DocumentType.ANNUAL_FILING,
    ]

    if document_type in checkable_types:
        # First check: same company, type, and time period
        # IMPORTANT: Only check against documents that are already INDEXED (not still processing)
        if time_period:
            query = db.query(Document).filter(
                Document.company_id == company_id,
                Document.document_type == document_type,
                Document.time_period == time_period,
                Document.indexing_status
                == ProcessingStatus.INDEXED,  # Only check indexed documents
            )
            if exclude_document_id:
                query = query.filter(Document.id != exclude_document_id)
            existing = query.first()

            if existing:
                return {
                    "is_duplicate": True,
                    "existing_document": existing,
                    "match_reason": "same_company_type_period",
                }

        # Second check: same filename (case-insensitive)
        # Only check against documents that are already INDEXED
        query = db.query(Document).filter(
            Document.company_id == company_id,
            Document.filename.ilike(filename),
            Document.indexing_status == ProcessingStatus.INDEXED,  # Only check indexed documents
        )
        if exclude_document_id:
            query = query.filter(Document.id != exclude_document_id)
        existing_by_filename = query.first()

        if existing_by_filename:
            return {
                "is_duplicate": True,
                "existing_document": existing_by_filename,
                "match_reason": "same_filename",
            }
    else:
        # For all other document types, check by unique_id
        # Only check against documents that are already INDEXED
        if unique_id:
            query = db.query(Document).filter(
                Document.company_id == company_id,
                Document.unique_id == unique_id,
                Document.indexing_status
                == ProcessingStatus.INDEXED,  # Only check indexed documents
            )
            if exclude_document_id:
                query = query.filter(Document.id != exclude_document_id)
            existing_by_unique_id = query.first()

            if existing_by_unique_id:
                return {
                    "is_duplicate": True,
                    "existing_document": existing_by_unique_id,
                    "match_reason": "same_unique_id",
                }

    return None

import os

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document


def cleanup_document_file(document_id: str, file_path: str | None, db: Session) -> None:
    """
    Clean up document file and database record on error.

    Args:
        document_id: ID of the document to clean up
        file_path: Path to the file to delete (if exists)
        db: Database session
    """
    # Clean up file
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[Cleanup] Deleted file: {file_path}")
        except Exception as e:
            print(f"[Cleanup] Error deleting file {file_path}: {e}")

    # Clean up database record
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            db.delete(doc)
            db.commit()
            print(f"[Cleanup] Deleted document record: {document_id}")
    except Exception as e:
        print(f"[Cleanup] Error deleting document record {document_id}: {e}")
        db.rollback()


def cleanup_orphaned_files(max_age_days: int = 7) -> int:
    """
    Clean up files for failed documents older than max_age_days.

    Args:
        max_age_days: Maximum age in days for failed documents

    Returns:
        Number of documents cleaned up
    """
    from datetime import datetime, timedelta

    from app.models.document import DocumentStatus

    db = SessionLocal()
    cleaned_count = 0

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # Find failed documents older than cutoff
        failed_docs = (
            db.query(Document)
            .filter(
                Document.status.in_(
                    [
                        DocumentStatus.UPLOAD_FAILED,
                        DocumentStatus.CLASSIFICATION_FAILED,
                        DocumentStatus.INDEXING_FAILED,
                        DocumentStatus.EXTRACTION_FAILED,
                    ]
                ),
                Document.uploaded_at < cutoff_date,
            )
            .all()
        )

        for doc in failed_docs:
            # Delete file if exists
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                    print(f"[Cleanup] Removed file: {doc.file_path}")
                except Exception as e:
                    print(f"[Cleanup] Error removing file {doc.file_path}: {e}")

            # Delete database record
            db.delete(doc)
            cleaned_count += 1

        db.commit()
        print(f"[Cleanup] Removed {cleaned_count} failed documents older than {max_age_days} days")

    except Exception as e:
        print(f"[Cleanup] Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

    return cleaned_count

import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models.document import Document, DocumentStatus, ProcessingStatus


def migrate():
    """
    Migration script to:
    1. Add new columns to 'documents' table if they don't exist.
    2. Backfill 'status' from deprecated 'indexing_status' and 'analysis_status'.
    3. Backfill 'file_size' from filesystem.
    """
    print("Starting migration: add_unified_status_fields...")

    with engine.connect() as connection:
        # Check existing columns using Inspector
        inspector = inspect(engine)
        existing_columns = [col["name"] for col in inspector.get_columns("documents")]

        # 1. Add new columns
        print("Checking/Adding columns...")

        if "status" not in existing_columns:
            print("  Adding 'status' column...")
            connection.execute(text("ALTER TABLE documents ADD COLUMN status VARCHAR"))
            # We'll set default and NOT NULL constraints later after backfill if needed,
            # but for SQLite/simple logic we just add the column.
            # SQLite supports adding NOT NULL with DEFAULT, but we will backfill first.

        if "file_size" not in existing_columns:
            print("  Adding 'file_size' column...")
            connection.execute(text("ALTER TABLE documents ADD COLUMN file_size INTEGER"))

        if "error_message" not in existing_columns:
            print("  Adding 'error_message' column...")
            connection.execute(text("ALTER TABLE documents ADD COLUMN error_message TEXT"))

        if "processing_metadata" not in existing_columns:
            print("  Adding 'processing_metadata' column...")
            connection.execute(text("ALTER TABLE documents ADD COLUMN processing_metadata TEXT"))

        if "current_step" not in existing_columns:
            print("  Adding 'current_step' column...")
            connection.execute(text("ALTER TABLE documents ADD COLUMN current_step VARCHAR"))

        connection.commit()

    # 2. Backfill data
    print("Backfilling data...")
    session = Session(bind=engine)
    try:
        documents = session.query(Document).all()
        updated_count = 0

        for doc in documents:
            # Backfill status
            if not doc.status or doc.status == DocumentStatus.PENDING:
                if doc.analysis_status == ProcessingStatus.PROCESSED:
                    if doc.document_type == "earnings_announcement":
                        doc.status = DocumentStatus.PROCESSING_COMPLETE
                    else:
                        doc.status = DocumentStatus.CLASSIFIED
                elif (
                    doc.analysis_status == ProcessingStatus.ERROR
                    or doc.indexing_status == ProcessingStatus.ERROR
                ):
                    doc.status = DocumentStatus.EXTRACTION_FAILED
                elif doc.indexing_status == ProcessingStatus.INDEXED:
                    if doc.document_type == "earnings_announcement":
                        # If indexed but analysis not processed, likely failed or stuck or just indexed
                        doc.status = DocumentStatus.INDEXED
                    else:
                        doc.status = DocumentStatus.CLASSIFIED
                elif doc.indexing_status == ProcessingStatus.INDEXING:
                    doc.status = DocumentStatus.INDEXING
                elif doc.indexing_status == ProcessingStatus.CLASSIFIED:
                    doc.status = DocumentStatus.CLASSIFIED
                elif doc.indexing_status == ProcessingStatus.CLASSIFYING:
                    doc.status = DocumentStatus.CLASSIFYING
                elif doc.indexing_status == ProcessingStatus.UPLOADING:
                    doc.status = DocumentStatus.UPLOADING
                else:
                    doc.status = DocumentStatus.PENDING  # Default fallback

            # Backfill file_size
            if doc.file_size is None and doc.file_path and os.path.exists(doc.file_path):
                try:
                    doc.file_size = os.path.getsize(doc.file_path)
                except OSError:
                    print(f"  Warning: Could not get size for file {doc.file_path}")

            updated_count += 1

        session.commit()
        print(f"Backfilled {updated_count} documents.")

    except Exception as e:
        session.rollback()
        print(f"Error during backfill: {e}")
        raise
    finally:
        session.close()

    print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()

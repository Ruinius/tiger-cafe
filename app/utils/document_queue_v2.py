import queue
import threading
import traceback

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentType

# Import financial statement processors
# We import them inside methods or here if no circular dep
# functionality is in routers/services, we might need to move them or import carefully
# For now, we will perform dynamic imports in the process loop to avoid circular deps with routers if any.


class DocumentQueue:
    def __init__(self):
        self._queue = queue.Queue()
        self._current_document_id: str | None = None
        self._current_status: str = "Idle"
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._process_loop, daemon=True, name="DocumentQueueWorker"
        )
        self._worker_thread.start()
        print("DocumentQueue v2 initialized and worker started.")

    def add_document(self, document_id: str):
        """Add a document to the processing queue."""
        print(f"Enqueuing document {document_id}")
        self._queue.put(document_id)

    def get_status(self) -> dict:
        """Get current queue status."""
        with self._lock:
            return {
                "queue_length": self._queue.qsize(),
                "current_document_id": self._current_document_id,
                "current_status": self._current_status,
                "is_active": self._worker_thread.is_alive(),
            }

    def shutdown(self):
        """Stop the worker thread gracefully."""
        self._stop_event.set()
        # queue.get() blocks, so we might put a sentinel or wait
        # We'll rely on daemon thread for now or put None
        self._queue.put(None)
        print("DocumentQueue shutdown requested.")

    def _process_loop(self):
        """Main processing loop."""
        while not self._stop_event.is_set():
            try:
                document_id = self._queue.get()
                if document_id is None:  # Sentinel
                    break

                with self._lock:
                    self._current_document_id = document_id
                    self._current_status = "Starting processing..."

                self._process_document_end_to_end(document_id)

                with self._lock:
                    self._current_document_id = None
                    self._current_status = "Idle"

                self._queue.task_done()
            except Exception as e:
                print(f"Critical error in DocumentQueue loop: {e}")
                traceback.print_exc()
                with self._lock:
                    self._current_document_id = None
                    self._current_status = "Error"

    def _process_document_end_to_end(self, document_id: str):
        """
        Orchestrate the strict sequential processing of a single document.
        Does not return until document reaches a terminal state.
        """
        db = SessionLocal()
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                print(f"Document {document_id} not found in queue processing.")
                return

            print(f"Processing document {document_id}, type: {document.document_type}")

            # 1. Classification & Indexing (if not done)
            if (
                document.status == DocumentStatus.PENDING
                or document.status == DocumentStatus.UPLOADING
            ):
                self._update_status(db, document, DocumentStatus.CLASSIFYING)

                # We reuse the existing process_document logic which does classification + indexing + summary
                # But we want to call it synchronously.
                # process_document is synchronous.
                # It handles: Pre-processing (Classify -> Index)
                try:
                    from app.services.document_processing import (
                        DocumentProcessingMode,
                        process_document,
                    )

                    # We run in FULL mode to get classification + summary + indexing (if earnings)
                    # NOTE: process_document updates `indexing_status` (legacy). We need to verify what it sets.
                    # We might need to manually update our unified `status` after it returns.

                    process_document(
                        db_session=db, mode=DocumentProcessingMode.FULL, document_id=document_id
                    )

                    # Refresh to check result
                    db.refresh(document)

                    if document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT:
                        self._update_status(db, document, DocumentStatus.INDEXED)
                    else:
                        # Non-earnings documents are done after classification/indexing
                        self._update_status(db, document, DocumentStatus.CLASSIFIED)
                        return  # Terminal state

                except Exception as e:
                    print(f"Error in classification/indexing step: {e}")
                    traceback.print_exc()
                    self._update_status(db, document, DocumentStatus.CLASSIFICATION_FAILED, str(e))
                    return

            # 2. Financial Extraction (Earnings Announcements Only)
            if (
                document.status == DocumentStatus.INDEXED
                or document.status == DocumentStatus.INDEXING
            ):  # In case previous step left it there
                # Double check type
                print(
                    f"[Queue] Document status is {document.status}, checking if should process financials..."
                )
                if document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT:
                    print("[Queue] Document is EARNINGS_ANNOUNCEMENT, calling _process_financials")
                    self._process_financials(document_id, db)
                else:
                    print(
                        f"[Queue] Document type is {document.document_type}, skipping financial extraction"
                    )
                    self._update_status(db, document, DocumentStatus.CLASSIFIED)

        except Exception as e:
            print(f"Unhandled error processing document {document_id}: {e}")
            traceback.print_exc()
            try:
                # Re-fetch as session might be messed up
                if db:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if document:
                        self._update_status(db, document, DocumentStatus.EXTRACTION_FAILED, str(e))
            except Exception:
                pass
        finally:
            db.close()

    def _process_financials(self, document_id: str, db: Session):
        """Sequential financial statement extraction."""

        print(f"[Queue] _process_financials called for document {document_id}")

        # A. Balance Sheet
        print("[Queue] Starting balance sheet extraction...")
        self._update_status_by_id(db, document_id, DocumentStatus.EXTRACTING_BALANCE_SHEET)
        from app.routers.balance_sheet import process_balance_sheet_async

        process_balance_sheet_async(document_id, db)
        print("[Queue] Balance sheet extraction completed")

        # B. Income Statement (Includes Additional Items & Non-Operating Classification)
        print("[Queue] Starting income statement extraction...")
        self._update_status_by_id(db, document_id, DocumentStatus.EXTRACTING_INCOME_STATEMENT)
        from app.routers.income_statement import process_income_statement_async

        process_income_statement_async(document_id, db)
        print("[Queue] Income statement extraction completed")

        # E. Finish
        print("[Queue] All extractions complete, marking as PROCESSING_COMPLETE")
        self._update_status_by_id(db, document_id, DocumentStatus.PROCESSING_COMPLETE)

    def _update_status(
        self, db: Session, document: Document, status: DocumentStatus, error_msg: str = None
    ):
        """Update document status helper."""
        document.status = status
        if error_msg:
            document.error_message = error_msg

        # Update current step description for UI
        step_map = {
            DocumentStatus.CLASSIFYING: "1/7: Classifying & Indexing",
            DocumentStatus.INDEXED: "2/7: Ready for Extraction",
            DocumentStatus.EXTRACTING_BALANCE_SHEET: "3/7: Extracting Balance Sheet",
            DocumentStatus.EXTRACTING_INCOME_STATEMENT: "4/7: Extracting Income Statement",
            DocumentStatus.EXTRACTING_ADDITIONAL_ITEMS: "5/7: Extracting Additional Items",
            DocumentStatus.CLASSIFYING_NON_OPERATING: "6/7: Classifying Non-Operating Items",
            DocumentStatus.PROCESSING_COMPLETE: "7/7: Processing Complete",
            DocumentStatus.EXTRACTION_FAILED: "Error Detected",
            DocumentStatus.CLASSIFIED: "Processing Complete",
        }
        document.current_step = step_map.get(status, status.value)

        db.commit()
        # db.refresh(document) # Not strictly fetching unless needed

    def _update_status_by_id(
        self, db: Session, document_id: str, status: DocumentStatus, error_msg: str = None
    ):
        """Update status by ID (refetches document to be safe)."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            self._update_status(db, doc, status, error_msg)

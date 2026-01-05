"""
Global document processing queue to ensure documents are processed sequentially
and prevent overwhelming the Gemini API.

This queue handles:
1. Classification (LLM call to classify document type, company, time period)
2. Indexing (embedding generation)
3. Financial statement processing (if eligible)
"""

import queue
import threading
from dataclasses import dataclass

from app.database import SessionLocal
from app.models.document import Document, DocumentType, ProcessingStatus
from app.routers.balance_sheet import process_balance_sheet_async
from app.routers.income_statement import process_income_statement_async
from app.services.document_processing import DocumentProcessingMode, process_document

# Task priorities: lower number = higher priority
PRIORITY_CLASSIFICATION_INDEXING = 0  # Highest priority
PRIORITY_FINANCIAL_STATEMENTS = 1  # Lower priority


@dataclass
class ProcessingTask:
    """Task to be processed in the queue"""

    priority: int
    document_id: str
    task_type: str  # 'classification_indexing' or 'financial_statements'

    def __lt__(self, other):
        """For PriorityQueue ordering (lower priority number = higher priority)"""
        return self.priority < other.priority


# Global processing queue (priority queue)
_processing_queue = queue.PriorityQueue()
_processing_thread: threading.Thread | None = None
_queue_lock = threading.Lock()
_shutdown_event = threading.Event()


def _process_document_with_service(document_id: str, mode: DocumentProcessingMode, db_session):
    try:
        process_document(db_session=db_session, document_id=document_id, mode=mode)
    except Exception as exc:
        print(f"Error processing document {document_id} in mode {mode.value}: {exc}")
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if document:
            document.indexing_status = ProcessingStatus.ERROR
            db_session.commit()


def _process_financial_statements(document_id: str, db_session: SessionLocal):
    """
    Process financial statements for an indexed document.
    Balance sheet is processed first, then income statement (which uses balance sheet location and
    triggers additional items + non-operating classification).
    """
    document = db_session.query(Document).filter(Document.id == document_id).first()
    if not document:
        print(f"Document {document_id} not found for financial statement processing")
        return

    eligible_types = [
        DocumentType.EARNINGS_ANNOUNCEMENT,
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]

    if document.document_type in eligible_types:
        # Process balance sheet first (blocking call - completes before income statement starts)
        print(f"Starting balance sheet processing for document {document_id}")
        process_balance_sheet_async(document_id, db_session)

        # Refresh document to get updated balance sheet status
        db_session.refresh(document)

        # Process income statement (uses balance sheet location for finding income statement)
        # No sleep needed - balance sheet processing is synchronous and completes before this
        print(f"Starting income statement processing for document {document_id}")
        db_is = SessionLocal()
        try:
            process_income_statement_async(document_id, db_is)
        finally:
            db_is.close()

        print(f"Completed financial statement processing for document {document_id}")


def _process_document_worker():
    """Worker thread that processes documents from the priority queue"""
    while not _shutdown_event.is_set():
        try:
            # Get next task from priority queue (blocks until available or timeout)
            # PriorityQueue returns items in priority order (lowest priority number first)
            try:
                task: ProcessingTask = _processing_queue.get(timeout=1)
            except queue.Empty:
                # Timeout - check for shutdown and continue
                continue

            if task is None:  # Shutdown signal
                break

            print(
                f"Processing {task.task_type} for document {task.document_id} (queue size: {_processing_queue.qsize()})"
            )

            # Create database session for this document
            db_session = SessionLocal()
            try:
                # Get document
                document = (
                    db_session.query(Document).filter(Document.id == task.document_id).first()
                )
                if not document:
                    print(f"Document {task.document_id} not found, skipping")
                    continue

                if task.task_type == "classification_indexing":
                    # Handle classification and indexing
                    if (
                        document.indexing_status == ProcessingStatus.UPLOADING
                        or document.indexing_status == ProcessingStatus.CLASSIFYING
                    ):
                        # Document needs classification and indexing
                        _process_document_with_service(
                            task.document_id, DocumentProcessingMode.FULL, db_session
                        )

                        # Refresh document to get updated status
                        db_session.refresh(document)

                        # If document is now indexed and eligible, queue financial statement processing
                        if document.indexing_status == ProcessingStatus.INDEXED:
                            eligible_types = [
                                DocumentType.EARNINGS_ANNOUNCEMENT,
                                DocumentType.QUARTERLY_FILING,
                                DocumentType.ANNUAL_FILING,
                            ]

                            if document.document_type in eligible_types:
                                # Queue financial statement processing with lower priority
                                queue_financial_statements_processing(task.document_id)
                    elif document.indexing_status == ProcessingStatus.INDEXING:
                        # Document is already classified, just needs indexing
                        # This can happen when replace_and_index is called
                        _process_document_with_service(
                            task.document_id, DocumentProcessingMode.INDEX_ONLY, db_session
                        )

                        # Refresh document to get updated status
                        db_session.refresh(document)

                        # Only auto-trigger financial statement processing if:
                        # 1. Document is eligible for financial statements
                        # 2. Financial statements haven't been processed yet (not a re-index)
                        # We check analysis_status to distinguish between initial indexing and re-indexing
                        eligible_types = [
                            DocumentType.EARNINGS_ANNOUNCEMENT,
                            DocumentType.QUARTERLY_FILING,
                            DocumentType.ANNUAL_FILING,
                        ]

                        if (
                            document.document_type in eligible_types
                            and document.analysis_status != ProcessingStatus.PROCESSED
                        ):
                            # Only queue if financial statements haven't been processed yet
                            # This prevents re-triggering financial statement extraction during re-indexing
                            queue_financial_statements_processing(task.document_id)

                elif task.task_type == "financial_statements":
                    # Handle financial statement processing
                    if document.indexing_status == ProcessingStatus.INDEXED:
                        _process_financial_statements(task.document_id, db_session)
                    else:
                        print(
                            f"Document {task.document_id} is not indexed yet, skipping financial statement processing"
                        )

            except Exception as e:
                print(
                    f"Error processing {task.task_type} for document {task.document_id}: {str(e)}"
                )
                import traceback

                traceback.print_exc()
            finally:
                db_session.close()
                # Mark task as done
                _processing_queue.task_done()

        except Exception as e:
            print(f"Error in document processing worker: {str(e)}")
            import traceback

            traceback.print_exc()
            # Wait before retrying, but respect shutdown event
            # wait() returns True if event is set (shutdown), False if timeout
            if _shutdown_event.wait(timeout=5):
                # Shutdown requested during wait
                break
            # Otherwise continue (loop will check shutdown condition again)

    print("Document processing worker thread stopped")


def _ensure_worker_thread():
    """Ensure the worker thread is running"""
    global _processing_thread
    with _queue_lock:
        if _processing_thread is None or not _processing_thread.is_alive():
            # Reset shutdown event if thread was stopped
            _shutdown_event.clear()
            _processing_thread = threading.Thread(target=_process_document_worker, daemon=True)
            _processing_thread.start()
            print("Started document processing worker thread")


def stop_processing_worker():
    """
    Gracefully shut down the document processing worker thread.
    This will stop processing new tasks but will complete the current task.
    Useful for testing or application shutdown.
    """
    global _processing_thread
    with _queue_lock:
        if _processing_thread is not None and _processing_thread.is_alive():
            print("Stopping document processing worker thread...")
            _shutdown_event.set()
            # Wait for thread to finish (with timeout)
            _processing_thread.join(timeout=10)
            if _processing_thread.is_alive():
                print("Warning: Worker thread did not stop within timeout")
            else:
                print("Document processing worker thread stopped")
            _processing_thread = None


def queue_document_for_processing(document_id: str):
    """
    Add a document to the processing queue for classification and indexing.
    This is high priority and will be processed before financial statement extraction.

    Args:
        document_id: ID of the document to process
    """
    _ensure_worker_thread()
    task = ProcessingTask(
        priority=PRIORITY_CLASSIFICATION_INDEXING,
        document_id=document_id,
        task_type="classification_indexing",
    )
    _processing_queue.put(task)
    print(
        f"Queued document {document_id} for classification/indexing (queue size: {_processing_queue.qsize()})"
    )


def queue_financial_statements_processing(document_id: str):
    """
    Add a document to the processing queue for financial statement extraction.
    This is lower priority and will be processed after classification/indexing tasks.

    Args:
        document_id: ID of the document to process
    """
    _ensure_worker_thread()
    task = ProcessingTask(
        priority=PRIORITY_FINANCIAL_STATEMENTS,
        document_id=document_id,
        task_type="financial_statements",
    )
    _processing_queue.put(task)
    print(
        f"Queued document {document_id} for financial statement processing (queue size: {_processing_queue.qsize()})"
    )

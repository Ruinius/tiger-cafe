"""
Global document processing queue to ensure documents are processed sequentially
and prevent overwhelming the Gemini API.

This queue handles:
1. Classification (LLM call to classify document type, company, time period)
2. Indexing (embedding generation)
3. Financial statement processing (if eligible)
"""

import threading
import queue
import time
from typing import Optional, Tuple
from dataclasses import dataclass
from app.database import SessionLocal
from app.models.document import Document, DocumentType, ProcessingStatus
from app.routers.balance_sheet import process_balance_sheet_async
from app.routers.income_statement import process_income_statement_async
from agents.document_classifier import classify_document
from agents.document_summarizer import generate_document_summary
from app.utils.document_indexer import index_document_chunks
from app.utils.duplicate_detector import check_duplicate_document
from app.utils.document_hash import generate_document_hash
from app.utils.pdf_extractor import extract_text_from_pdf
from app.models.company import Company
from datetime import datetime
import os
import uuid

# Task priorities: lower number = higher priority
PRIORITY_CLASSIFICATION_INDEXING = 0  # Highest priority
PRIORITY_FINANCIAL_STATEMENTS = 1     # Lower priority

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
_processing_thread: Optional[threading.Thread] = None
_queue_lock = threading.Lock()


def _classify_and_index_document(document_id: str, db_session: SessionLocal):
    """
    Classify and index a document.
    This includes: classification, duplicate check, summary generation, and embedding.
    """
    document = db_session.query(Document).filter(Document.id == document_id).first()
    if not document:
        print(f"Document {document_id} not found")
        return
    
    # Step 1: Extract text and classify
    document.indexing_status = ProcessingStatus.CLASSIFYING
    db_session.commit()
    
    if not document.file_path or not os.path.exists(document.file_path):
        print(f"File not found for document {document_id}")
        document.indexing_status = ProcessingStatus.ERROR
        db_session.commit()
        return
    
    # Extract text from first few pages for classification
    extracted_text, total_pages, character_count = extract_text_from_pdf(document.file_path, max_pages=5)
    
    # Generate hash from first 5000 characters
    hash_text = extracted_text[:5000] if len(extracted_text) > 5000 else extracted_text
    document_hash = generate_document_hash(hash_text)
    
    # Classify document
    classification_data = classify_document(extracted_text)
    company_name = classification_data.get("company_name")
    
    if not company_name:
        document.indexing_status = ProcessingStatus.ERROR
        db_session.commit()
        return
    
    # Get or create company
    company = db_session.query(Company).filter(
        Company.name.ilike(company_name)
    ).first()
    
    if not company:
        company = Company(
            id=str(uuid.uuid4()),
            name=company_name,
            ticker=classification_data.get("ticker")
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
    
    # Update document with company and classification
    document.company_id = company.id
    document.document_type = classification_data.get("document_type")
    document.time_period = classification_data.get("time_period")
    document.unique_id = document_hash
    document.page_count = total_pages
    document.character_count = character_count
    
    # Check for duplicates
    document_type = classification_data.get("document_type")
    time_period = classification_data.get("time_period")
    duplicate_check = None
    
    if document_type:
        duplicate_check = check_duplicate_document(
            db=db_session,
            company_id=company.id,
            document_type=document_type,
            time_period=time_period,
            filename=document.filename,
            unique_id=document_hash,
            exclude_document_id=document_id
        )
    
    # If duplicate detected, stop and wait for user action
    if duplicate_check and duplicate_check.get("is_duplicate"):
        existing_doc = duplicate_check["existing_document"]
        document.duplicate_detected = True
        document.existing_document_id = existing_doc.id
        document.indexing_status = ProcessingStatus.CLASSIFYING  # Stay in classifying until user confirms
        db_session.commit()
        return  # Stop here, wait for user to click "Replace & Index"
    
    # Step 2: No duplicate, proceed with indexing
    document.indexing_status = ProcessingStatus.INDEXING
    db_session.commit()
    
    # Generate summary
    try:
        summary = generate_document_summary(extracted_text)
        if summary:
            document.summary = summary
            db_session.commit()
    except Exception as e:
        print(f"Warning: Failed to generate summary: {str(e)}")
    
    # Index document using chunk-based approach (5-page chunks)
    # This replaces the old document-level embedding
    chunk_metadata = index_document_chunks(document.file_path, document_id, chunk_size=5)
    
    # Update character count (approximate, based on extracted text)
    full_extracted_text, total_pages, character_count = extract_text_from_pdf(document.file_path, max_pages=None)
    
    # Update final status
    document.indexing_status = ProcessingStatus.INDEXED
    document.indexed_at = datetime.utcnow()
    document.page_count = total_pages
    document.character_count = character_count
    db_session.commit()
    
    print(f"Completed classification and indexing for document {document_id}")


def _process_financial_statements(document_id: str, db_session: SessionLocal):
    """
    Process financial statements for an indexed document.
    """
    document = db_session.query(Document).filter(Document.id == document_id).first()
    if not document:
        print(f"Document {document_id} not found for financial statement processing")
        return
    
    eligible_types = [
        DocumentType.EARNINGS_ANNOUNCEMENT,
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING
    ]
    
    if document.document_type in eligible_types:
        # Process balance sheet first
        print(f"Starting balance sheet processing for document {document_id}")
        process_balance_sheet_async(document_id, db_session)
        
        # Small delay between balance sheet and income statement
        time.sleep(2)
        
        # Process income statement
        print(f"Starting income statement processing for document {document_id}")
        db_is = SessionLocal()
        try:
            process_income_statement_async(document_id, db_is)
        finally:
            db_is.close()
        
        print(f"Completed financial statement processing for document {document_id}")


def _process_document_worker():
    """Worker thread that processes documents from the priority queue"""
    while True:
        try:
            # Get next task from priority queue (blocks until available)
            # PriorityQueue returns items in priority order (lowest priority number first)
            task: ProcessingTask = _processing_queue.get(timeout=1)
            
            if task is None:  # Shutdown signal
                break
            
            print(f"Processing {task.task_type} for document {task.document_id} (queue size: {_processing_queue.qsize()})")
            
            # Create database session for this document
            db_session = SessionLocal()
            try:
                # Get document
                document = db_session.query(Document).filter(Document.id == task.document_id).first()
                if not document:
                    print(f"Document {task.document_id} not found, skipping")
                    continue
                
                if task.task_type == 'classification_indexing':
                    # Handle classification and indexing
                    if document.indexing_status == ProcessingStatus.UPLOADING or document.indexing_status == ProcessingStatus.CLASSIFYING:
                        # Document needs classification and indexing
                        _classify_and_index_document(task.document_id, db_session)
                        
                        # Refresh document to get updated status
                        db_session.refresh(document)
                        
                        # If document is now indexed and eligible, queue financial statement processing
                        if document.indexing_status == ProcessingStatus.INDEXED:
                            eligible_types = [
                                DocumentType.EARNINGS_ANNOUNCEMENT,
                                DocumentType.QUARTERLY_FILING,
                                DocumentType.ANNUAL_FILING
                            ]
                            
                            if document.document_type in eligible_types:
                                # Queue financial statement processing with lower priority
                                queue_financial_statements_processing(task.document_id)
                    elif document.indexing_status == ProcessingStatus.INDEXING:
                        # Document is already classified, just needs indexing
                        # This can happen when replace_and_index is called
                        if not document.file_path or not os.path.exists(document.file_path):
                            print(f"File not found for document {task.document_id}")
                            document.indexing_status = ProcessingStatus.ERROR
                            db_session.commit()
                            continue
                        
                        # Index document using chunk-based approach
                        chunk_metadata = index_document_chunks(document.file_path, task.document_id, chunk_size=5)
                        
                        # Update character count (approximate, based on extracted text)
                        full_extracted_text, total_pages, character_count = extract_text_from_pdf(document.file_path, max_pages=None)
                        
                        # Update final status
                        document.indexing_status = ProcessingStatus.INDEXED
                        document.indexed_at = datetime.utcnow()
                        document.page_count = total_pages
                        document.character_count = character_count
                        db_session.commit()
                        
                        print(f"Completed indexing for document {task.document_id}")
                        
                        # Refresh document to get updated status
                        db_session.refresh(document)
                        
                        # If document is eligible, queue financial statement processing
                        eligible_types = [
                            DocumentType.EARNINGS_ANNOUNCEMENT,
                            DocumentType.QUARTERLY_FILING,
                            DocumentType.ANNUAL_FILING
                        ]
                        
                        if document.document_type in eligible_types:
                            queue_financial_statements_processing(task.document_id)
                
                elif task.task_type == 'financial_statements':
                    # Handle financial statement processing
                    if document.indexing_status == ProcessingStatus.INDEXED:
                        _process_financial_statements(task.document_id, db_session)
                    else:
                        print(f"Document {task.document_id} is not indexed yet, skipping financial statement processing")
                
            except Exception as e:
                print(f"Error processing {task.task_type} for document {task.document_id}: {str(e)}")
                import traceback
                traceback.print_exc()
            finally:
                db_session.close()
                # Mark task as done
                _processing_queue.task_done()
                
        except queue.Empty:
            # Timeout - continue loop to check for shutdown
            continue
        except Exception as e:
            print(f"Error in document processing worker: {str(e)}")
            import traceback
            traceback.print_exc()
            time.sleep(5)  # Wait before retrying


def _ensure_worker_thread():
    """Ensure the worker thread is running"""
    global _processing_thread
    with _queue_lock:
        if _processing_thread is None or not _processing_thread.is_alive():
            _processing_thread = threading.Thread(target=_process_document_worker, daemon=True)
            _processing_thread.start()
            print("Started document processing worker thread")


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
        task_type='classification_indexing'
    )
    _processing_queue.put(task)
    print(f"Queued document {document_id} for classification/indexing (queue size: {_processing_queue.qsize()})")


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
        task_type='financial_statements'
    )
    _processing_queue.put(task)
    print(f"Queued document {document_id} for financial statement processing (queue size: {_processing_queue.qsize()})")


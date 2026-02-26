"""
Document routes
"""

import json
import os
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.app_agents.document_classifier import classify_document
from app.database import get_db
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_status import DocumentStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.document import Document as DocumentSchema
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentUploadResponse,
)
from app.schemas.file_metadata import DuplicateCheckResult, ExistingDocumentInfo, FileMetadata
from app.utils.document_hash import generate_document_hash
from app.utils.document_indexer import (
    delete_chunk_embeddings,
    get_chunk_metadata,
    load_full_document_text,
)
from app.utils.pdf_extractor import extract_text_from_pdf
from config.config import DEBUG, UPLOAD_DIR

router = APIRouter()


def add_uploader_name_to_document(db: Session, document: Document) -> dict:
    """
    Convert document to dict and add uploader_name.
    """
    doc_dict = {
        "id": document.id,
        "user_id": document.user_id,
        "company_id": document.company_id,
        "filename": document.filename,
        "file_path": document.file_path,
        "document_type": document.document_type,
        "time_period": document.time_period,
        "period_end_date": document.period_end_date,
        "document_date": document.document_date,
        "summary": document.summary,
        "unique_id": document.unique_id,
        "indexing_status": document.indexing_status,
        "analysis_status": document.analysis_status,
        "status": document.status,
        "page_count": document.page_count,
        "character_count": document.character_count,
        "uploaded_at": document.uploaded_at,
        "indexed_at": document.indexed_at,
        "processed_at": document.processed_at,
        "duplicate_detected": document.duplicate_detected,
        "existing_document_id": document.existing_document_id,
        "uploader_name": None,
        "balance_sheet_status": None,
        "income_statement_status": None,
        "gaap_reconciliation_status": None,
        "organic_growth_status": None,
        "shares_outstanding_status": None,
    }
    # Get uploader name
    if document.user_id:
        user = db.query(User).filter(User.id == document.user_id).first()
        if user:
            name = f"{user.first_name} {user.last_name}".strip()
            doc_dict["uploader_name"] = name or user.email

    # Harmonized status values:
    # - "success": Data exists and is valid (green badge)
    # - "warning": Data exists but has validation issues (yellow badge)
    # - "error": Data not found / 404 (red badge)
    # - None: Not yet extracted (no badge shown)

    # Balance Sheet Status
    if document.balance_sheet:
        doc_dict["balance_sheet_status"] = (
            "success" if document.balance_sheet.is_valid else "warning"
        )
    elif document.status == DocumentStatus.PROCESSING_COMPLETE:
        doc_dict["balance_sheet_status"] = "error"  # Processed but not found

    # Income Statement Status
    if document.income_statement:
        doc_dict["income_statement_status"] = (
            "success" if document.income_statement.is_valid else "warning"
        )
    elif document.status == DocumentStatus.PROCESSING_COMPLETE:
        doc_dict["income_statement_status"] = "error"  # Processed but not found

    # Organic Growth Status
    from app.models.organic_growth import OrganicGrowth

    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document.id).first()
    )
    if organic_growth:
        # Check if it has meaningful data
        has_data = (
            organic_growth.prior_period_revenue is not None
            or organic_growth.current_period_revenue is not None
        )
        doc_dict["organic_growth_status"] = "success" if has_data else "warning"
    elif document.status == DocumentStatus.PROCESSING_COMPLETE:
        doc_dict["organic_growth_status"] = "error"  # Processed but not found

    # Shares Outstanding Status
    from app.models.shares_outstanding import SharesOutstanding

    shares = (
        db.query(SharesOutstanding).filter(SharesOutstanding.document_id == document.id).first()
    )
    if shares:
        # Check if at least one value exists
        has_data = (
            shares.basic_shares_outstanding is not None
            or shares.diluted_shares_outstanding is not None
        )
        doc_dict["shares_outstanding_status"] = "success" if has_data else "warning"
    elif document.status == DocumentStatus.PROCESSING_COMPLETE:
        doc_dict["shares_outstanding_status"] = "error"  # Processed but not found

    return doc_dict


# New batch upload endpoint for multi-file upload
@router.post("/check-duplicates-batch", response_model=list[DuplicateCheckResult])
async def check_duplicates_batch(
    files: list[FileMetadata],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check for potential duplicates before upload.
    Returns list of potential matches for user confirmation.
    """
    results = []
    for file_meta in files:
        # Check by filename + size first (fast)
        # Note: We rely on file_size being populated in Phase 1
        potential_dupe = (
            db.query(Document)
            .filter(Document.filename == file_meta.filename, Document.file_size == file_meta.size)
            .first()
        )

        existing_info = None
        if potential_dupe:
            uploader = db.query(User).filter(User.id == potential_dupe.user_id).first()
            uploader_name = (
                f"{uploader.first_name} {uploader.last_name}".strip() if uploader else "Unknown"
            )

            existing_info = ExistingDocumentInfo(
                id=potential_dupe.id,
                uploaded_by=uploader_name,
                uploaded_at=potential_dupe.uploaded_at,
                filename=potential_dupe.filename,
            )

        results.append(
            DuplicateCheckResult(
                filename=file_meta.filename,
                is_potential_duplicate=potential_dupe is not None,
                existing_document=existing_info,
            )
        )

    return results


# New batch upload endpoint for multi-file upload
@router.post("/upload-batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload multiple documents (up to 10) and process them asynchronously via the queue.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")

    results = []

    # Process files sequentially using the internal logic
    # Note: upload_document_internal saves file and enqueues it, so it's fast.
    for file in files:
        if not file.filename.endswith(".pdf"):
            continue  # Skip non-pdfs or handle error

        # We need to reset the file pointer if it was read previously,
        # but here we receive fresh SpooledTemporaryFile objects.
        # upload_document_internal reads from file.file

        try:
            result = await upload_document_internal(file, db, current_user)
            results.append(result.document_id)
        except HTTPException:
            # If one fails, we log/skip? Or fail batch?
            # For simplicity, we skip error handling per-file here or handle basic
            pass
        except Exception as e:
            print(f"Batch upload error for {file.filename}: {e}")

    if not results:
        raise HTTPException(status_code=400, detail="No valid PDF files processed or all failed")

    return {"document_ids": results, "message": f"Queued {len(results)} documents"}


if DEBUG:

    @router.post("/upload-batch-test")
    async def upload_batch_test(
        files: list[UploadFile] = File(...),
        db: Session = Depends(get_db),
    ):
        """
        TEST ENDPOINT: Upload multiple documents without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(id="test-user-id", email="test@example.com", name="Test User")
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")

        results = []
        for file in files:
            if not file.filename.endswith(".pdf"):
                continue

            try:
                result = await upload_document_internal(file, db, test_user)
                results.append(result.document_id)
            except Exception as e:
                print(f"Test batch upload error for {file.filename}: {e}")

        if not results:
            raise HTTPException(
                status_code=400, detail="No valid PDF files processed or all failed"
            )

        return {"document_ids": results, "message": f"Queued {len(results)} documents"}


@router.get("/upload-progress", response_model=list[DocumentSchema])
async def get_upload_progress(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get list of documents currently being processed (uploading, classifying, or indexing).
    Used to show upload progress in the UI.
    """
    active_statuses = [
        ProcessingStatus.UPLOADING,
        ProcessingStatus.CLASSIFYING,
        ProcessingStatus.INDEXING,
        ProcessingStatus.PENDING,
    ]
    # Query all documents with active statuses, ordered by most recent first
    documents = (
        db.query(Document)
        .filter(Document.indexing_status.in_(active_statuses))
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [add_uploader_name_to_document(db, doc) for doc in documents]


@router.get("/processing-queue-status")
async def get_queue_status():
    """Get the current status of the document processing queue."""
    from app.services.queue_service import queue_service

    return queue_service.get_status()


if DEBUG:

    @router.get("/upload-progress-test", response_model=list[DocumentSchema])
    async def get_upload_progress_test(db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Get upload progress without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        active_statuses = [
            ProcessingStatus.UPLOADING,
            ProcessingStatus.CLASSIFYING,
            ProcessingStatus.INDEXING,
            ProcessingStatus.PENDING,
        ]
        documents = (
            db.query(Document)
            .filter(Document.indexing_status.in_(active_statuses))
            .order_by(Document.uploaded_at.desc())
            .all()
        )
        return [add_uploader_name_to_document(db, doc) for doc in documents]


# Temporary test endpoint without authentication (for development/testing only)
if DEBUG:

    @router.post("/upload-test", response_model=DocumentUploadResponse)
    async def upload_document_test(file: UploadFile = File(...), db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Upload a PDF document without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        from app.models.user import User

        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(id="test-user-id", email="test@example.com", name="Test User")
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        # Initialize progress tracking for test uploads as well
        str(uuid.uuid4())  # Note: logic in internal func generates ID too
        # To avoid double generation or mismatched IDs, we rely on upload_document_internal
        # But we can't easily hook in there if we want test-specific behavior unless we pass a flag.
        # Actually, upload_document_internal now handles init/update, so we just call it.

        # Use the same logic as the authenticated endpoint
        return await upload_document_internal(file, db, test_user)


async def upload_document_internal(file: UploadFile, db: Session, current_user: User):
    """
    Internal upload function shared by authenticated and test endpoints.
    New Flow (Phase 4):
    1. Validate PDF.
    2. Save file to UPLOAD_DIR.
    3. Create Document record (Pending).
    4. Queue for processing.
    5. Return immediate response.
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Create upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Generate unique filename
    document_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{document_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    # Save uploaded file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

    # Create Document record
    # Use placeholder company if none exists (logic retained from old flow but simplified)
    # We really should have a proper "Unassigned" company or require selection.
    # For now, we grab the first one or create a placeholder to satisfy FK constraints.
    placeholder_company = db.query(Company).first()
    if not placeholder_company:
        placeholder_company = Company(id=str(uuid.uuid4()), name="Processing...", ticker=None)
        db.add(placeholder_company)
        db.commit()

    document = Document(
        id=document_id,
        user_id=current_user.id,
        company_id=placeholder_company.id,
        filename=file.filename,
        file_path=file_path,
        indexing_status=ProcessingStatus.PENDING,
        analysis_status=ProcessingStatus.PENDING,
        # Unified status
        status=DocumentStatus.PENDING,
        uploaded_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()

    # Enqueue for processing
    from app.services.queue_service import queue_service

    # Initialize progress tracking (shadowing status)
    from app.utils.financial_statement_progress import (
        FinancialStatementMilestone,
        MilestoneStatus,
        initialize_progress,
        update_milestone,
    )

    initialize_progress(document_id)
    update_milestone(
        document_id,
        FinancialStatementMilestone.UPLOAD,
        MilestoneStatus.COMPLETED,
        message="File uploaded successfully",
    )

    queue_service.add_document(document_id)

    # Return immediate response
    return DocumentUploadResponse(
        document_id=document_id,
        classification=None,  # Will be determined in background
        duplicate_info=None,  # Checked pre-upload (Phase 2)
        requires_confirmation=False,
        message="File uploaded and queued for processing.",
    )


if DEBUG:

    @router.get("/test", response_model=list[DocumentSchema])
    async def list_documents_test(
        company_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
    ):
        """
        TEST ENDPOINT: List documents without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        query = db.query(Document).options(
            joinedload(Document.balance_sheet),
            joinedload(Document.income_statement),
        )
        if company_id:
            query = query.filter(Document.company_id == company_id)
        documents = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()
        return [add_uploader_name_to_document(db, doc) for doc in documents]


@router.get("/", response_model=list[DocumentSchema])
async def list_documents(
    company_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents, optionally filtered by company. Shows all documents (shared dashboard)."""
    query = db.query(Document).options(
        joinedload(Document.balance_sheet),
        joinedload(Document.income_statement),
    )
    if company_id:
        query = query.filter(Document.company_id == company_id)
    documents = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()

    # Add uploader names to documents
    return [add_uploader_name_to_document(db, doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentSchema)
async def get_document(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get a specific document by ID (shared dashboard - all users can see all documents)"""
    document = (
        db.query(Document)
        .options(
            joinedload(Document.balance_sheet),
            joinedload(Document.income_statement),
        )
        .filter(Document.id == document_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return add_uploader_name_to_document(db, document)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Serve the PDF file for a document (shared dashboard - all users can access all documents)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Document file not found")

    return FileResponse(
        document.file_path, media_type="application/pdf", filename=document.filename
    )


if DEBUG:

    @router.get("/{document_id}/file-test")
    async def get_document_file_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Serve the PDF file for a document without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not os.path.exists(document.file_path):
            raise HTTPException(status_code=404, detail="Document file not found")

        return FileResponse(
            document.file_path, media_type="application/pdf", filename=document.filename
        )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF document, classify it, check for duplicates, and return classification results.
    User must confirm before document is indexed.
    """
    return await upload_document_internal(file, db, current_user)


if DEBUG:

    @router.post("/confirm-upload-test", response_model=DocumentSchema)
    async def confirm_upload_test(
        document_id: str,
        existing_document_id: str | None = None,
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: Session = Depends(get_db),
    ):
        """
        TEST ENDPOINT: Confirm document upload without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        This creates the document record and starts the indexing process.
        If existing_document_id is provided, replaces that document instead.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(id="test-user-id", email="test@example.com", name="Test User")
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        # Use the same logic as the authenticated endpoint
        return await confirm_upload_internal(
            document_id, db, test_user, background_tasks, existing_document_id
        )


async def confirm_upload_internal(
    document_id: str,
    db: Session,
    current_user: User,
    background_tasks: BackgroundTasks,
    existing_document_id: str | None = None,
):
    """
    Internal confirm upload function shared by authenticated and test endpoints.
    If existing_document_id is provided, updates that document instead of creating a new one.
    Returns quickly by doing heavy processing in background.
    """
    # Find the uploaded file
    file_path = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    # Get basic info from file (quick extraction for page count)
    try:
        _, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    # For now, we need to get company info. We'll use a quick classification on first few pages
    # or we can get it from the upload step. Let's do a quick classification on first 5 pages
    try:
        extracted_text_preview, _, _ = extract_text_from_pdf(file_path, max_pages=5)
        classification_data = classify_document(extracted_text_preview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error classifying document: {str(e)}")

    # Get company (required to create document)
    ticker = (
        classification_data.get("ticker").strip().upper()
        if classification_data.get("ticker")
        else None
    )
    company_name = classification_data.get("company_name")

    # 1. Try to find by ticker (the primary unique identifier)
    company = None
    if ticker:
        company = db.query(Company).filter(Company.ticker == ticker).first()

    # 2. Fallback to name if not found by ticker
    if not company and company_name:
        company = db.query(Company).filter(Company.name.ilike(company_name)).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Company not found (Ticker: {ticker or 'N/A'}, Name: {company_name or 'N/A'})",
        )

    # Sync Identity
    needs_commit = False
    if company_name and company.name != company_name:
        company.name = company_name
        needs_commit = True

    if ticker and not company.ticker:
        company.ticker = ticker
        needs_commit = True

    if needs_commit:
        db.commit()

    # Generate hash from first 5000 characters (avoids large document issues)
    hash_text = (
        extracted_text_preview[:5000]
        if len(extracted_text_preview) > 5000
        else extracted_text_preview
    )
    document_hash = generate_document_hash(hash_text)

    # Check if we're replacing an existing document
    if existing_document_id:
        # Update existing document
        document = db.query(Document).filter(Document.id == existing_document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Existing document not found")

        # Delete old file if it's different
        if document.file_path != file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                print(f"Warning: Failed to delete old file {document.file_path}: {str(e)}")

        # Update document with new data (basic info, will be refined in background)
        filename = os.path.basename(file_path)
        document.user_id = current_user.id
        document.company_id = company.id
        document.filename = filename
        document.file_path = file_path
        document.document_type = classification_data.get("document_type")
        document.time_period = classification_data.get("time_period")
        document.unique_id = document_hash  # Will be updated with full hash in background
        document.page_count = total_pages  # Will be updated with accurate count in background
        document.character_count = character_count  # Will be updated in background
        document.indexing_status = ProcessingStatus.INDEXING
        document.uploaded_at = datetime.utcnow()
        # Summary will be generated in background

        # Delete old chunk embeddings if they exist
        delete_chunk_embeddings(existing_document_id)
    else:
        # Create new document record (basic info, will be refined in background)
        filename = os.path.basename(file_path)
        document = Document(
            id=document_id,
            user_id=current_user.id,
            company_id=company.id,
            filename=filename,
            file_path=file_path,
            document_type=classification_data.get("document_type"),
            time_period=classification_data.get("time_period"),
            unique_id=document_hash,  # Will be updated with full hash in background
            page_count=total_pages,  # Will be updated with accurate count in background
            character_count=character_count,  # Will be updated in background
            indexing_status=ProcessingStatus.INDEXING,
            analysis_status=ProcessingStatus.PENDING,
            # Summary will be generated in background
        )
        db.add(document)

    db.commit()

    # Queue document for full processing and indexing (sequential processing)
    # This includes: full text extraction, re-classification, summary generation, and indexing
    from app.services.queue_service import queue_service

    document.status = DocumentStatus.UPLOADING
    db.commit()
    queue_service.add_document(document.id)

    db.refresh(document)
    return document


@router.post("/confirm-upload", response_model=DocumentSchema)
async def confirm_upload(
    document_id: str,
    existing_document_id: str | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm document upload and proceed with indexing.
    This creates the document record and starts the indexing process asynchronously.
    If existing_document_id is provided, replaces that document instead of creating a new one.
    """
    return await confirm_upload_internal(
        document_id, db, current_user, background_tasks, existing_document_id
    )


@router.post("/{document_id}/replace-and-index", response_model=DocumentSchema)
async def replace_and_index(
    document_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replace existing document and proceed with indexing.
    Called when user confirms "Replace & Index" for a duplicate document.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.duplicate_detected or not document.existing_document_id:
        raise HTTPException(status_code=400, detail="Document is not a duplicate")

    existing_document_id = document.existing_document_id

    # Get the existing document
    existing_doc = db.query(Document).filter(Document.id == existing_document_id).first()
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Existing document not found")

    # Delete old file and chunk embeddings
    if os.path.exists(existing_doc.file_path):
        try:
            os.remove(existing_doc.file_path)
        except Exception as e:
            print(f"Warning: Failed to delete old file: {str(e)}")
    delete_chunk_embeddings(existing_document_id)

    # Update existing document with new document's data
    existing_doc.user_id = document.user_id
    existing_doc.filename = document.filename
    existing_doc.file_path = document.file_path
    existing_doc.document_type = document.document_type
    existing_doc.time_period = document.time_period
    existing_doc.unique_id = document.unique_id
    existing_doc.page_count = document.page_count
    existing_doc.character_count = document.character_count
    existing_doc.indexing_status = ProcessingStatus.INDEXING
    existing_doc.duplicate_detected = False
    existing_doc.existing_document_id = None
    existing_doc.uploaded_at = datetime.utcnow()

    # Delete the new document record (we're using the existing one)
    db.delete(document)
    db.commit()

    # Queue document for indexing (sequential processing)
    # Document is already classified, just needs indexing
    from app.services.queue_service import queue_service

    existing_doc.status = DocumentStatus.PENDING
    db.commit()
    queue_service.add_document(existing_document_id)

    db.refresh(existing_doc)
    return existing_doc


@router.post("/{document_id}/rerun-indexing", response_model=DocumentSchema)
async def rerun_indexing(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run indexing for an already indexed document.
    Deletes existing chunk embeddings and re-indexes the document.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only allow re-indexing if document is already indexed
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail="Document must be indexed before re-indexing. Current status: "
            + str(document.indexing_status),
        )

    # Delete existing chunk embeddings
    delete_chunk_embeddings(document_id)

    # Set status to INDEXING and queue for processing
    document.indexing_status = ProcessingStatus.INDEXING
    db.commit()

    # Queue document for INDEX_ONLY processing
    # Queue for re-indexing using the new queue service
    from app.services.queue_service import queue_service

    document.status = DocumentStatus.PENDING  # Or another status that triggers indexing
    db.commit()
    queue_service.add_document(document_id)

    db.refresh(document)
    return document


if DEBUG:

    @router.post("/{document_id}/replace-and-index-test", response_model=DocumentSchema)
    async def replace_and_index_test(
        document_id: str,
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: Session = Depends(get_db),
    ):
        """
        TEST ENDPOINT: Replace and index without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(id="test-user-id", email="test@example.com", name="Test User")
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        return await replace_and_index(document_id, background_tasks, db, test_user)

    @router.post("/{document_id}/rerun-indexing-test", response_model=DocumentSchema)
    async def rerun_indexing_test(
        document_id: str,
        db: Session = Depends(get_db),
    ):
        """
        TEST ENDPOINT: Re-run indexing without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(id="test-user-id", email="test@example.com", name="Test User")
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

        return await rerun_indexing(document_id, db, test_user)

    @router.delete("/{document_id}/test")
    async def delete_document_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Delete document without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Only allow deletion if document is not yet indexed or is a duplicate
        if document.indexing_status == ProcessingStatus.INDEXED and not document.duplicate_detected:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete indexed document. Only unprocessed or duplicate documents can be deleted.",
            )

        # Delete file if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

        # Delete chunk embeddings if they exist
        delete_chunk_embeddings(document_id)

        # Delete document from database
        db.delete(document)
        db.commit()

        return {"message": "Document deleted successfully"}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete a document (useful for canceling duplicate uploads).
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only allow deletion if document is not yet indexed or is a duplicate
    if document.indexing_status == ProcessingStatus.INDEXED and not document.duplicate_detected:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete indexed document. Only unprocessed or duplicate documents can be deleted.",
        )

    # Delete file if it exists
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

    # Delete chunk embeddings if they exist
    delete_chunk_embeddings(document_id)

    # Delete document from database
    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}


@router.delete("/{document_id}/permanent")
async def delete_document_permanent(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Permanently delete a document and all associated data including financial statements.
    This is a destructive operation that cannot be undone.
    """
    from app.models.amortization import Amortization, AmortizationLineItem
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    from app.models.gaap_reconciliation import GAAPReconciliation
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    from app.models.non_operating_classification import (
        NonOperatingClassification,
        NonOperatingClassificationItem,
    )
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
    from app.models.shares_outstanding import SharesOutstanding
    from app.utils.financial_statement_progress import clear_progress

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Store document_id to ensure we're using the correct one
    target_document_id = document.id
    print(f"Deleting document {target_document_id} and its associated data")

    # Delete balance sheets and their line items
    balance_sheets = db.query(BalanceSheet).filter_by(document_id=target_document_id).all()
    print(f"Found {len(balance_sheets)} balance sheet(s) for document {target_document_id}")
    for balance_sheet in balance_sheets:
        # Delete line items first
        db.query(BalanceSheetLineItem).filter_by(balance_sheet_id=balance_sheet.id).delete()
        print(f"Deleting balance sheet {balance_sheet.id} for document {target_document_id}")
        db.delete(balance_sheet)

    # Delete income statements and their line items
    income_statements = db.query(IncomeStatement).filter_by(document_id=target_document_id).all()
    print(f"Found {len(income_statements)} income statement(s) for document {target_document_id}")
    for income_statement in income_statements:
        # Delete line items first
        db.query(IncomeStatementLineItem).filter_by(
            income_statement_id=income_statement.id
        ).delete()
        print(f"Deleting income statement {income_statement.id} for document {target_document_id}")
        db.delete(income_statement)

    # Delete amortizations and their line items
    amortizations = db.query(Amortization).filter_by(document_id=target_document_id).all()
    print(f"Found {len(amortizations)} amortization(s) for document {target_document_id}")
    for amortization in amortizations:
        # Delete line items first
        db.query(AmortizationLineItem).filter_by(amortization_id=amortization.id).delete()
        db.delete(amortization)

    # Delete organic growth entries
    organic_growth_entries = db.query(OrganicGrowth).filter_by(document_id=target_document_id).all()
    print(
        f"Found {len(organic_growth_entries)} organic growth entry(ies) for document {target_document_id}"
    )
    for organic_growth in organic_growth_entries:
        db.delete(organic_growth)

    # Delete other assets and their line items
    other_assets_entries = db.query(OtherAssets).filter_by(document_id=target_document_id).all()
    print(
        f"Found {len(other_assets_entries)} other assets entry(ies) for document {target_document_id}"
    )
    for other_assets in other_assets_entries:
        # Delete line items first
        db.query(OtherAssetsLineItem).filter_by(other_assets_id=other_assets.id).delete()
        db.delete(other_assets)

    # Delete other liabilities and their line items
    other_liabilities_entries = (
        db.query(OtherLiabilities).filter_by(document_id=target_document_id).all()
    )
    print(
        f"Found {len(other_liabilities_entries)} other liabilities entry(ies) for document {target_document_id}"
    )
    for other_liabilities in other_liabilities_entries:
        # Delete line items first
        db.query(OtherLiabilitiesLineItem).filter_by(
            other_liabilities_id=other_liabilities.id
        ).delete()
        db.delete(other_liabilities)

    # Delete non-operating classifications and their items
    non_operating_entries = (
        db.query(NonOperatingClassification).filter_by(document_id=target_document_id).all()
    )
    print(
        f"Found {len(non_operating_entries)} non-operating classification(s) for document {target_document_id}"
    )
    for non_operating in non_operating_entries:
        # Delete classification items first
        db.query(NonOperatingClassificationItem).filter_by(
            classification_id=non_operating.id
        ).delete()
        db.delete(non_operating)

    # Delete shares outstanding
    shares_outstanding_entries = (
        db.query(SharesOutstanding).filter_by(document_id=target_document_id).all()
    )
    print(
        f"Found {len(shares_outstanding_entries)} shares outstanding entry(ies) for document {target_document_id}"
    )
    for shares in shares_outstanding_entries:
        db.delete(shares)

    # Delete GAAP reconciliations
    gaap_reconciliations = (
        db.query(GAAPReconciliation).filter_by(document_id=target_document_id).all()
    )
    print(
        f"Found {len(gaap_reconciliations)} GAAP reconciliation(s) for document {target_document_id}"
    )
    for gaap_recon in gaap_reconciliations:
        db.delete(gaap_recon)

    # Delete historical calculations
    historical_calculations = (
        db.query(HistoricalCalculation).filter_by(document_id=target_document_id).all()
    )
    print(
        f"Found {len(historical_calculations)} historical calculation(s) for document {target_document_id}"
    )
    for historical_calculation in historical_calculations:
        db.delete(historical_calculation)

    # Commit financial statement deletions before deleting the document
    db.commit()
    print(f"Committed deletions of all related data for document {target_document_id}")

    # Clear financial statement progress tracking
    clear_progress(target_document_id)

    # Delete file if it exists
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
            print(f"Deleted file: {document.file_path}")
        except Exception as e:
            print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

    # Delete chunk embeddings if they exist
    try:
        delete_chunk_embeddings(target_document_id)
        print(f"Deleted chunk embeddings for document {target_document_id}")
    except Exception as e:
        print(f"Warning: Failed to delete chunk embeddings: {str(e)}")

    # Delete document from database
    db.delete(document)
    db.commit()
    print(f"Successfully deleted document {target_document_id}")

    return {"message": "Document and all associated data deleted successfully"}


if DEBUG:

    @router.delete("/{document_id}/permanent/test")
    async def delete_document_permanent_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Permanently delete a document without authentication.
        """
        from app.models.amortization import Amortization, AmortizationLineItem
        from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
        from app.models.gaap_reconciliation import GAAPReconciliation
        from app.models.historical_calculation import HistoricalCalculation
        from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
        from app.models.non_operating_classification import (
            NonOperatingClassification,
            NonOperatingClassificationItem,
        )
        from app.models.organic_growth import OrganicGrowth
        from app.models.other_assets import OtherAssets, OtherAssetsLineItem
        from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
        from app.models.shares_outstanding import SharesOutstanding
        from app.utils.financial_statement_progress import clear_progress

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Store document_id to ensure we're using the correct one
        target_document_id = document.id
        print(f"[TEST] Deleting document {target_document_id} and its associated data")

        # Delete balance sheets and their line items
        balance_sheets = db.query(BalanceSheet).filter_by(document_id=target_document_id).all()
        for balance_sheet in balance_sheets:
            db.query(BalanceSheetLineItem).filter_by(balance_sheet_id=balance_sheet.id).delete()
            db.delete(balance_sheet)

        # Delete income statements and their line items
        income_statements = (
            db.query(IncomeStatement).filter_by(document_id=target_document_id).all()
        )
        for income_statement in income_statements:
            db.query(IncomeStatementLineItem).filter_by(
                income_statement_id=income_statement.id
            ).delete()
            db.delete(income_statement)

        # Delete amortizations and their line items
        amortizations = db.query(Amortization).filter_by(document_id=target_document_id).all()
        for amortization in amortizations:
            db.query(AmortizationLineItem).filter_by(amortization_id=amortization.id).delete()
            db.delete(amortization)

        # Delete organic growth entries
        organic_growth_entries = (
            db.query(OrganicGrowth).filter_by(document_id=target_document_id).all()
        )
        for organic_growth in organic_growth_entries:
            db.delete(organic_growth)

        # Delete other assets and their line items
        other_assets_entries = db.query(OtherAssets).filter_by(document_id=target_document_id).all()
        for other_assets in other_assets_entries:
            db.query(OtherAssetsLineItem).filter_by(other_assets_id=other_assets.id).delete()
            db.delete(other_assets)

        # Delete other liabilities and their line items
        other_liabilities_entries = (
            db.query(OtherLiabilities).filter_by(document_id=target_document_id).all()
        )
        for other_liabilities in other_liabilities_entries:
            db.query(OtherLiabilitiesLineItem).filter_by(
                other_liabilities_id=other_liabilities.id
            ).delete()
            db.delete(other_liabilities)

        # Delete non-operating classifications and their items
        non_operating_entries = (
            db.query(NonOperatingClassification).filter_by(document_id=target_document_id).all()
        )
        for non_operating in non_operating_entries:
            db.query(NonOperatingClassificationItem).filter_by(
                classification_id=non_operating.id
            ).delete()
            db.delete(non_operating)

        # Delete shares outstanding
        shares_outstanding_entries = (
            db.query(SharesOutstanding).filter_by(document_id=target_document_id).all()
        )
        for shares in shares_outstanding_entries:
            db.delete(shares)

        # Delete GAAP reconciliations
        gaap_reconciliations = (
            db.query(GAAPReconciliation).filter_by(document_id=target_document_id).all()
        )
        for gaap_recon in gaap_reconciliations:
            db.delete(gaap_recon)

        # Delete historical calculations
        historical_calculations = (
            db.query(HistoricalCalculation).filter_by(document_id=target_document_id).all()
        )
        for historical_calculation in historical_calculations:
            db.delete(historical_calculation)

        # Commit financial statement deletions before deleting the document
        db.commit()
        print(f"[TEST] Committed deletions of all related data for document {target_document_id}")

        # Clear financial statement progress tracking
        clear_progress(target_document_id)

        # Delete file if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

        # Delete chunk embeddings if they exist
        try:
            delete_chunk_embeddings(target_document_id)
        except Exception as e:
            print(f"Warning: Failed to delete chunk embeddings: {str(e)}")

        # Delete document from database
        db.delete(document)
        db.commit()
        print(f"[TEST] Successfully deleted document {target_document_id}")

        return {"message": "Document and all associated data deleted successfully"}


def _build_financial_statement_progress(document_id: str, db: Session) -> dict:
    from app.models.amortization import Amortization
    from app.models.balance_sheet import BalanceSheet
    from app.models.income_statement import IncomeStatement
    from app.models.non_operating_classification import NonOperatingClassification
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets
    from app.models.other_liabilities import OtherLiabilities
    from app.utils.financial_statement_progress import get_progress

    progress = get_progress(document_id)
    if progress:
        return progress

    def _active_progress_milestone(key: str) -> dict | None:
        if not progress:
            return None
        milestone = progress.get("milestones", {}).get(key)
        # Return milestone regardless of status (completed, warning, etc.)
        if milestone:
            return milestone
        return None

    # Always check database state to determine actual milestone status
    from app.models.document import Document

    document = db.query(Document).filter(Document.id == document_id).first()
    is_earnings_announcement = (
        document and document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT
    )

    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )
    other_assets = db.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    other_liabilities = (
        db.query(OtherLiabilities).filter(OtherLiabilities.document_id == document_id).first()
    )
    amortization = db.query(Amortization).filter(Amortization.document_id == document_id).first()
    organic_growth = (
        db.query(OrganicGrowth).filter(OrganicGrowth.document_id == document_id).first()
    )
    non_operating = (
        db.query(NonOperatingClassification)
        .filter(NonOperatingClassification.document_id == document_id)
        .first()
    )

    milestones = {}

    # Balance Sheet milestone
    if balance_sheet and balance_sheet.line_items:
        has_classifications = any(
            item.is_operating is not None for item in balance_sheet.line_items
        )
        if balance_sheet.is_valid and has_classifications:
            milestones["balance_sheet"] = {
                "status": "completed",
                "message": "Balance sheet extracted and classified",
                "updated_at": balance_sheet.extraction_date.isoformat()
                if balance_sheet.extraction_date
                else None,
            }
        else:
            error_message = "Balance sheet processing incomplete"
            if balance_sheet.validation_errors:
                try:
                    validation_errors = json.loads(balance_sheet.validation_errors)
                    if validation_errors:
                        error_summary = "; ".join(validation_errors[:3])
                        if len(validation_errors) > 3:
                            error_summary += f" (+{len(validation_errors) - 3} more)"
                        error_message = f"Validation failed: {error_summary}"
                except (json.JSONDecodeError, TypeError):
                    pass
            milestones["balance_sheet"] = {
                "status": "error",
                "message": error_message,
                "updated_at": balance_sheet.extraction_date.isoformat()
                if balance_sheet.extraction_date
                else None,
            }
    elif _active_progress_milestone("balance_sheet"):
        milestones["balance_sheet"] = _active_progress_milestone("balance_sheet")
    else:
        milestones["balance_sheet"] = {
            "status": "not_found",
            "message": "Balance sheet not found",
            "updated_at": None,
        }

    # Income Statement milestone
    if income_statement and income_statement.line_items:
        has_classifications = any(
            item.is_operating is not None for item in income_statement.line_items
        )
        if income_statement.is_valid and has_classifications:
            milestones["income_statement"] = {
                "status": "completed",
                "message": "Income statement extracted and classified",
                "updated_at": income_statement.extraction_date.isoformat()
                if income_statement.extraction_date
                else None,
            }
        else:
            error_message = "Income statement processing incomplete"
            if income_statement.validation_errors:
                try:
                    validation_errors = json.loads(income_statement.validation_errors)
                    if validation_errors:
                        error_summary = "; ".join(validation_errors[:3])
                        if len(validation_errors) > 3:
                            error_summary += f" (+{len(validation_errors) - 3} more)"
                        error_message = f"Validation failed: {error_summary}"
                except (json.JSONDecodeError, TypeError):
                    pass
            milestones["income_statement"] = {
                "status": "error",
                "message": error_message,
                "updated_at": income_statement.extraction_date.isoformat()
                if income_statement.extraction_date
                else None,
            }
    elif _active_progress_milestone("income_statement"):
        milestones["income_statement"] = _active_progress_milestone("income_statement")
    else:
        milestones["income_statement"] = {
            "status": "not_found",
            "message": "Income statement not found",
            "updated_at": None,
        }

    # Additional Items milestone
    additional_item_missing = []
    additional_item_errors = []

    shares_present = income_statement and (
        income_statement.basic_shares_outstanding is not None
        or income_statement.diluted_shares_outstanding is not None
    )
    if not shares_present:
        additional_item_missing.append("shares outstanding")

    # Use appropriate label based on document type (document already queried above)
    reconciliation_label = "Non-GAAP reconciliation" if is_earnings_announcement else "amortization"

    if amortization and amortization.line_items:
        if not amortization.is_valid:
            additional_item_errors.append(reconciliation_label)
    else:
        additional_item_missing.append(reconciliation_label)

    if organic_growth:
        if not organic_growth.is_valid:
            additional_item_errors.append("organic growth")
    else:
        additional_item_missing.append("organic growth")

    # Note: document type already checked above for earnings announcement

    if not is_earnings_announcement:
        # Only check for other assets/liabilities for non-earnings announcements
        if other_assets and other_assets.line_items:
            if not other_assets.is_valid:
                additional_item_errors.append("other assets")
        else:
            additional_item_missing.append("other assets")

        if other_liabilities and other_liabilities.line_items:
            if not other_liabilities.is_valid:
                additional_item_errors.append("other liabilities")
        else:
            additional_item_missing.append("other liabilities")

    # Legacy 'extracting_additional_items' block removed.
    # We now strictly use granular milestones (amortization, organic_growth, etc).
    # If in-memory progress is lost (e.g. server restart), we do not attempt
    # to reconstruct a fake aggregate status.
    pass

    # Non-operating classification milestone
    if _active_progress_milestone("classifying_non_operating_items"):
        milestones["classifying_non_operating_items"] = _active_progress_milestone(
            "classifying_non_operating_items"
        )
    elif non_operating and non_operating.line_items and len(non_operating.line_items) > 0:
        milestones["classifying_non_operating_items"] = {
            "status": "completed",
            "message": "Non-operating items classified",
            "updated_at": non_operating.extraction_date.isoformat()
            if non_operating.extraction_date
            else None,
        }
    elif non_operating:
        milestones["classifying_non_operating_items"] = {
            "status": "error",
            "message": "Non-operating classification incomplete",
            "updated_at": non_operating.extraction_date.isoformat()
            if non_operating.extraction_date
            else None,
        }
    else:
        milestones["classifying_non_operating_items"] = {
            "status": "not_found",
            "message": "Non-operating classification not found",
            "updated_at": None,
        }

    # Determine overall status
    if progress:
        has_in_progress = any(m.get("status") == "in_progress" for m in milestones.values())
        has_pending = any(m.get("status") == "pending" for m in milestones.values())
        if has_in_progress or has_pending:
            status = "processing"
        else:
            has_error = any(m.get("status") == "error" for m in milestones.values())
            all_completed = all(m.get("status") == "completed" for m in milestones.values())
            has_not_found = any(m.get("status") == "not_found" for m in milestones.values())
            if has_error:
                status = "error"
            elif all_completed:
                status = "completed"
            elif has_not_found:
                status = "not_found"
            else:
                status = "checking"
    else:
        has_error = any(m.get("status") == "error" for m in milestones.values())
        all_completed = all(m.get("status") == "completed" for m in milestones.values())
        has_not_found = any(m.get("status") == "not_found" for m in milestones.values())

        if has_error:
            status = "error"
        elif all_completed:
            status = "completed"
        elif has_not_found:
            status = "not_found"
        else:
            status = "not_started"

    return {
        "status": status,
        "milestones": milestones,
        "last_updated": progress.get("last_updated") if progress else None,
    }


@router.get("/{document_id}/financial-statement-progress")
async def get_financial_statement_progress(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get financial statement processing progress with milestones"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return _build_financial_statement_progress(document_id, db)


@router.get("/{document_id}/status", response_model=DocumentSchema)
async def get_document_status(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get document status including indexing progress (shared dashboard - all users can see all documents)"""
    document = (
        db.query(Document)
        .options(
            joinedload(Document.balance_sheet),
            joinedload(Document.income_statement),
        )
        .filter(Document.id == document_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return add_uploader_name_to_document(db, document)


if DEBUG:

    @router.get("/{document_id}/financial-statement-progress-test")
    async def get_financial_statement_progress_test(
        document_id: str, db: Session = Depends(get_db)
    ):
        """TEST ENDPOINT: Get financial statement processing progress without authentication"""
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return _build_financial_statement_progress(document_id, db)

    @router.get("/{document_id}/status-test", response_model=DocumentSchema)
    async def get_document_status_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Get document status without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        document = (
            db.query(Document)
            .options(
                joinedload(Document.balance_sheet),
                joinedload(Document.income_statement),
            )
            .filter(Document.id == document_id)
            .first()
        )
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return add_uploader_name_to_document(db, document)


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all chunks for an indexed document.
    Returns chunk text, page ranges, and metadata for each chunk.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only return chunks for indexed documents
    if document.indexing_status != ProcessingStatus.INDEXED:
        raise HTTPException(
            status_code=400,
            detail=f"Document is not indexed. Current status: {document.indexing_status.value}",
        )

    # Get chunk metadata
    chunk_metadata = get_chunk_metadata(document_id)
    if not chunk_metadata:
        raise HTTPException(
            status_code=404, detail="Chunk metadata not found. Document may not be indexed."
        )

    num_chunks = chunk_metadata.get("num_chunks", 0)
    chunk_size = chunk_metadata.get("chunk_size", 2)

    # Check if this is a legacy page-based chunking (chunk_size small, e.g. < 100)
    is_legacy_page_based = chunk_size < 100

    chunks = []

    if is_legacy_page_based:
        # Legacy: Page-based chunks
        # Return a simple message instead of trying to load content
        for chunk_index in range(num_chunks):
            start_page = chunk_index * chunk_size
            end_page = start_page + chunk_size

            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": "Legacy chunk (page-based), please re-index document to view content.",
                    "start_page": start_page,
                    "end_page": end_page - 1,
                    "character_count": 0,
                    "note": "Legacy page-based chunk",
                }
            )

    else:
        # New: Character-based chunks
        # Load full text once (cached or extracted)
        full_text = load_full_document_text(document_id, document.file_path)
        total_chars = len(full_text)

        for chunk_index in range(num_chunks):
            try:
                start_char = chunk_index * chunk_size
                end_char = min(start_char + chunk_size, total_chars)
                chunk_text = full_text[start_char:end_char]

                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "start_char": start_char,
                        "end_char": end_char,
                        "start_page": None,
                        "end_page": None,
                        "character_count": len(chunk_text),
                    }
                )
            except Exception as e:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": None,
                        "start_char": chunk_index * chunk_size,
                        "end_char": (chunk_index + 1) * chunk_size,
                        "character_count": 0,
                        "error": str(e),
                    }
                )

    return {
        "document_id": document_id,
        "num_chunks": num_chunks,
        "chunk_size": chunk_size,
        "total_pages": chunk_metadata.get("total_pages", 0),
        "chunks": chunks,
    }


if DEBUG:

    @router.get("/{document_id}/chunks-test")
    async def get_document_chunks_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Get all chunks for an indexed document without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Only return chunks for indexed documents
        if document.indexing_status != ProcessingStatus.INDEXED:
            raise HTTPException(
                status_code=400,
                detail=f"Document is not indexed. Current status: {document.indexing_status.value}",
            )

        # Get chunk metadata
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            raise HTTPException(
                status_code=404, detail="Chunk metadata not found. Document may not be indexed."
            )

        num_chunks = chunk_metadata.get("num_chunks", 0)
        chunk_size = chunk_metadata.get("chunk_size", 2)

        is_legacy_page_based = chunk_size < 100

        chunks = []

        if is_legacy_page_based:
            # Legacy: Page-based chunks
            # Return a simple message instead of trying to load content
            for chunk_index in range(num_chunks):
                start_page = chunk_index * chunk_size
                end_page = start_page + chunk_size

                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": "Legacy chunk (page-based), please re-index document to view content.",
                        "start_page": start_page,
                        "end_page": end_page - 1,
                        "character_count": 0,
                        "note": "Legacy page-based chunk",
                    }
                )
        else:
            full_text = load_full_document_text(document_id, document.file_path)
            total_chars = len(full_text)

            for chunk_index in range(num_chunks):
                try:
                    start_char = chunk_index * chunk_size
                    end_char = min(start_char + chunk_size, total_chars)
                    chunk_text = full_text[start_char:end_char]

                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "text": chunk_text,
                            "start_char": start_char,
                            "end_char": end_char,
                            "start_page": None,
                            "end_page": None,
                            "character_count": len(chunk_text),
                        }
                    )
                except Exception as e:
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "text": None,
                            "start_char": chunk_index * chunk_size,
                            "end_char": (chunk_index + 1) * chunk_size,
                            "character_count": 0,
                            "error": str(e),
                        }
                    )

        return {
            "document_id": document_id,
            "num_chunks": num_chunks,
            "chunk_size": chunk_size,
            "total_pages": chunk_metadata.get("total_pages", 0),
            "chunks": chunks,
        }


@router.post("/", response_model=DocumentSchema)
async def create_document(
    document: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new document record (legacy endpoint - use upload endpoint instead)"""
    db_document = Document(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_id=document.company_id,
        filename=document.filename,
        file_path=document.file_path,
        document_type=document.document_type,
        time_period=document.time_period,
        summary=document.summary,
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


@router.patch("/{document_id}", response_model=DocumentSchema)
async def update_document(
    document_id: str,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a document (shared dashboard - any user can update)"""
    db_document = db.query(Document).filter(Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = document_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_document, field, value)

    db.commit()
    db.refresh(db_document)
    return db_document

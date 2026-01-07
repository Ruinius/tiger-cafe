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

from agents.document_classifier import classify_document
from app.database import get_db
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.document import (
    ClassificationResult,
    DocumentCreate,
    DocumentUpdate,
    DocumentUploadResponse,
    DuplicateInfo,
)
from app.schemas.document import Document as DocumentSchema
from app.services.document_processing import DocumentProcessingMode, process_document
from app.utils.document_hash import generate_document_hash
from app.utils.document_indexer import delete_chunk_embeddings, get_chunk_metadata, get_chunk_text
from app.utils.pdf_extractor import extract_text_from_pdf
from config.config import DEBUG, UPLOAD_DIR

router = APIRouter()

# In-memory tracking of active uploads (in production, use Redis or database)
active_uploads = {}  # {document_id: {"status": "uploading|classifying|indexing", "progress": 0-100}}


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
        "summary": document.summary,
        "unique_id": document.unique_id,
        "indexing_status": document.indexing_status,
        "analysis_status": document.analysis_status,
        "page_count": document.page_count,
        "character_count": document.character_count,
        "uploaded_at": document.uploaded_at,
        "indexed_at": document.indexed_at,
        "processed_at": document.processed_at,
        "duplicate_detected": document.duplicate_detected,
        "existing_document_id": document.existing_document_id,
        "uploader_name": None,
        "balance_sheet_status": "not_extracted",
        "income_statement_status": "not_extracted",
        "gaap_reconciliation_status": "not_extracted",  # Placeholder for future
    }
    # Get uploader name
    if document.user_id:
        user = db.query(User).filter(User.id == document.user_id).first()
        if user:
            doc_dict["uploader_name"] = user.name or user.email

    # Check for financial statements (assumes eager loading or lazy loading)
    if document.balance_sheet:
        doc_dict["balance_sheet_status"] = "valid" if document.balance_sheet.is_valid else "invalid"

    if document.income_statement:
        doc_dict["income_statement_status"] = (
            "valid" if document.income_statement.is_valid else "invalid"
        )

    return doc_dict


# New batch upload endpoint for multi-file upload
@router.post("/upload-batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload multiple documents (up to 10) and process them asynchronously.
    Returns immediately with document IDs. Processing happens in background.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")

    document_ids = []
    import asyncio

    async def read_file_content(file: UploadFile) -> tuple[bytes, str, str]:
        """Read file content asynchronously"""
        document_id = str(uuid.uuid4())
        file_content = await file.read()
        return file_content, file.filename, document_id

    # Read all files in parallel
    file_tasks = [read_file_content(file) for file in files if file.filename.endswith(".pdf")]

    if not file_tasks:
        raise HTTPException(status_code=400, detail="No valid PDF files provided")

    file_results = await asyncio.gather(*file_tasks)

    # Start background tasks for all files
    for file_content, filename, document_id in file_results:
        document_ids.append(document_id)
        background_tasks.add_task(
            upload_and_process_async_with_content,
            file_content,
            filename,
            document_id,
            current_user.id,
            db,
        )

    return {"document_ids": document_ids, "message": f"Uploading {len(document_ids)} documents"}


if DEBUG:

    @router.post("/upload-batch-test")
    async def upload_batch_test(
        files: list[UploadFile] = File(...),
        background_tasks: BackgroundTasks = BackgroundTasks(),
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

        document_ids = []
        import asyncio

        async def read_file_content(file: UploadFile) -> tuple[bytes, str, str]:
            """Read file content asynchronously"""
            document_id = str(uuid.uuid4())
            file_content = await file.read()
            return file_content, file.filename, document_id

        # Read all files in parallel
        file_tasks = [read_file_content(file) for file in files if file.filename.endswith(".pdf")]

        if not file_tasks:
            raise HTTPException(status_code=400, detail="No valid PDF files provided")

        file_results = await asyncio.gather(*file_tasks)

        # Start background tasks for all files
        for file_content, filename, document_id in file_results:
            document_ids.append(document_id)
            background_tasks.add_task(
                upload_and_process_async_with_content,
                file_content,
                filename,
                document_id,
                test_user.id,
                db,
            )

        return {"document_ids": document_ids, "message": f"Uploading {len(document_ids)} documents"}


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


def upload_and_process_async_with_content(
    file_content: bytes, filename: str, document_id: str, user_id: str, db: Session
):
    """
    Complete async workflow with file content already read: upload → classify → check duplicate → index (if no duplicate).
    This function handles the entire process in the background.
    """

    from app.database import SessionLocal

    db_session = SessionLocal()
    file_path = None

    try:
        # Create a temporary document record with UPLOADING status
        placeholder_company = db_session.query(Company).first()
        if not placeholder_company:
            # Create a temporary placeholder company
            placeholder_company = Company(id=str(uuid.uuid4()), name="Processing...", ticker=None)
            db_session.add(placeholder_company)
            db_session.commit()

        # Create document record with UPLOADING status
        document = Document(
            id=document_id,
            user_id=user_id,
            company_id=placeholder_company.id,
            filename=filename,
            file_path="",  # Will be set after upload
            indexing_status=ProcessingStatus.UPLOADING,
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)  # Ensure document is fully committed and visible

        # Step 1: Save file
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_extension = os.path.splitext(filename)[1]
        saved_filename = f"{document_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, saved_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        # Update document with file path
        document.file_path = file_path
        db_session.commit()

        # Queue document for classification and indexing (sequential processing)
        # Upload is complete, now classification and indexing will happen in the queue
        from app.utils.document_processing_queue import queue_document_for_processing

        queue_document_for_processing(document_id)

    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        if db_session:
            try:
                document = db_session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.indexing_status = ProcessingStatus.ERROR
                    db_session.commit()
            except Exception:
                pass
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    finally:
        if db_session:
            db_session.close()


def upload_and_process_async(file: UploadFile, document_id: str, user_id: str, db: Session):
    """
    Complete async workflow: upload → classify → check duplicate → index (if no duplicate).
    This function handles the entire process in the background.
    """
    from app.database import SessionLocal

    db_session = SessionLocal()
    file_path = None

    try:
        # Create a temporary document record with UPLOADING status
        # We need to get company first, but we'll update it later
        # For now, create a placeholder company
        placeholder_company = db_session.query(Company).first()
        if not placeholder_company:
            # Create a temporary placeholder company
            placeholder_company = Company(id=str(uuid.uuid4()), name="Processing...", ticker=None)
            db_session.add(placeholder_company)
            db_session.commit()

        # Create document record with UPLOADING status
        document = Document(
            id=document_id,
            user_id=user_id,
            company_id=placeholder_company.id,
            filename=file.filename,
            file_path="",  # Will be set after upload
            indexing_status=ProcessingStatus.UPLOADING,
        )
        db_session.add(document)
        db_session.commit()

        # Step 1: Upload file
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_extension = os.path.splitext(file.filename)[1]
        saved_filename = f"{document_id}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, saved_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update document with file path
        document.file_path = file_path
        db_session.commit()
        process_document(
            db_session=db_session,
            document_id=document_id,
            mode=DocumentProcessingMode.FULL,
        )

    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        if db_session:
            try:
                document = db_session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.indexing_status = ProcessingStatus.ERROR
                    db_session.commit()
            except Exception:
                pass
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    finally:
        if db_session:
            db_session.close()


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

        # Use the same logic as the authenticated endpoint
        return await upload_document_internal(file, db, test_user)


async def upload_document_internal(file: UploadFile, db: Session, current_user: User):
    """
    Internal upload function shared by authenticated and test endpoints.
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

    try:
        processing_result = process_document(
            db_session=db,
            mode=DocumentProcessingMode.PREVIEW,
            file_path=file_path,
            filename=file.filename,
            document_id=document_id,
        )
    except ValueError as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

    classification_data = processing_result.classification_data
    text_preview = processing_result.extracted_text_preview
    preliminary_summary = processing_result.summary

    # Get or create company
    company_name = classification_data.get("company_name")
    ticker = classification_data.get("ticker")

    if not company_name:
        # Clean up file on error
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="Could not identify company from document. Please ensure the document contains company information.",
        )

    # Check for duplicates
    duplicate_info = None
    document_type = classification_data.get("document_type")
    time_period = classification_data.get("time_period")
    duplicate_check = processing_result.duplicate_check

    if duplicate_check and duplicate_check.get("is_duplicate"):
        existing_doc = duplicate_check["existing_document"]
        existing_user = db.query(User).filter(User.id == existing_doc.user_id).first()

        duplicate_info = DuplicateInfo(
            is_duplicate=True,
            existing_document_id=existing_doc.id,
            existing_document_filename=existing_doc.filename,
            existing_document_uploaded_at=existing_doc.uploaded_at,
            existing_document_uploaded_by=existing_user.name if existing_user else "Unknown",
            match_reason=duplicate_check["match_reason"],
        )

    # Create classification result
    classification_result = ClassificationResult(
        document_type=document_type,
        time_period=time_period,
        company_name=company_name,
        ticker=ticker,
        confidence=classification_data.get("confidence"),
        extracted_text_preview=text_preview,
        summary=preliminary_summary,
    )

    # Determine if confirmation is required
    requires_confirmation = (
        duplicate_info is None  # New document needs confirmation
        or (duplicate_info and duplicate_info.is_duplicate)  # Duplicate also needs confirmation
    )

    message = "Document uploaded and classified successfully."
    if duplicate_info and duplicate_info.is_duplicate:
        message = f"Potential duplicate detected. A similar document was uploaded by {duplicate_info.existing_document_uploaded_by}."

    return DocumentUploadResponse(
        document_id=document_id,
        classification=classification_result,
        duplicate_info=duplicate_info,
        requires_confirmation=requires_confirmation,
        message=message,
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
    company_name = classification_data.get("company_name")
    if not company_name:
        raise HTTPException(status_code=400, detail="Company not found")

    company = db.query(Company).filter(Company.name.ilike(company_name)).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

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
    from app.utils.document_processing_queue import queue_document_for_processing

    # Set status to UPLOADING so queue knows to do full classification and indexing
    document.indexing_status = ProcessingStatus.UPLOADING
    db.commit()
    queue_document_for_processing(document.id)

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
    from app.utils.document_processing_queue import queue_document_for_processing

    queue_document_for_processing(existing_document_id)

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
    from app.utils.document_processing_queue import queue_document_for_processing

    queue_document_for_processing(document_id)

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
    from app.models.amortization import Amortization
    from app.models.balance_sheet import BalanceSheet
    from app.models.historical_calculation import HistoricalCalculation
    from app.models.income_statement import IncomeStatement
    from app.models.non_operating_classification import NonOperatingClassification
    from app.models.organic_growth import OrganicGrowth
    from app.models.other_assets import OtherAssets
    from app.models.other_liabilities import OtherLiabilities
    from app.utils.financial_statement_progress import clear_progress

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Store document_id to ensure we're using the correct one
    target_document_id = document.id
    print(f"Deleting document {target_document_id} and its associated data")

    # Delete financial statements explicitly with proper filtering
    # Use filter_by to ensure we're only deleting for this specific document
    balance_sheets = db.query(BalanceSheet).filter_by(document_id=target_document_id).all()
    print(f"Found {len(balance_sheets)} balance sheet(s) for document {target_document_id}")
    for balance_sheet in balance_sheets:
        print(f"Deleting balance sheet {balance_sheet.id} for document {target_document_id}")
        db.delete(balance_sheet)

    income_statements = db.query(IncomeStatement).filter_by(document_id=target_document_id).all()
    print(f"Found {len(income_statements)} income statement(s) for document {target_document_id}")
    for income_statement in income_statements:
        print(f"Deleting income statement {income_statement.id} for document {target_document_id}")
        db.delete(income_statement)

    amortizations = db.query(Amortization).filter_by(document_id=target_document_id).all()
    for amortization in amortizations:
        db.delete(amortization)

    organic_growth_entries = db.query(OrganicGrowth).filter_by(document_id=target_document_id).all()
    for organic_growth in organic_growth_entries:
        db.delete(organic_growth)

    other_assets_entries = db.query(OtherAssets).filter_by(document_id=target_document_id).all()
    for other_assets in other_assets_entries:
        db.delete(other_assets)

    other_liabilities_entries = (
        db.query(OtherLiabilities).filter_by(document_id=target_document_id).all()
    )
    for other_liabilities in other_liabilities_entries:
        db.delete(other_liabilities)

    non_operating_entries = (
        db.query(NonOperatingClassification).filter_by(document_id=target_document_id).all()
    )
    for non_operating in non_operating_entries:
        db.delete(non_operating)

    # Delete historical calculations
    historical_calculations = (
        db.query(HistoricalCalculation).filter_by(document_id=target_document_id).all()
    )
    for historical_calculation in historical_calculations:
        db.delete(historical_calculation)

    # Commit financial statement deletions before deleting the document
    db.commit()
    print(f"Committed deletions of financial statements for document {target_document_id}")

    # Clear financial statement progress tracking
    clear_progress(target_document_id)

    # Delete file if it exists
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

    # Delete chunk embeddings if they exist
    delete_chunk_embeddings(target_document_id)

    # Delete document from database
    db.delete(document)
    db.commit()

    return {"message": "Document and all associated data deleted successfully"}


if DEBUG:

    @router.delete("/{document_id}/permanent/test")
    async def delete_document_permanent_test(document_id: str, db: Session = Depends(get_db)):
        """
        TEST ENDPOINT: Permanently delete a document without authentication.
        """
        from app.models.amortization import Amortization
        from app.models.balance_sheet import BalanceSheet
        from app.models.historical_calculation import HistoricalCalculation
        from app.models.income_statement import IncomeStatement
        from app.models.non_operating_classification import NonOperatingClassification
        from app.models.organic_growth import OrganicGrowth
        from app.models.other_assets import OtherAssets
        from app.models.other_liabilities import OtherLiabilities
        from app.utils.financial_statement_progress import clear_progress

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Store document_id to ensure we're using the correct one
        target_document_id = document.id

        # Delete financial statements explicitly with proper filtering
        # Use filter_by to ensure we're only deleting for this specific document
        balance_sheets = db.query(BalanceSheet).filter_by(document_id=target_document_id).all()
        for balance_sheet in balance_sheets:
            db.delete(balance_sheet)

        income_statements = (
            db.query(IncomeStatement).filter_by(document_id=target_document_id).all()
        )
        for income_statement in income_statements:
            db.delete(income_statement)

        amortizations = db.query(Amortization).filter_by(document_id=target_document_id).all()
        for amortization in amortizations:
            db.delete(amortization)

        organic_growth_entries = (
            db.query(OrganicGrowth).filter_by(document_id=target_document_id).all()
        )
        for organic_growth in organic_growth_entries:
            db.delete(organic_growth)

        other_assets_entries = db.query(OtherAssets).filter_by(document_id=target_document_id).all()
        for other_assets in other_assets_entries:
            db.delete(other_assets)

        other_liabilities_entries = (
            db.query(OtherLiabilities).filter_by(document_id=target_document_id).all()
        )
        for other_liabilities in other_liabilities_entries:
            db.delete(other_liabilities)

        non_operating_entries = (
            db.query(NonOperatingClassification).filter_by(document_id=target_document_id).all()
        )
        for non_operating in non_operating_entries:
            db.delete(non_operating)

        # Delete historical calculations
        historical_calculations = (
            db.query(HistoricalCalculation).filter_by(document_id=target_document_id).all()
        )
        for historical_calculation in historical_calculations:
            db.delete(historical_calculation)

        # Commit financial statement deletions before deleting the document
        db.commit()

        # Clear financial statement progress tracking
        clear_progress(target_document_id)

        # Delete file if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                print(f"Warning: Failed to delete file {document.file_path}: {str(e)}")

        # Delete chunk embeddings if they exist
        delete_chunk_embeddings(target_document_id)

        # Delete document from database
        db.delete(document)
        db.commit()

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

    def _active_progress_milestone(key: str) -> dict | None:
        if not progress:
            return None
        milestone = progress.get("milestones", {}).get(key)
        if milestone and milestone.get("status") in ["pending", "in_progress"]:
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

    if not income_statement and not _active_progress_milestone("extracting_additional_items"):
        milestones["extracting_additional_items"] = {
            "status": "not_found",
            "message": "Additional items not found",
            "updated_at": None,
        }
    elif not additional_item_missing and not additional_item_errors:
        milestones["extracting_additional_items"] = {
            "status": "completed",
            "message": "Additional items extracted",
            "updated_at": income_statement.extraction_date.isoformat()
            if income_statement and income_statement.extraction_date
            else None,
        }
    elif _active_progress_milestone("extracting_additional_items"):
        milestones["extracting_additional_items"] = _active_progress_milestone(
            "extracting_additional_items"
        )
    elif not additional_item_missing and additional_item_errors:
        milestones["extracting_additional_items"] = {
            "status": "error",
            "message": f"Validation errors for: {', '.join(additional_item_errors)}",
            "updated_at": income_statement.extraction_date.isoformat()
            if income_statement and income_statement.extraction_date
            else None,
        }
    else:
        milestones["extracting_additional_items"] = {
            "status": "error",
            "message": f"Missing: {', '.join(additional_item_missing)}",
            "updated_at": income_statement.extraction_date.isoformat()
            if income_statement and income_statement.extraction_date
            else None,
        }

    # Non-operating classification milestone
    if non_operating and non_operating.line_items and len(non_operating.line_items) > 0:
        milestones["classifying_non_operating_items"] = {
            "status": "completed",
            "message": "Non-operating items classified",
            "updated_at": non_operating.extraction_date.isoformat()
            if non_operating.extraction_date
            else None,
        }
    elif _active_progress_milestone("classifying_non_operating_items"):
        milestones["classifying_non_operating_items"] = _active_progress_milestone(
            "classifying_non_operating_items"
        )
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

    # Get all chunks
    chunks = []
    for chunk_index in range(num_chunks):
        try:
            chunk_text, start_page, end_page = get_chunk_text(
                document.file_path, chunk_index, chunk_size
            )
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "start_page": start_page,
                    "end_page": end_page - 1,  # end_page is exclusive, so subtract 1 for display
                    "character_count": len(chunk_text),
                }
            )
        except Exception as e:
            # If a chunk fails, continue with others
            print(f"Error loading chunk {chunk_index}: {str(e)}")
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": None,
                    "start_page": chunk_index * chunk_size,
                    "end_page": min(
                        (chunk_index + 1) * chunk_size - 1, chunk_metadata.get("total_pages", 0) - 1
                    ),
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

        # Get all chunks
        chunks = []
        for chunk_index in range(num_chunks):
            try:
                chunk_text, start_page, end_page = get_chunk_text(
                    document.file_path, chunk_index, chunk_size
                )
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "start_page": start_page,
                        "end_page": end_page
                        - 1,  # end_page is exclusive, so subtract 1 for display
                        "character_count": len(chunk_text),
                    }
                )
            except Exception as e:
                # If a chunk fails, continue with others
                print(f"Error loading chunk {chunk_index}: {str(e)}")
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "text": None,
                        "start_page": chunk_index * chunk_size,
                        "end_page": min(
                            (chunk_index + 1) * chunk_size - 1,
                            chunk_metadata.get("total_pages", 0) - 1,
                        ),
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

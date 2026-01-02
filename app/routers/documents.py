"""
Document routes
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db, SessionLocal
from app.models.document import Document, ProcessingStatus
from app.models.company import Company
from app.models.user import User
from app.schemas.document import (
    Document as DocumentSchema, 
    DocumentCreate, 
    DocumentUpdate,
    DocumentUploadResponse,
    ClassificationResult,
    DuplicateInfo
)
from app.routers.auth import get_current_user
from app.utils.pdf_extractor import extract_text_from_pdf, get_pdf_metadata
import pdfplumber
from agents.document_classifier import classify_document
from agents.document_summarizer import generate_document_summary
from app.utils.duplicate_detector import check_duplicate_document
from app.utils.document_indexer import generate_embedding, save_embedding
from app.utils.document_hash import generate_document_hash
from config.config import UPLOAD_DIR, DEBUG
import uuid
import os
import shutil
from datetime import datetime

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
        "uploader_name": None
    }
    # Get uploader name
    if document.user_id:
        user = db.query(User).filter(User.id == document.user_id).first()
        if user:
            doc_dict["uploader_name"] = user.name or user.email
    return doc_dict


# New batch upload endpoint for multi-file upload
@router.post("/upload-batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload multiple documents (up to 10) and process them asynchronously.
    Returns immediately with document IDs. Processing happens in background.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")
    
    document_ids = []
    for file in files:
        if not file.filename.endswith('.pdf'):
            continue  # Skip non-PDF files
        
        document_id = str(uuid.uuid4())
        document_ids.append(document_id)
        
        # Read file content before request completes
        file_content = await file.read()
        filename = file.filename
        
        # Start async upload process with file content
        background_tasks.add_task(
            upload_and_process_async_with_content,
            file_content, filename, document_id, current_user.id, db
        )
    
    return {"document_ids": document_ids, "message": f"Uploading {len(document_ids)} documents"}


if DEBUG:
    @router.post("/upload-batch-test")
    async def upload_batch_test(
        files: List[UploadFile] = File(...),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: Upload multiple documents without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(
                id="test-user-id",
                email="test@example.com",
                name="Test User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")
        
        document_ids = []
        for file in files:
            if not file.filename.endswith('.pdf'):
                continue  # Skip non-PDF files
            
            document_id = str(uuid.uuid4())
            document_ids.append(document_id)
            
            # Read file content before request completes
            file_content = await file.read()
            filename = file.filename
            
            # Start async upload process with file content
            background_tasks.add_task(
                upload_and_process_async_with_content,
                file_content, filename, document_id, test_user.id, db
            )
        
        return {"document_ids": document_ids, "message": f"Uploading {len(document_ids)} documents"}


@router.get("/upload-progress", response_model=List[DocumentSchema])
async def get_upload_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of documents currently being processed (uploading, classifying, or indexing).
    Used to show upload progress in the UI.
    """
    active_statuses = [
        ProcessingStatus.UPLOADING,
        ProcessingStatus.CLASSIFYING,
        ProcessingStatus.INDEXING,
        ProcessingStatus.PENDING
    ]
    # Query all documents with active statuses, ordered by most recent first
    documents = db.query(Document).filter(
        Document.indexing_status.in_(active_statuses)
    ).order_by(Document.uploaded_at.desc()).all()
    return [add_uploader_name_to_document(db, doc) for doc in documents]


if DEBUG:
    @router.get("/upload-progress-test", response_model=List[DocumentSchema])
    async def get_upload_progress_test(
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: Get upload progress without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        active_statuses = [
            ProcessingStatus.UPLOADING,
            ProcessingStatus.CLASSIFYING,
            ProcessingStatus.INDEXING,
            ProcessingStatus.PENDING
        ]
        documents = db.query(Document).filter(
            Document.indexing_status.in_(active_statuses)
        ).order_by(Document.uploaded_at.desc()).all()
        return [add_uploader_name_to_document(db, doc) for doc in documents]


def upload_and_process_async_with_content(
    file_content: bytes,
    filename: str,
    document_id: str,
    user_id: str,
    db: Session
):
    """
    Complete async workflow with file content already read: upload → classify → check duplicate → index (if no duplicate).
    This function handles the entire process in the background.
    """
    from app.database import SessionLocal
    import io
    
    db_session = SessionLocal()
    file_path = None
    
    try:
        # Create a temporary document record with UPLOADING status
        placeholder_company = db_session.query(Company).first()
        if not placeholder_company:
            # Create a temporary placeholder company
            placeholder_company = Company(
                id=str(uuid.uuid4()),
                name="Processing...",
                ticker=None
            )
            db_session.add(placeholder_company)
            db_session.commit()
        
        # Create document record with UPLOADING status
        document = Document(
            id=document_id,
            user_id=user_id,
            company_id=placeholder_company.id,
            filename=filename,
            file_path="",  # Will be set after upload
            indexing_status=ProcessingStatus.UPLOADING
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
        
        # Step 2: Extract text and classify (CLASSIFYING status)
        document.indexing_status = ProcessingStatus.CLASSIFYING
        db_session.commit()
        
        # Extract text from first few pages for classification
        extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=5)
        
        # Generate hash from first 5000 characters (avoids large document issues)
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
        
        # Step 3: Check for duplicates
        document_type = classification_data.get("document_type")
        time_period = classification_data.get("time_period")
        duplicate_check = None
        
        if document_type:
            duplicate_check = check_duplicate_document(
                db=db_session,
                company_id=company.id,
                document_type=document_type,
                time_period=time_period,
                filename=filename,
                unique_id=document_hash
            )
        
        # If duplicate detected, stop and wait for user action
        if duplicate_check and duplicate_check.get("is_duplicate"):
            existing_doc = duplicate_check["existing_document"]
            document.duplicate_detected = True
            document.existing_document_id = existing_doc.id
            document.indexing_status = ProcessingStatus.CLASSIFYING  # Stay in classifying until user confirms
            db_session.commit()
            return  # Stop here, wait for user to click "Replace & Index"
        
        # Step 4: No duplicate, proceed with indexing
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
        
        # Extract full text for indexing
        full_extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=None)
        
        # Generate and save embedding
        embedding = generate_embedding(full_extracted_text)
        save_embedding(embedding, document_id)
        
        # Update final status
        document.indexing_status = ProcessingStatus.INDEXED
        document.indexed_at = datetime.utcnow()
        document.page_count = total_pages
        document.character_count = character_count
        db_session.commit()
        
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
            except:
                pass
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
    finally:
        if db_session:
            db_session.close()


def upload_and_process_async(
    file: UploadFile,
    document_id: str,
    user_id: str,
    db: Session
):
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
            placeholder_company = Company(
                id=str(uuid.uuid4()),
                name="Processing...",
                ticker=None
            )
            db_session.add(placeholder_company)
            db_session.commit()
        
        # Create document record with UPLOADING status
        document = Document(
            id=document_id,
            user_id=user_id,
            company_id=placeholder_company.id,
            filename=file.filename,
            file_path="",  # Will be set after upload
            indexing_status=ProcessingStatus.UPLOADING
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
        
        # Step 2: Extract text and classify (CLASSIFYING status)
        document.indexing_status = ProcessingStatus.CLASSIFYING
        db_session.commit()
        
        # Extract text from first few pages for classification
        extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=5)
        
        # Generate hash from first 5000 characters (avoids large document issues)
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
        
        # Step 3: Check for duplicates
        document_type = classification_data.get("document_type")
        time_period = classification_data.get("time_period")
        duplicate_check = None
        
        if document_type:
            duplicate_check = check_duplicate_document(
                db=db_session,
                company_id=company.id,
                document_type=document_type,
                time_period=time_period,
                filename=file.filename,
                unique_id=document_hash
            )
        
        # If duplicate detected, stop and wait for user action
        if duplicate_check and duplicate_check.get("is_duplicate"):
            existing_doc = duplicate_check["existing_document"]
            document.duplicate_detected = True
            document.existing_document_id = existing_doc.id
            document.indexing_status = ProcessingStatus.CLASSIFYING  # Stay in classifying until user confirms
            db_session.commit()
            return  # Stop here, wait for user to click "Replace & Index"
        
        # Step 4: No duplicate, proceed with indexing
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
        
        # Extract full text for indexing
        full_extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=None)
        
        # Generate and save embedding
        embedding = generate_embedding(full_extracted_text)
        save_embedding(embedding, document_id)
        
        # Update final status
        document.indexing_status = ProcessingStatus.INDEXED
        document.indexed_at = datetime.utcnow()
        document.page_count = total_pages
        document.character_count = character_count
        db_session.commit()
        
    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        if db_session:
            try:
                document = db_session.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.indexing_status = ProcessingStatus.ERROR
                    db_session.commit()
            except:
                pass
        # Clean up file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
    finally:
        if db_session:
            db_session.close()


# Temporary test endpoint without authentication (for development/testing only)
if DEBUG:
    @router.post("/upload-test", response_model=DocumentUploadResponse)
    async def upload_document_test(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: Upload a PDF document without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        from app.models.user import User
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(
                id="test-user-id",
                email="test@example.com",
                name="Test User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        
        # Use the same logic as the authenticated endpoint
        return await upload_document_internal(file, db, test_user)


async def upload_document_internal(
    file: UploadFile,
    db: Session,
    current_user: User
):
    """
    Internal upload function shared by authenticated and test endpoints.
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
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
    
    # Extract text from first few pages for classification
    try:
        extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=5)
        text_preview = extracted_text[:500]  # First 500 chars for preview
    except Exception as e:
        # Clean up file on error
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error extracting text from PDF: {str(e)}")
    
    # Generate document hash from first 5000 characters (avoids large document issues)
    hash_text = extracted_text[:5000] if len(extracted_text) > 5000 else extracted_text
    document_hash = generate_document_hash(hash_text)
    
    # Classify document using LLM
    try:
        classification_data = classify_document(extracted_text)
    except Exception as e:
        # Clean up file on error
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error classifying document: {str(e)}")
    
    # Generate preliminary summary using LLM (based on first few pages)
    preliminary_summary = None
    try:
        preliminary_summary = generate_document_summary(extracted_text)
    except Exception as e:
        # Summary generation is non-blocking - log error but continue
        print(f"Warning: Failed to generate preliminary summary: {str(e)}")
    
    # Get or create company
    company_name = classification_data.get("company_name")
    ticker = classification_data.get("ticker")
    
    if not company_name:
        # Clean up file on error
        os.remove(file_path)
        raise HTTPException(
            status_code=400, 
            detail="Could not identify company from document. Please ensure the document contains company information."
        )
    
    # Find or create company
    company = db.query(Company).filter(
        Company.name.ilike(company_name)
    ).first()
    
    if not company:
        # Create new company
        company = Company(
            id=str(uuid.uuid4()),
            name=company_name,
            ticker=ticker
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    
    # Check for duplicates
    duplicate_info = None
    document_type = classification_data.get("document_type")
    time_period = classification_data.get("time_period")
    
    if document_type:
        duplicate_check = check_duplicate_document(
            db=db,
            company_id=company.id,
            document_type=document_type,
            time_period=time_period,
            filename=file.filename,
            unique_id=document_hash
        )
        
        if duplicate_check and duplicate_check["is_duplicate"]:
            existing_doc = duplicate_check["existing_document"]
            existing_user = db.query(User).filter(User.id == existing_doc.user_id).first()
            
            duplicate_info = DuplicateInfo(
                is_duplicate=True,
                existing_document_id=existing_doc.id,
                existing_document_filename=existing_doc.filename,
                existing_document_uploaded_at=existing_doc.uploaded_at,
                existing_document_uploaded_by=existing_user.name if existing_user else "Unknown",
                match_reason=duplicate_check["match_reason"]
            )
    
    # Create classification result
    classification_result = ClassificationResult(
        document_type=document_type,
        time_period=time_period,
        company_name=company_name,
        ticker=ticker,
        confidence=classification_data.get("confidence"),
        extracted_text_preview=text_preview,
        summary=preliminary_summary
    )
    
    # Determine if confirmation is required
    requires_confirmation = (
        duplicate_info is None or  # New document needs confirmation
        (duplicate_info and duplicate_info.is_duplicate)  # Duplicate also needs confirmation
    )
    
    message = "Document uploaded and classified successfully."
    if duplicate_info and duplicate_info.is_duplicate:
        message = f"Potential duplicate detected. A similar document was uploaded by {duplicate_info.existing_document_uploaded_by}."
    
    return DocumentUploadResponse(
        document_id=document_id,
        classification=classification_result,
        duplicate_info=duplicate_info,
        requires_confirmation=requires_confirmation,
        message=message
    )


if DEBUG:
    @router.get("/test", response_model=List[DocumentSchema])
    async def list_documents_test(
        company_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: List documents without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        query = db.query(Document)
        if company_id:
            query = query.filter(Document.company_id == company_id)
        documents = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()
        return [add_uploader_name_to_document(db, doc) for doc in documents]


@router.get("/", response_model=List[DocumentSchema])
async def list_documents(
    company_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List documents, optionally filtered by company. Shows all documents (shared dashboard)."""
    query = db.query(Document)
    if company_id:
        query = query.filter(Document.company_id == company_id)
    documents = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()
    
    # Add uploader names to documents
    return [add_uploader_name_to_document(db, doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentSchema)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific document by ID (shared dashboard - all users can see all documents)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return add_uploader_name_to_document(db, document)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Serve the PDF file for a document (shared dashboard - all users can access all documents)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    return FileResponse(
        document.file_path,
        media_type="application/pdf",
        filename=document.filename
    )


if DEBUG:
    @router.get("/{document_id}/file-test")
    async def get_document_file_test(
        document_id: str,
        db: Session = Depends(get_db)
    ):
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
            document.file_path,
            media_type="application/pdf",
            filename=document.filename
        )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        existing_document_id: Optional[str] = None,
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: Session = Depends(get_db)
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
            test_user = User(
                id="test-user-id",
                email="test@example.com",
                name="Test User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        
        # Use the same logic as the authenticated endpoint
        return await confirm_upload_internal(document_id, db, test_user, background_tasks, existing_document_id)


def index_document_async(document_id: str, extracted_text: Optional[str], db: Session):
    """
    Background task to index a document asynchronously.
    If extracted_text is None, will extract from file_path stored in document.
    """
    from app.database import SessionLocal
    
    # Create a new database session for the background task
    db_session = SessionLocal()
    try:
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"Document {document_id} not found for indexing")
            return
        
        # Extract text if not provided
        if extracted_text is None:
            try:
                extracted_text, _, _ = extract_text_from_pdf(document.file_path, max_pages=5)
                # Update hash with first 5000 characters
                hash_text = extracted_text[:5000] if len(extracted_text) > 5000 else extracted_text
                document.unique_id = generate_document_hash(hash_text)
                db_session.commit()
            except Exception as e:
                print(f"Error extracting text for indexing document {document_id}: {str(e)}")
                document.indexing_status = ProcessingStatus.ERROR
                db_session.commit()
                return
        
        # Update status to indexing (if not already)
        if document.indexing_status != ProcessingStatus.INDEXING:
            document.indexing_status = ProcessingStatus.INDEXING
            db_session.commit()
        
        try:
            # Generate embedding
            embedding = generate_embedding(extracted_text)
            # Save embedding
            save_embedding(embedding, document_id)
            
            # Update document status
            document.indexing_status = ProcessingStatus.INDEXED
            document.indexed_at = datetime.utcnow()
            db_session.commit()
        except Exception as e:
            # Mark as error but don't fail the request
            document.indexing_status = ProcessingStatus.ERROR
            db_session.commit()
            # Log error (in production, use proper logging)
            print(f"Error indexing document {document_id}: {str(e)}")
    finally:
        db_session.close()


def process_document_async(document_id: str, file_path: str, db: Session):
    """
    Background task to process document: extract full text, re-classify, generate summary, and index.
    This allows the confirm endpoint to return quickly.
    """
    from app.database import SessionLocal
    
    db_session = SessionLocal()
    extracted_text = None
    try:
        document = db_session.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"Document {document_id} not found for processing")
            return
        
        # Extract full text
        try:
            extracted_text, total_pages, character_count = extract_text_from_pdf(file_path, max_pages=None)
        except Exception as e:
            print(f"Error extracting text for document {document_id}: {str(e)}")
            return
        
        # Update hash with full document hash
        document.unique_id = generate_document_hash(extracted_text)
        
        # Re-classify with full document (more accurate)
        try:
            classification_data = classify_document(extracted_text)
            # Update document with refined classification
            document.document_type = classification_data.get("document_type")
            document.time_period = classification_data.get("time_period")
            document.page_count = total_pages
            document.character_count = character_count
            db_session.commit()
        except Exception as e:
            print(f"Warning: Failed to re-classify document {document_id}: {str(e)}")
        
        # Generate summary asynchronously
        try:
            summary = generate_document_summary(extracted_text)
            if summary:
                document.summary = summary
                db_session.commit()
        except Exception as e:
            print(f"Warning: Failed to generate summary for document {document_id}: {str(e)}")
        
        # Now trigger indexing with the extracted text
        try:
            index_document_async(document_id, extracted_text, db)
        except Exception as e:
            print(f"Warning: Failed to trigger indexing for document {document_id}: {str(e)}")
        
    finally:
        db_session.close()


async def confirm_upload_internal(
    document_id: str,
    db: Session,
    current_user: User,
    background_tasks: BackgroundTasks,
    existing_document_id: Optional[str] = None
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
    hash_text = extracted_text_preview[:5000] if len(extracted_text_preview) > 5000 else extracted_text_preview
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
        
        # Delete old embedding if it exists
        old_embedding_path = os.path.join("data/storage", f"{existing_document_id}.json")
        if os.path.exists(old_embedding_path):
            try:
                os.remove(old_embedding_path)
            except Exception as e:
                print(f"Warning: Failed to delete old embedding: {str(e)}")
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
            analysis_status=ProcessingStatus.PENDING
            # Summary will be generated in background
        )
        db.add(document)
    
    db.commit()
    
    # Start full processing and indexing asynchronously in background
    # This includes: full text extraction, re-classification, summary generation, and indexing
    background_tasks.add_task(process_document_async, document.id, file_path, db)
    
    db.refresh(document)
    return document


@router.post("/confirm-upload", response_model=DocumentSchema)
async def confirm_upload(
    document_id: str,
    existing_document_id: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm document upload and proceed with indexing.
    This creates the document record and starts the indexing process asynchronously.
    If existing_document_id is provided, replaces that document instead of creating a new one.
    """
    return await confirm_upload_internal(document_id, db, current_user, background_tasks, existing_document_id)


@router.post("/{document_id}/replace-and-index", response_model=DocumentSchema)
async def replace_and_index(
    document_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    
    # Delete old file and embedding
    if os.path.exists(existing_doc.file_path):
        try:
            os.remove(existing_doc.file_path)
        except Exception as e:
            print(f"Warning: Failed to delete old file: {str(e)}")
    
    old_embedding_path = os.path.join("data/storage", f"{existing_document_id}_embedding.json")
    if os.path.exists(old_embedding_path):
        try:
            os.remove(old_embedding_path)
        except Exception as e:
            print(f"Warning: Failed to delete old embedding: {str(e)}")
    
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
    
    # Start indexing for the existing document
    background_tasks.add_task(
        index_document_async,
        existing_document_id,
        None,  # Will extract from file_path
        db
    )
    
    db.refresh(existing_doc)
    return existing_doc


if DEBUG:
    @router.post("/{document_id}/replace-and-index-test", response_model=DocumentSchema)
    async def replace_and_index_test(
        document_id: str,
        background_tasks: BackgroundTasks = BackgroundTasks(),
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: Replace and index without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        # Create a dummy user for testing
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(
                id="test-user-id",
                email="test@example.com",
                name="Test User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        
        return await replace_and_index(document_id, background_tasks, db, test_user)


@router.get("/{document_id}/status", response_model=DocumentSchema)
async def get_document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get document status including indexing progress (shared dashboard - all users can see all documents)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return add_uploader_name_to_document(db, document)


if DEBUG:
    @router.get("/{document_id}/status-test", response_model=DocumentSchema)
    async def get_document_status_test(
        document_id: str,
        db: Session = Depends(get_db)
    ):
        """
        TEST ENDPOINT: Get document status without authentication.
        Only available when DEBUG=true or ENVIRONMENT=development.
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return add_uploader_name_to_document(db, document)


@router.post("/", response_model=DocumentSchema)
async def create_document(
    document: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        summary=document.summary
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
    current_user: User = Depends(get_current_user)
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


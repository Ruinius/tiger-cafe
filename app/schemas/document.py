"""
Document schemas
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.document import DocumentType, ProcessingStatus


class DocumentBase(BaseModel):
    filename: str
    document_type: Optional[DocumentType] = None
    time_period: Optional[str] = None
    summary: Optional[str] = None
    unique_id: Optional[str] = None


class DocumentCreate(DocumentBase):
    company_id: str
    file_path: str


class DocumentUpdate(BaseModel):
    document_type: Optional[DocumentType] = None
    time_period: Optional[str] = None
    summary: Optional[str] = None
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    indexing_status: Optional[ProcessingStatus] = None
    analysis_status: Optional[ProcessingStatus] = None


class Document(DocumentBase):
    id: str
    user_id: str
    company_id: str
    file_path: str
    indexing_status: ProcessingStatus
    analysis_status: ProcessingStatus
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    uploaded_at: datetime
    indexed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    duplicate_detected: Optional[bool] = False
    existing_document_id: Optional[str] = None
    uploader_name: Optional[str] = None  # Name of user who uploaded the document

    class Config:
        from_attributes = True


# Upload and classification response schemas
class ClassificationResult(BaseModel):
    document_type: Optional[DocumentType] = None
    time_period: Optional[str] = None
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    confidence: Optional[str] = None  # "high", "medium", "low"
    extracted_text_preview: Optional[str] = None
    summary: Optional[str] = None  # LLM-generated summary


class DuplicateInfo(BaseModel):
    is_duplicate: bool
    existing_document_id: Optional[str] = None
    existing_document_filename: Optional[str] = None
    existing_document_uploaded_at: Optional[datetime] = None
    existing_document_uploaded_by: Optional[str] = None
    match_reason: Optional[str] = None  # "same_company_type_period", "same_filename", or "same_unique_id"


class DocumentUploadResponse(BaseModel):
    document_id: Optional[str] = None
    classification: ClassificationResult
    duplicate_info: Optional[DuplicateInfo] = None
    requires_confirmation: bool = False
    message: str
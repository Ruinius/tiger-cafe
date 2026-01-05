"""
Document schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentType, ProcessingStatus


class DocumentBase(BaseModel):
    filename: str
    document_type: DocumentType | None = None
    time_period: str | None = None
    summary: str | None = None
    unique_id: str | None = None


class DocumentCreate(DocumentBase):
    company_id: str
    file_path: str


class DocumentUpdate(BaseModel):
    document_type: DocumentType | None = None
    time_period: str | None = None
    summary: str | None = None
    page_count: int | None = None
    character_count: int | None = None
    indexing_status: ProcessingStatus | None = None
    analysis_status: ProcessingStatus | None = None


class Document(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    file_path: str
    indexing_status: ProcessingStatus
    analysis_status: ProcessingStatus
    page_count: int | None = None
    character_count: int | None = None
    uploaded_at: datetime
    indexed_at: datetime | None = None
    processed_at: datetime | None = None
    duplicate_detected: bool | None = False
    existing_document_id: str | None = None
    uploader_name: str | None = None  # Name of user who uploaded the document


# Upload and classification response schemas
class ClassificationResult(BaseModel):
    document_type: DocumentType | None = None
    time_period: str | None = None
    company_name: str | None = None
    ticker: str | None = None
    confidence: str | None = None  # "high", "medium", "low"
    extracted_text_preview: str | None = None
    summary: str | None = None  # LLM-generated summary


class DuplicateInfo(BaseModel):
    is_duplicate: bool
    existing_document_id: str | None = None
    existing_document_filename: str | None = None
    existing_document_uploaded_at: datetime | None = None
    existing_document_uploaded_by: str | None = None
    match_reason: str | None = (
        None  # "same_company_type_period", "same_filename", or "same_unique_id"
    )


class DocumentUploadResponse(BaseModel):
    document_id: str | None = None
    classification: ClassificationResult
    duplicate_info: DuplicateInfo | None = None
    requires_confirmation: bool = False
    message: str

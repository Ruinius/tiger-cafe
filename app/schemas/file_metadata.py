from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    filename: str
    size: int
    quick_hash: str  # Hex string of first 5KB SHA-256


class ExistingDocumentInfo(BaseModel):
    id: str
    uploaded_by: str
    uploaded_at: datetime
    filename: str


class DuplicateCheckResult(BaseModel):
    filename: str
    is_potential_duplicate: bool
    existing_document: ExistingDocumentInfo | None = None

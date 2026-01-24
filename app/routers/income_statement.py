"""
Income statement CRUD routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document, ProcessingStatus
from app.models.income_statement import IncomeStatement
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.income_statement import IncomeStatement as IncomeStatementSchema

router = APIRouter()


@router.get("/{document_id}/income-statement")
async def get_income_statement(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get income statement data for a document.
    Returns three possible states:
    1. Income statement exists - returns income statement data
    2. Processing - returns processing status with milestones
    3. Does not exist and not processing - returns 404
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )

    # State 1: Income statement exists
    if income_statement:
        # Convert to schema for proper serialization
        income_statement_schema = IncomeStatementSchema.model_validate(income_statement)
        return {"status": "exists", "data": income_statement_schema.model_dump()}

    # State 2: Processing
    if document.analysis_status == ProcessingStatus.PROCESSING:
        return {
            "status": "processing",
            "message": "Income statement processing in progress",
            "milestones": {"step": "extracting", "progress": "Processing income statement data..."},
        }

    # State 3: Does not exist and not processing
    raise HTTPException(status_code=404, detail="Income statement not found for this document")

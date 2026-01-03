"""
Company routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.models.document import Document
from app.schemas.company import Company as CompanySchema, CompanyCreate
from app.routers.auth import get_current_user
from sqlalchemy import func
import uuid

router = APIRouter()


@router.get("/", response_model=List[CompanySchema])
async def list_companies(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all companies with document counts"""
    # Query companies with document counts
    companies = db.query(
        Company,
        func.count(Document.id).label('document_count')
    ).outerjoin(
        Document, Company.id == Document.company_id
    ).group_by(Company.id).offset(skip).limit(limit).all()
    
    # Convert to schema format with document counts
    result = []
    for company, doc_count in companies:
        # Filter out placeholder "Processing..." companies that have no documents
        # These are temporary placeholders created during upload
        if company.name == "Processing..." and (doc_count or 0) == 0:
            continue  # Skip placeholder companies with no documents
        
        company_dict = {
            "id": company.id,
            "name": company.name,
            "ticker": company.ticker,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "document_count": doc_count or 0
        }
        result.append(company_dict)
    
    return result


@router.get("/{company_id}", response_model=CompanySchema)
async def get_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific company by ID"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/", response_model=CompanySchema)
async def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new company"""
    db_company = Company(
        id=str(uuid.uuid4()),
        name=company.name,
        ticker=company.ticker
    )
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


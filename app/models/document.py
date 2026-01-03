"""
Document model
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class DocumentType(enum.Enum):
    EARNINGS_ANNOUNCEMENT = "earnings_announcement"
    QUARTERLY_FILING = "quarterly_filing"
    ANNUAL_FILING = "annual_filing"
    PRESS_RELEASE = "press_release"
    ANALYST_REPORT = "analyst_report"
    NEWS_ARTICLE = "news_article"
    OTHER = "other"


class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    CLASSIFYING = "classifying"
    INDEXING = "indexing"
    INDEXED = "indexed"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Document metadata
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Path to stored PDF file
    document_type = Column(Enum(DocumentType), nullable=True)
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    unique_id = Column(String, nullable=True, index=True)  # Unique identifier (URL, article ID, report ID, etc.)
    
    # Processing status
    indexing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)  # Tracks: PENDING → UPLOADING → CLASSIFYING → INDEXING → INDEXED
    analysis_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    duplicate_detected = Column(Boolean, default=False)  # Flag to indicate duplicate was detected
    existing_document_id = Column(String, nullable=True)  # ID of existing document if duplicate
    
    # Document stats
    summary = Column(Text, nullable=True)  # LLM-generated summary from initial upload
    page_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User")
    company = relationship("Company", back_populates="documents")
    balance_sheet = relationship("BalanceSheet", back_populates="document", uselist=False)
    income_statement = relationship("IncomeStatement", back_populates="document", uselist=False)
    historical_calculation = relationship("HistoricalCalculation", back_populates="document", uselist=False)


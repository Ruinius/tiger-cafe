"""
Document model
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.document_status import DocumentStatus


class DocumentType(str, enum.Enum):
    EARNINGS_ANNOUNCEMENT = "earnings_announcement"
    QUARTERLY_FILING = "quarterly_filing"
    ANNUAL_FILING = "annual_filing"
    PRESS_RELEASE = "press_release"
    ANALYST_REPORT = "analyst_report"
    NEWS_ARTICLE = "news_article"
    TRANSCRIPT = "transcript"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    INDEXING = "indexing"
    INDEXED = "indexed"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    # Document metadata
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Path to stored PDF file
    file_size = Column(Integer, nullable=True)  # File size in bytes (for duplicate check)
    document_type = Column(Enum(DocumentType), nullable=True)
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    period_end_date = Column(String, nullable=True)  # e.g., "2024-03-31" (YYYY-MM-DD)
    unique_id = Column(
        String, nullable=True, index=True
    )  # Unique identifier (URL, article ID, report ID, etc.)

    # Processing status (Unified)
    status = Column(
        String, nullable=False, default=DocumentStatus.PENDING, index=True
    )  # Unified status tracking (see DocumentStatus enum)

    # Detailed status tracking
    error_message = Column(Text, nullable=True)  # Failure details
    processing_metadata = Column(Text, nullable=True)  # JSON: {current_step, details}
    current_step = Column(String, nullable=True)  # e.g., "3/7: Indexing"

    # DEPRECATED Fields (Retained for migration/rollback):
    indexing_status = Column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING
    )  # Tracks: PENDING → UPLOADING → CLASSIFYING → INDEXING → INDEXED
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
    historical_calculation = relationship(
        "HistoricalCalculation", back_populates="document", uselist=False
    )
    organic_growth = relationship("OrganicGrowth", back_populates="document", uselist=False)
    amortization = relationship("Amortization", back_populates="document", uselist=False)
    other_assets = relationship("OtherAssets", back_populates="document", uselist=False)
    other_liabilities = relationship("OtherLiabilities", back_populates="document", uselist=False)
    non_operating_classification = relationship(
        "NonOperatingClassification", back_populates="document", uselist=False
    )
    shares_outstanding = relationship("SharesOutstanding", back_populates="document", uselist=False)
    gaap_reconciliation = relationship(
        "GAAPReconciliation", back_populates="document", uselist=False
    )

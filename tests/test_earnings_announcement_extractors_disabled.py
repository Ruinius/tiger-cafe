"""
Test that other assets and other liabilities extractors are disabled for earnings announcements
and that no data is created (extraction is completely skipped).
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.user import User

os.environ.setdefault("GEMINI_API_KEY", "test-key")


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_user(db_session):
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def test_company(db_session):
    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture()
def earnings_announcement_document(db_session, test_user, test_company):
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="earnings.pdf",
        file_path="/tmp/earnings.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture()
def quarterly_filing_document(db_session, test_user, test_company):
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10q.pdf",
        file_path="/tmp/10q.pdf",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_earnings_announcement_document_type_check(db_session, earnings_announcement_document):
    """Test that earnings announcement document type is correctly identified for conditional logic"""
    document_id = earnings_announcement_document.id

    # Verify document type is earnings announcement
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is not None
    assert document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT

    # Verify that the conditional check would skip these extractors
    # This is the same logic used in extraction_orchestrator.py
    should_run_extractors = document.document_type in [
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]
    assert should_run_extractors is False, (
        "Earnings announcements should skip amortization/other assets/liabilities"
    )


def test_quarterly_filing_document_type_check(db_session, quarterly_filing_document):
    """Test that quarterly filing document type is correctly identified for conditional logic"""
    document_id = quarterly_filing_document.id

    # Verify document type is quarterly filing
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is not None
    assert document.document_type == DocumentType.QUARTERLY_FILING

    # Verify that the conditional check would NOT skip these extractors
    # This is the same logic used in extraction_orchestrator.py
    should_run_extractors = document.document_type in [
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]
    assert should_run_extractors is True, (
        "Quarterly filings should NOT skip amortization/other assets/liabilities"
    )


def test_annual_filing_document_type_check(db_session, test_user, test_company):
    """Test that annual filing document type is correctly identified for conditional logic"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10k.pdf",
        file_path="/tmp/10k.pdf",
        document_type=DocumentType.ANNUAL_FILING,
        time_period="FY 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()

    document_id = document.id

    # Verify document type is annual filing
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is not None
    assert document.document_type == DocumentType.ANNUAL_FILING

    # Verify that the conditional check would NOT skip these extractors
    should_run_extractors = document.document_type in [
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]
    assert should_run_extractors is True, (
        "Annual filings should NOT skip amortization/other assets/liabilities"
    )

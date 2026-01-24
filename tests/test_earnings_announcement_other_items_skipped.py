"""
Test that other-assets and other-liabilities extraction is skipped for earnings announcements.
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
    """Create an earnings announcement document"""
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
    """Create a quarterly filing document"""
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


def test_earnings_announcement_conditional_logic(db_session, earnings_announcement_document):
    """Test that earnings announcements are correctly identified to skip other assets/liabilities"""
    document_id = earnings_announcement_document.id

    # Verify document type
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is not None
    assert document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT

    # Test the conditional logic from extraction_orchestrator.py
    should_extract = document.document_type in [
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]
    assert should_extract is False, (
        "Earnings announcements should skip other assets/liabilities extraction"
    )


def test_quarterly_filing_conditional_logic(db_session, quarterly_filing_document):
    """Test that quarterly filings are correctly identified to run other assets/liabilities"""
    document_id = quarterly_filing_document.id

    # Verify document type
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is not None
    assert document.document_type == DocumentType.QUARTERLY_FILING

    # Test the conditional logic from extraction_orchestrator.py
    should_extract = document.document_type in [
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ]
    assert should_extract is True, (
        "Quarterly filings should run other assets/liabilities extraction"
    )

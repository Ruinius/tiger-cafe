"""
Test for document deletion to verify all associated data is properly deleted.
This test ensures that deleting a document also deletes HistoricalCalculation records.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base, get_db
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.historical_calculation import HistoricalCalculation
from app.models.user import User
from app.routers.auth import get_current_user

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from app.main import app


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
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        user = db_session.query(User).filter(User.id == "test-user").first()
        if not user:
            user = User(
                id="test-user", email="test@example.com", first_name="Test", last_name="User"
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_delete_document_permanent_deletes_historical_calculations(client, db_session):
    """
    Test that permanently deleting a document also deletes associated HistoricalCalculation records.
    This test verifies that the NOT NULL constraint on historical_calculations.document_id doesn't cause errors.
    """
    # Create user
    user = db_session.query(User).filter(User.id == "test-user").first()
    if not user:
        user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    # Create company
    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    # Create document
    document_id = str(uuid.uuid4())
    document = Document(
        id=document_id,
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        time_period="Q3 2023",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    # Create historical calculation for the document
    historical_calculation_id = str(uuid.uuid4())
    historical_calculation = HistoricalCalculation(
        id=historical_calculation_id,
        document_id=document_id,
        time_period="Q3 2023",
        currency="USD",
        unit="millions",
        net_working_capital=1000.00,
        invested_capital=5000.00,
    )
    db_session.add(historical_calculation)
    db_session.commit()
    db_session.refresh(historical_calculation)

    # Verify historical calculation exists
    assert (
        db_session.query(HistoricalCalculation).filter_by(document_id=document_id).first()
        is not None
    )

    # Delete the document permanently
    response = client.delete(f"/api/documents/{document_id}/permanent")

    # Verify the request succeeded
    assert response.status_code == 200
    assert response.json()["message"] == "Document and all associated data deleted successfully"

    # Verify document is deleted
    assert db_session.query(Document).filter_by(id=document_id).first() is None

    # Verify historical calculation is also deleted
    assert (
        db_session.query(HistoricalCalculation).filter_by(document_id=document_id).first() is None
    )
    assert (
        db_session.query(HistoricalCalculation).filter_by(id=historical_calculation_id).first()
        is None
    )

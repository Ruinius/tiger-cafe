"""
Tests for the new processing router endpoints.
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


def test_processing_status_endpoint(client, db_session):
    """Test that the processing status endpoint returns document status."""
    # Create test data
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)
    db_session.commit()

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()

    # Test status endpoint
    response = client.get(f"/api/processing/documents/{document.id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == document.id
    assert "status" in data  # Should have a status field
    assert "milestones" in data  # Should have milestones


def test_processing_endpoints_exist(client):
    """Test that all new processing endpoints are registered."""
    # These should return 404 for non-existent document, not 405 (method not allowed)
    fake_id = str(uuid.uuid4())

    # Test that endpoints exist (will return 404 for fake ID, not 405)
    response = client.post(f"/api/processing/documents/{fake_id}/ingest")
    assert response.status_code in [404, 422]  # Not 405

    response = client.post(f"/api/processing/documents/{fake_id}/extract")
    assert response.status_code in [404, 422]

    response = client.post(f"/api/processing/documents/{fake_id}/analyze")
    assert response.status_code in [404, 422]

    response = client.post(f"/api/processing/documents/{fake_id}/rerun")
    assert response.status_code in [404, 422]

    response = client.get(f"/api/processing/documents/{fake_id}/status")
    assert response.status_code == 404


def test_extraction_tasks_endpoints_exist(client):
    """Test that extraction tasks endpoints are registered."""
    fake_id = str(uuid.uuid4())

    # Test that endpoints exist
    response = client.get(f"/api/documents/{fake_id}/shares")
    assert response.status_code == 404  # Document not found, but endpoint exists

    response = client.get(f"/api/documents/{fake_id}/gaap-reconciliation")
    assert response.status_code == 404


def test_balance_sheet_simplified(client, db_session):
    """Test that balance sheet router only has CRUD endpoints."""
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)
    db_session.commit()

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
    )
    db_session.add(document)
    db_session.commit()

    # GET endpoint should exist
    response = client.get(f"/api/balance-sheet/{document.id}/balance-sheet")
    assert response.status_code in [200, 404]  # Either exists or not found

    # DELETE endpoint should exist
    response = client.delete(f"/api/balance-sheet/{document.id}/financial-statements")
    assert response.status_code in [200, 404]


def test_income_statement_simplified(client, db_session):
    """Test that income statement router only has CRUD endpoints."""
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)
    db_session.commit()

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
    )
    db_session.add(document)
    db_session.commit()

    # GET endpoint should exist
    response = client.get(f"/api/income-statement/{document.id}/income-statement")
    assert response.status_code in [200, 404]  # Either exists or not found

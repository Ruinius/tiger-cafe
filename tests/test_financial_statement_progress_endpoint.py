"""
Test for financial-statement-progress endpoint to verify all model imports are correct.
This test ensures that the endpoint can query all required models without NameError.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models  # noqa: F401
from app.models.company import Company
from app.models.document import Document, DocumentType
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
            user = User(id="test-user", email="test@example.com", name="Test User")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_financial_statement_progress_endpoint_handles_all_models(client, db_session):
    """
    Test that the financial-statement-progress endpoint successfully queries all required models
    without raising NameError. This test verifies that all model imports are present in the endpoint.
    """
    user = db_session.query(User).filter(User.id == "test-user").first()
    if not user:
        user = User(id="test-user", email="test@example.com", name="Test User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)
    db_session.commit()

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q1 2024",
    )
    db_session.add(document)
    db_session.commit()

    # Call the endpoint - this should not raise NameError if all imports are correct
    response = client.get(f"/api/documents/{document.id}/financial-statement-progress")

    # The endpoint should return 200 with a valid response structure
    # Even if no financial statements exist, it should return milestones with "not_found" status
    assert response.status_code == 200
    data = response.json()
    
    # Verify the response structure
    assert "status" in data or "milestones" in data
    
    # If milestones are present, verify they have the expected structure
    if "milestones" in data:
        milestones = data["milestones"]
        # Should have milestone entries (even if status is "not_found")
        assert isinstance(milestones, dict)


import io
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.company import Company
from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.user import User
from app.routers.auth import get_current_user

# Ensure DEBUG is True for test endpoint
os.environ["DEBUG"] = "True"

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

    # Create test user
    test_user = User(
        id="test-user-id", email="test@example.com", first_name="Test", last_name="User"
    )
    session.add(test_user)

    # Create test company (required for FK in upload_document_internal)
    test_company = Company(id="test-company-id", name="Test Company", ticker="TEST")
    session.add(test_company)

    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return db_session.query(User).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Mock queue_service to avoid background processing
    monkeypatch.setattr("app.services.queue_service.queue_service.add_document", lambda x: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_upload_batch_success(client, db_session):
    # Prepare multiple dummy PDF files
    file1 = (io.BytesIO(b"%PDF-1.4 dummy content 1"), "test1.pdf")
    file2 = (io.BytesIO(b"%PDF-1.4 dummy content 2"), "test2.pdf")

    files = [
        ("files", (file1[1], file1[0], "application/pdf")),
        ("files", (file2[1], file2[0], "application/pdf")),
    ]

    response = client.post("/api/documents/upload-batch", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "document_ids" in data
    assert len(data["document_ids"]) == 2
    assert "Queued 2 documents" in data["message"]

    # Verify documents were created in DB with correct status
    for doc_id in data["document_ids"]:
        doc = db_session.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None
        assert doc.status == DocumentStatus.PENDING
        assert doc.filename in ["test1.pdf", "test2.pdf"]


def test_upload_batch_test_endpoint(client, db_session):
    # Prepare dummy PDF files
    file1 = (io.BytesIO(b"%PDF-1.4 dummy content test"), "test_anon.pdf")

    files = [
        ("files", (file1[1], file1[0], "application/pdf")),
    ]

    # Use the test endpoint (no auth required, handles test user creation)
    response = client.post("/api/documents/upload-batch", files=files)

    assert response.status_code == 200
    data = response.json()
    assert len(data["document_ids"]) == 1

    doc_id = data["document_ids"][0]
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.status == DocumentStatus.PENDING


def test_upload_batch_invalid_file_type(client):
    # Prepare a non-PDF file
    file1 = (io.BytesIO(b"not a pdf"), "test.txt")

    files = [
        ("files", (file1[1], file1[0], "text/plain")),
    ]

    # The current implementation skips non-PDFs and returns 400 if none valid
    response = client.post("/api/documents/upload-batch", files=files)

    assert response.status_code == 400
    assert "No valid PDF files processed" in response.json()["detail"]

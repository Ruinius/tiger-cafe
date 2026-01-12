import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base, get_db
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


def test_user_flow_company_document_lifecycle(client):
    company_payload = {"name": "Tiger Coffee", "ticker": "TCFE"}
    company_response = client.post("/api/companies", json=company_payload)

    assert company_response.status_code == 200
    company = company_response.json()

    document_payload = {
        "company_id": company["id"],
        "filename": "tiger-cafe-q4.pdf",
        "file_path": "data/uploads/tiger-cafe-q4.pdf",
        "document_type": "annual_filing",
        "time_period": "FY 2023",
        "summary": "Initial upload",
    }
    document_response = client.post("/api/documents", json=document_payload)

    assert document_response.status_code == 200
    document = document_response.json()
    assert document["company_id"] == company["id"]
    assert document["document_type"] == "annual_filing"
    assert document["time_period"] == "FY 2023"

    list_response = client.get("/api/documents")
    assert list_response.status_code == 200
    documents = list_response.json()
    assert len(documents) == 1
    assert documents[0]["id"] == document["id"]
    assert documents[0]["uploader_name"] == "Test User"

    detail_response = client.get(f"/api/documents/{document['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["filename"] == "tiger-cafe-q4.pdf"

    update_payload = {"summary": "Updated summary", "time_period": "FY 2023 (restated)"}
    update_response = client.patch(f"/api/documents/{document['id']}", json=update_payload)

    assert update_response.status_code == 200
    updated_document = update_response.json()
    assert updated_document["summary"] == "Updated summary"
    assert updated_document["time_period"] == "FY 2023 (restated)"

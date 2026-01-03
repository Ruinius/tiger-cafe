import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models  # noqa: F401
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


def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_company_create_list_and_get(client):
    payload = {"name": "Tiger Holdings", "ticker": "TIGR"}
    create_response = client.post("/api/companies", json=payload)

    assert create_response.status_code == 200
    created_company = create_response.json()
    assert created_company["name"] == payload["name"]
    assert created_company["ticker"] == payload["ticker"]

    list_response = client.get("/api/companies")
    assert list_response.status_code == 200
    companies = list_response.json()
    assert len(companies) == 1
    assert companies[0]["id"] == created_company["id"]
    assert companies[0]["document_count"] == 0

    get_response = client.get(f"/api/companies/{created_company['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_company["id"]


def test_company_missing_returns_404(client):
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/companies/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"

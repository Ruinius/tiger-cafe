import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base, get_db
from app.models.company import Company
from app.models.document import Document, DocumentType
from app.models.historical_calculation import HistoricalCalculation
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
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


def test_company_historical_calculations_returns_sorted_entries(client, db_session):
    user = db_session.query(User).filter(User.id == "test-user").first()
    if not user:
        user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    company = Company(id=str(uuid.uuid4()), name="Tiger Holdings", ticker="TIGR")
    db_session.add(company)
    db_session.commit()

    document_q1 = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="q1.pdf",
        file_path="/tmp/q1.pdf",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q1 2024",
    )
    document_fy = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="fy.pdf",
        file_path="/tmp/fy.pdf",
        document_type=DocumentType.ANNUAL_FILING,
        time_period="FY 2023",
    )
    db_session.add_all([document_q1, document_fy])
    db_session.commit()

    income_q1 = IncomeStatement(
        id=str(uuid.uuid4()),
        document_id=document_q1.id,
        time_period="Q1 2024",
        revenue_growth_yoy=Decimal("0.12"),
    )
    income_q1.line_items.append(
        IncomeStatementLineItem(
            id=str(uuid.uuid4()),
            income_statement_id=income_q1.id,
            line_name="Total Net Revenue",
            standardized_name="revenue",  # Add standardized name
            line_value=Decimal("100.00"),
            line_category="Revenue",
            is_operating=True,
            line_order=1,
        )
    )
    income_fy = IncomeStatement(
        id=str(uuid.uuid4()),
        document_id=document_fy.id,
        time_period="FY 2023",
    )
    income_fy.line_items.append(
        IncomeStatementLineItem(
            id=str(uuid.uuid4()),
            income_statement_id=income_fy.id,
            line_name="Net Sales",
            standardized_name="revenue",  # Add standardized name
            line_value=Decimal("250.00"),
            line_category="Revenue",
            is_operating=True,
            line_order=1,
        )
    )
    db_session.add_all([income_q1, income_fy])

    db_session.add_all(
        [
            HistoricalCalculation(
                id=str(uuid.uuid4()),
                document_id=document_q1.id,
                time_period="Q1 2024",
                currency="USD",
                unit="millions",
                calculated_at=datetime(2024, 3, 31, tzinfo=UTC),
                ebita=Decimal("10.00"),
            ),
            HistoricalCalculation(
                id=str(uuid.uuid4()),
                document_id=document_fy.id,
                time_period="FY 2023",
                currency="EUR",
                unit="thousands",
                calculated_at=datetime(2024, 1, 15, tzinfo=UTC),
                ebita=Decimal("25.00"),
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/companies/{company.id}/historical-calculations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == company.id
    assert payload["currency"] == "Multiple"
    assert payload["unit"] == "millions"
    assert [entry["time_period"] for entry in payload["entries"]] == ["FY 2023", "Q1 2024"]
    assert payload["entries"][0]["revenue"] == "0.25"
    assert payload["entries"][1]["revenue"] == "100.0"
    assert payload["entries"][1]["revenue_growth_yoy"] == "0.12"

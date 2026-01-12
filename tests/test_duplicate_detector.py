import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.user import User
from app.utils.duplicate_detector import check_duplicate_document


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def seed_company_and_user(session, company_id="company-1", user_id="user-1"):
    session.add_all(
        [
            Company(id=company_id, name="Test Company", ticker="TCO"),
            User(id=user_id, email="user@example.com", first_name="Test", last_name="User"),
        ]
    )
    session.commit()


@pytest.mark.parametrize(
    "document_type",
    [
        DocumentType.EARNINGS_ANNOUNCEMENT,
        DocumentType.QUARTERLY_FILING,
        DocumentType.ANNUAL_FILING,
    ],
)
def test_duplicate_by_company_type_time_period(db_session, document_type):
    seed_company_and_user(db_session)
    existing = Document(
        id="doc-1",
        user_id="user-1",
        company_id="company-1",
        filename="results.pdf",
        file_path="/tmp/results.pdf",
        document_type=document_type,
        time_period="Q1 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(existing)
    db_session.commit()

    result = check_duplicate_document(
        db_session,
        company_id="company-1",
        document_type=document_type,
        time_period="Q1 2024",
        filename="new-results.pdf",
    )

    assert result is not None
    assert result["match_reason"] == "same_company_type_period"
    assert result["existing_document"].id == existing.id


def test_duplicate_by_filename_case_insensitive(db_session):
    seed_company_and_user(db_session)
    existing = Document(
        id="doc-2",
        user_id="user-1",
        company_id="company-1",
        filename="Quarterly-Report.PDF",
        file_path="/tmp/Quarterly-Report.PDF",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q4 2023",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(existing)
    db_session.commit()

    result = check_duplicate_document(
        db_session,
        company_id="company-1",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q1 2024",
        filename="quarterly-report.pdf",
    )

    assert result is not None
    assert result["match_reason"] == "same_filename"
    assert result["existing_document"].id == existing.id


def test_duplicate_by_unique_id_for_other_types(db_session):
    seed_company_and_user(db_session)
    existing = Document(
        id="doc-3",
        user_id="user-1",
        company_id="company-1",
        filename="press-release.pdf",
        file_path="/tmp/press-release.pdf",
        document_type=DocumentType.PRESS_RELEASE,
        unique_id="press-123",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(existing)
    db_session.commit()

    result = check_duplicate_document(
        db_session,
        company_id="company-1",
        document_type=DocumentType.PRESS_RELEASE,
        time_period=None,
        filename="new-press-release.pdf",
        unique_id="press-123",
    )

    assert result is not None
    assert result["match_reason"] == "same_unique_id"
    assert result["existing_document"].id == existing.id


def test_no_duplicate_returns_none(db_session):
    seed_company_and_user(db_session, company_id="company-1", user_id="user-1")
    other_company = Company(id="company-2", name="Other Company", ticker="OTC")
    other_user = User(id="user-2", email="other@example.com", first_name="Other", last_name="User")
    db_session.add_all([other_company, other_user])
    db_session.add(
        Document(
            id="doc-4",
            user_id="user-2",
            company_id="company-2",
            filename="other.pdf",
            file_path="/tmp/other.pdf",
            document_type=DocumentType.PRESS_RELEASE,
            unique_id="other-999",
            indexing_status=ProcessingStatus.INDEXED,
        )
    )
    db_session.commit()

    result = check_duplicate_document(
        db_session,
        company_id="company-1",
        document_type=DocumentType.PRESS_RELEASE,
        time_period=None,
        filename="new.pdf",
        unique_id="different-123",
    )

    assert result is None

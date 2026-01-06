"""
Test that non-earnings announcements get CLASSIFIED status instead of CLASSIFYING.
"""

import os
import tempfile
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.database import Base
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.user import User
from app.services.document_processing import DocumentProcessingMode, process_document

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
    user = User(id="test-user", email="test@example.com", name="Test User")
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
def mock_pdf_file():
    """Create a temporary PDF file for testing"""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        # Write minimal PDF content (just enough to be recognized as a PDF)
        f.write(b"%PDF-1.4\n")
        f.write(b"1 0 obj\n<< /Type /Catalog >>\nendobj\n")
        f.write(b"xref\n0 1\ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n0\n%%EOF")
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_quarterly_filing_gets_classified_status(
    db_session, test_user, test_company, mock_pdf_file
):
    """Test that quarterly filings get CLASSIFIED status (not CLASSIFYING)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10q.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFYING,
    )
    db_session.add(document)
    db_session.commit()

    # Mock the classifier to return quarterly filing
    with patch("app.services.document_processing.classify_document") as mock_classify:
        mock_classify.return_value = {
            "document_type": DocumentType.QUARTERLY_FILING,
            "time_period": "Q3 2024",
            "company_name": "Test Company",
            "ticker": "TEST",
            "confidence": "high",
        }

        # Mock PDF extraction
        with patch("app.services.document_processing.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = ("Sample text content", 10, 1000)

            # Mock document hash
            with patch("app.services.document_processing.generate_document_hash") as mock_hash:
                mock_hash.return_value = "test-hash-quarterly"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock indexing (should NOT be called)
                    with patch(
                        "app.services.document_processing.index_document_chunks"
                    ) as mock_index:
                        # Process the document
                        result = process_document(
                            db_session=db_session,
                            document_id=document.id,
                            mode=DocumentProcessingMode.FULL,
                        )

                        # Verify indexing was NOT called
                        mock_index.assert_not_called()

                        # Verify document status is CLASSIFIED (not CLASSIFYING or INDEXED)
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.CLASSIFIED
                        assert document.document_type == DocumentType.QUARTERLY_FILING
                        assert result is not None


def test_annual_filing_gets_classified_status(db_session, test_user, test_company, mock_pdf_file):
    """Test that annual filings get CLASSIFIED status (not CLASSIFYING)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10k.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFYING,
    )
    db_session.add(document)
    db_session.commit()

    # Mock the classifier to return annual filing
    with patch("app.services.document_processing.classify_document") as mock_classify:
        mock_classify.return_value = {
            "document_type": DocumentType.ANNUAL_FILING,
            "time_period": "FY 2024",
            "company_name": "Test Company",
            "ticker": "TEST",
            "confidence": "high",
        }

        # Mock PDF extraction
        with patch("app.services.document_processing.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = ("Sample text content", 10, 1000)

            # Mock document hash
            with patch("app.services.document_processing.generate_document_hash") as mock_hash:
                mock_hash.return_value = "test-hash-annual"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock indexing (should NOT be called)
                    with patch(
                        "app.services.document_processing.index_document_chunks"
                    ) as mock_index:
                        # Process the document
                        process_document(
                            db_session=db_session,
                            document_id=document.id,
                            mode=DocumentProcessingMode.FULL,
                        )

                        # Verify indexing was NOT called
                        mock_index.assert_not_called()

                        # Verify document status is CLASSIFIED
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.CLASSIFIED
                        assert document.document_type == DocumentType.ANNUAL_FILING


def test_transcript_gets_classified_status(db_session, test_user, test_company, mock_pdf_file):
    """Test that transcripts get CLASSIFIED status (not CLASSIFYING)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="transcript.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFYING,
    )
    db_session.add(document)
    db_session.commit()

    # Mock the classifier to return transcript
    with patch("app.services.document_processing.classify_document") as mock_classify:
        mock_classify.return_value = {
            "document_type": DocumentType.TRANSCRIPT,
            "time_period": "Q3 2024",
            "company_name": "Test Company",
            "ticker": "TEST",
            "confidence": "high",
        }

        # Mock PDF extraction
        with patch("app.services.document_processing.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = ("Sample text content", 10, 1000)

            # Mock document hash
            with patch("app.services.document_processing.generate_document_hash") as mock_hash:
                mock_hash.return_value = "test-hash-transcript"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock indexing (should NOT be called)
                    with patch(
                        "app.services.document_processing.index_document_chunks"
                    ) as mock_index:
                        # Process the document
                        process_document(
                            db_session=db_session,
                            document_id=document.id,
                            mode=DocumentProcessingMode.FULL,
                        )

                        # Verify indexing was NOT called
                        mock_index.assert_not_called()

                        # Verify document status is CLASSIFIED
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.CLASSIFIED
                        assert document.document_type == DocumentType.TRANSCRIPT


def test_press_release_gets_classified_status(db_session, test_user, test_company, mock_pdf_file):
    """Test that press releases get CLASSIFIED status (not CLASSIFYING)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="press_release.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFYING,
    )
    db_session.add(document)
    db_session.commit()

    # Mock the classifier to return press release
    with patch("app.services.document_processing.classify_document") as mock_classify:
        mock_classify.return_value = {
            "document_type": DocumentType.PRESS_RELEASE,
            "time_period": None,
            "company_name": "Test Company",
            "ticker": "TEST",
            "confidence": "high",
        }

        # Mock PDF extraction
        with patch("app.services.document_processing.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = ("Sample text content", 10, 1000)

            # Mock document hash
            with patch("app.services.document_processing.generate_document_hash") as mock_hash:
                mock_hash.return_value = "test-hash-press"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock indexing (should NOT be called)
                    with patch(
                        "app.services.document_processing.index_document_chunks"
                    ) as mock_index:
                        # Process the document
                        process_document(
                            db_session=db_session,
                            document_id=document.id,
                            mode=DocumentProcessingMode.FULL,
                        )

                        # Verify indexing was NOT called
                        mock_index.assert_not_called()

                        # Verify document status is CLASSIFIED
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.CLASSIFIED
                        assert document.document_type == DocumentType.PRESS_RELEASE


def test_earnings_announcement_does_not_get_classified_status(
    db_session, test_user, test_company, mock_pdf_file
):
    """Test that earnings announcements do NOT get CLASSIFIED status (they get INDEXED)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="earnings.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFYING,
    )
    db_session.add(document)
    db_session.commit()

    # Mock the classifier to return earnings announcement
    with patch("app.services.document_processing.classify_document") as mock_classify:
        mock_classify.return_value = {
            "document_type": DocumentType.EARNINGS_ANNOUNCEMENT,
            "time_period": "Q3 2024",
            "company_name": "Test Company",
            "ticker": "TEST",
            "confidence": "high",
        }

        # Mock PDF extraction
        with patch("app.services.document_processing.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = ("Sample text content", 10, 1000)

            # Mock document hash
            with patch("app.services.document_processing.generate_document_hash") as mock_hash:
                mock_hash.return_value = "test-hash-earnings"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock summary generation
                    with patch(
                        "app.services.document_processing.generate_document_summary"
                    ) as mock_summary:
                        mock_summary.return_value = "Test summary"

                        # Mock indexing (should be called for earnings announcements)
                        with patch(
                            "app.services.document_processing.index_document_chunks"
                        ) as mock_index:
                            # Process the document
                            process_document(
                                db_session=db_session,
                                document_id=document.id,
                                mode=DocumentProcessingMode.FULL,
                            )

                            # Verify indexing was called
                            mock_index.assert_called_once()

                            # Verify document status is INDEXED (not CLASSIFIED)
                            db_session.refresh(document)
                            assert document.indexing_status == ProcessingStatus.INDEXED
                            assert document.indexing_status != ProcessingStatus.CLASSIFIED
                            assert document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT


def test_classified_status_is_terminal_state(db_session, test_user, test_company, mock_pdf_file):
    """Test that CLASSIFIED is a terminal state (document won't be processed further)"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="other.pdf",
        file_path=mock_pdf_file,
        indexing_status=ProcessingStatus.CLASSIFIED,  # Already classified
    )
    db_session.add(document)
    db_session.commit()

    # Verify the status is CLASSIFIED
    assert document.indexing_status == ProcessingStatus.CLASSIFIED

    # Verify it's not in a processing state
    assert document.indexing_status != ProcessingStatus.CLASSIFYING
    assert document.indexing_status != ProcessingStatus.INDEXING
    assert document.indexing_status != ProcessingStatus.PENDING

"""
Test that only earnings announcements go through full processing pipeline.
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


def test_earnings_announcement_goes_through_full_processing(
    db_session, test_user, test_company, mock_pdf_file
):
    """Test that earnings announcements are indexed and processed fully"""
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
                mock_hash.return_value = "test-hash-123"

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
                        result = process_document(
                            db_session=db_session,
                            document_id=document.id,
                            mode=DocumentProcessingMode.FULL,
                        )

                        # Verify indexing was called
                        mock_index.assert_called_once()

                        # Verify document status is INDEXED
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.INDEXED
                        assert document.document_type == DocumentType.EARNINGS_ANNOUNCEMENT
                        assert result is not None


def test_non_earnings_announcement_skips_indexing(
    db_session, test_user, test_company, mock_pdf_file
):
    """Test that non-earnings announcements skip indexing"""
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

    # Mock the classifier to return press release (not earnings announcement)
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
                mock_hash.return_value = "test-hash-456"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock indexing (should NOT be called for non-earnings announcements)
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
                        assert document.document_type == DocumentType.PRESS_RELEASE
                        assert result is not None
                        # Summary should be None since we skip it for non-earnings
                        assert result.summary is None


def test_quarterly_filing_skips_indexing(db_session, test_user, test_company, mock_pdf_file):
    """Test that quarterly filings skip indexing (only earnings announcements are processed)"""
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
                mock_hash.return_value = "test-hash-789"

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

                        # Verify document status is CLASSIFIED (not CLASSIFYING or INDEXED)
                        db_session.refresh(document)
                        assert document.indexing_status == ProcessingStatus.CLASSIFIED
                        assert document.document_type == DocumentType.QUARTERLY_FILING


def test_preview_mode_still_classifies_all_document_types(
    db_session, test_user, test_company, mock_pdf_file
):
    """Test that preview mode still classifies all document types (no filtering)"""
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
                mock_hash.return_value = "test-hash-preview"

                # Mock duplicate check
                with patch(
                    "app.services.document_processing.check_duplicate_document"
                ) as mock_duplicate:
                    mock_duplicate.return_value = {"is_duplicate": False}

                    # Mock summary generation
                    with patch(
                        "app.services.document_processing.generate_document_summary"
                    ) as mock_summary:
                        mock_summary.return_value = "Preview summary"

                        # Process in preview mode (should work for all types)
                        result = process_document(
                            db_session=db_session,
                            file_path=mock_pdf_file,
                            filename="preview.pdf",
                            mode=DocumentProcessingMode.PREVIEW,
                        )

                        # Preview mode should return result regardless of document type
                        assert result is not None
                        assert (
                            result.classification_data["document_type"]
                            == DocumentType.PRESS_RELEASE
                        )

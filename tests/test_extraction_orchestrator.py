"""
Tests for the extraction orchestrator service layer.

This test suite ensures that the service layer properly orchestrates
the extraction workflow and handles errors correctly.
"""

import os
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
from app.services.extraction_orchestrator import (
    extract_balance_sheet_task,
    extract_income_statement_task,
    run_full_extraction_pipeline,
    run_ingestion_pipeline,
)

os.environ.setdefault("GEMINI_API_KEY", "test-key")


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database for testing."""
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
def test_document(db_session):
    """Create a test document."""
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        indexing_status=ProcessingStatus.INDEXED,
        time_period="Q4 2024",
        period_end_date="2024-12-31",
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return document


@pytest.mark.asyncio
async def test_extract_balance_sheet_task_success(db_session, test_document):
    """Test successful balance sheet extraction."""
    mock_bs_data = {
        "line_items": [{"line_name": "Cash", "line_value": 1000, "standardized_name": "cash"}],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    with patch("agents.balance_sheet_extractor.extract_balance_sheet", return_value=mock_bs_data):
        await extract_balance_sheet_task(test_document.id, db_session)

    # Verify balance sheet was created
    from app.models.balance_sheet import BalanceSheet

    bs = db_session.query(BalanceSheet).filter(BalanceSheet.document_id == test_document.id).first()

    assert bs is not None
    assert bs.currency == "USD"
    assert bs.unit == "millions"
    assert bs.is_valid is True


@pytest.mark.asyncio
async def test_extract_balance_sheet_task_skips_ineligible_types(db_session, test_document):
    """Test that balance sheet extraction is skipped for ineligible document types."""
    # Change document type to press release
    test_document.document_type = DocumentType.PRESS_RELEASE
    db_session.commit()

    with patch("agents.balance_sheet_extractor.extract_balance_sheet") as mock_extract:
        await extract_balance_sheet_task(test_document.id, db_session)

    # Verify extraction was not called
    mock_extract.assert_not_called()

    # Verify no balance sheet was created
    from app.models.balance_sheet import BalanceSheet

    bs = db_session.query(BalanceSheet).filter(BalanceSheet.document_id == test_document.id).first()

    assert bs is None


@pytest.mark.asyncio
async def test_extract_income_statement_task_success(db_session, test_document):
    """Test successful income statement extraction."""
    mock_is_data = {
        "line_items": [
            {"line_name": "Revenue", "line_value": 5000, "standardized_name": "total_revenue"}
        ],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    with patch(
        "agents.income_statement_extractor.extract_income_statement", return_value=mock_is_data
    ):
        await extract_income_statement_task(test_document.id, db_session)

    # Verify income statement was created
    from app.models.income_statement import IncomeStatement

    income_stmt = (
        db_session.query(IncomeStatement)
        .filter(IncomeStatement.document_id == test_document.id)
        .first()
    )

    assert income_stmt is not None
    assert income_stmt.currency == "USD"
    assert income_stmt.unit == "millions"
    assert income_stmt.is_valid is True


@pytest.mark.asyncio
async def test_extract_balance_sheet_task_handles_errors(db_session, test_document):
    """Test that balance sheet extraction handles errors gracefully."""
    with patch(
        "agents.balance_sheet_extractor.extract_balance_sheet",
        side_effect=Exception("Extraction failed"),
    ):
        with pytest.raises(Exception, match="Extraction failed"):
            await extract_balance_sheet_task(test_document.id, db_session)

    # Verify no balance sheet was created
    from app.models.balance_sheet import BalanceSheet

    bs = db_session.query(BalanceSheet).filter(BalanceSheet.document_id == test_document.id).first()

    assert bs is None


@pytest.mark.asyncio
async def test_run_ingestion_pipeline(db_session, test_document):
    """Test the ingestion pipeline orchestration."""
    # Mock the process_document function
    with patch("app.services.extraction_orchestrator.process_document") as mock_process:
        mock_process.return_value = None

        await run_ingestion_pipeline(test_document.id, db_session)

        # Verify process_document was called with correct mode
        from app.services.document_processing import DocumentProcessingMode

        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[1]["document_id"] == test_document.id
        assert call_args[1]["mode"] == DocumentProcessingMode.FULL


@pytest.mark.asyncio
async def test_run_full_extraction_pipeline_orchestration(db_session, test_document):
    """Test that the full extraction pipeline calls all extraction tasks."""
    mock_bs_data = {
        "line_items": [
            {"line_name": "Cash", "line_value": 1000, "standardized_name": "cash", "line_order": 1}
        ],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    mock_is_data = {
        "line_items": [
            {
                "line_name": "Revenue",
                "line_value": 5000,
                "standardized_name": "revenue",
                "line_order": 1,
            }
        ],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    with (
        patch("agents.balance_sheet_extractor.extract_balance_sheet", return_value=mock_bs_data),
        patch(
            "agents.income_statement_extractor.extract_income_statement", return_value=mock_is_data
        ),
        patch("agents.shares_outstanding_extractor.extract_shares_outstanding", return_value={}),
        patch("agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch("agents.non_operating_classifier.classify_non_operating_items", return_value={}),
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    # Verify both balance sheet and income statement were created
    from app.models.balance_sheet import BalanceSheet
    from app.models.income_statement import IncomeStatement

    bs = db_session.query(BalanceSheet).filter(BalanceSheet.document_id == test_document.id).first()

    income_stmt = (
        db_session.query(IncomeStatement)
        .filter(IncomeStatement.document_id == test_document.id)
        .first()
    )

    assert bs is not None
    assert income_stmt is not None


@pytest.mark.asyncio
async def test_extraction_pipeline_updates_document_status(db_session, test_document):
    """Test that the extraction pipeline updates document status correctly."""
    mock_data = {
        "line_items": [
            {"line_name": "Cash", "line_value": 1000, "standardized_name": "cash", "line_order": 1}
        ],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    with (
        patch("agents.balance_sheet_extractor.extract_balance_sheet", return_value=mock_data),
        patch("agents.income_statement_extractor.extract_income_statement", return_value=mock_data),
        patch("agents.shares_outstanding_extractor.extract_shares_outstanding", return_value={}),
        patch("agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch("agents.non_operating_classifier.classify_non_operating_items", return_value={}),
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    # Refresh document from database
    db_session.refresh(test_document)

    # Verify analysis status was updated
    assert test_document.analysis_status == ProcessingStatus.PROCESSED


@pytest.mark.asyncio
async def test_extraction_task_deletes_existing_data(db_session, test_document):
    """Test that extraction tasks delete existing data before re-extracting."""
    # Create existing balance sheet
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem

    existing_bs = BalanceSheet(
        id=str(uuid.uuid4()), document_id=test_document.id, currency="EUR", unit="thousands"
    )
    db_session.add(existing_bs)
    db_session.commit()

    existing_item = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=existing_bs.id,
        line_name="Old Cash",
        line_value=500,
        line_order=1,
    )

    db_session.add(existing_item)
    db_session.add(existing_item)
    db_session.commit()

    existing_item_id = existing_item.id

    # Run extraction

    mock_bs_data = {
        "line_items": [{"line_name": "New Cash", "line_value": 1000, "standardized_name": "cash"}],
        "is_valid": True,
        "validation_errors": [],
        "currency": "USD",
        "unit": "millions",
    }

    with patch("agents.balance_sheet_extractor.extract_balance_sheet", return_value=mock_bs_data):
        await extract_balance_sheet_task(test_document.id, db_session)

    # Verify old data was deleted and new data was created
    bs = db_session.query(BalanceSheet).filter(BalanceSheet.document_id == test_document.id).first()

    assert bs is not None
    assert bs.id != existing_bs.id  # New balance sheet created
    assert bs.currency == "USD"  # New data

    # Verify old line item was deleted
    old_item = (
        db_session.query(BalanceSheetLineItem)
        .filter(BalanceSheetLineItem.id == existing_item_id)
        .first()
    )

    assert old_item is None

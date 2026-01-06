"""
Test that other-assets and other-liabilities extraction is skipped for earnings announcements.
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
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.income_statement import IncomeStatement
from app.models.other_assets import OtherAssets
from app.models.other_liabilities import OtherLiabilities
from app.models.user import User
from app.routers.income_statement import process_income_statement_async

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


@pytest.fixture()
def earnings_announcement_document(db_session, test_user, test_company, mock_pdf_file):
    """Create an earnings announcement document with balance sheet and income statement"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="earnings.pdf",
        file_path=mock_pdf_file,
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()

    # Create balance sheet
    balance_sheet = BalanceSheet(
        id=str(uuid.uuid4()),
        document_id=document.id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(balance_sheet)
    db_session.commit()
    db_session.refresh(balance_sheet)

    # Add balance sheet line items including "Other Current Assets" and "Other Non-Current Assets"
    other_current_assets = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Current Assets (Other current assets, net)",
        line_value=100.0,
        line_order=5,
    )
    other_non_current_assets = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Non-Current Assets (Other non-current assets)",
        line_value=200.0,
        line_order=10,
    )
    other_current_liabilities = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Current Liabilities (Other current liabilities)",
        line_value=50.0,
        line_order=15,
    )
    other_non_current_liabilities = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Non-Current Liabilities (Other non-current liabilities)",
        line_value=75.0,
        line_order=20,
    )
    db_session.add(other_current_assets)
    db_session.add(other_non_current_assets)
    db_session.add(other_current_liabilities)
    db_session.add(other_non_current_liabilities)
    db_session.commit()

    # Create income statement
    income_statement = IncomeStatement(
        id=str(uuid.uuid4()),
        document_id=document.id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(income_statement)
    db_session.commit()

    return document


@pytest.fixture()
def quarterly_filing_document(db_session, test_user, test_company, mock_pdf_file):
    """Create a quarterly filing document with balance sheet and income statement"""
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10q.pdf",
        file_path=mock_pdf_file,
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    # Create balance sheet
    balance_sheet = BalanceSheet(
        id=str(uuid.uuid4()),
        document_id=document.id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(balance_sheet)
    db_session.commit()
    db_session.refresh(balance_sheet)

    # Add balance sheet line items with standardized names
    other_current_assets = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Current Assets (Other current assets, net)",
        line_value=100.0,
        line_order=5,
    )
    other_non_current_assets = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Non-Current Assets (Other non-current assets)",
        line_value=200.0,
        line_order=10,
    )
    other_current_liabilities = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Current Liabilities (Other current liabilities)",
        line_value=50.0,
        line_order=15,
    )
    other_non_current_liabilities = BalanceSheetLineItem(
        id=str(uuid.uuid4()),
        balance_sheet_id=balance_sheet.id,
        line_name="Other Non-Current Liabilities (Other non-current liabilities)",
        line_value=75.0,
        line_order=20,
    )
    db_session.add(other_current_assets)
    db_session.add(other_non_current_assets)
    db_session.add(other_current_liabilities)
    db_session.add(other_non_current_liabilities)
    db_session.commit()

    # Create income statement
    income_statement = IncomeStatement(
        id=str(uuid.uuid4()),
        document_id=document.id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(income_statement)
    db_session.commit()

    return document


def test_earnings_announcement_skips_other_assets_extraction(
    db_session, earnings_announcement_document
):
    """Test that earnings announcements skip other-assets extraction"""
    document_id = earnings_announcement_document.id

    # Patch SessionLocal to return our test session
    # SessionLocal is a sessionmaker, so we need to make it return a callable that returns the session
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value = db_session
        # Mock the extractors
        with patch(
            "app.routers.income_statement.extract_other_assets"
        ) as mock_extract_other_assets:
            with patch(
                "app.routers.income_statement.extract_other_liabilities"
            ) as mock_extract_other_liabilities:
                with patch("app.routers.income_statement.extract_income_statement") as mock_income:
                    mock_income.return_value = {
                        "line_items": [
                            {
                                "line_name": "Revenue",
                                "line_value": 1000.0,
                                "line_category": "Revenue",
                                "is_operating": True,
                            }
                        ],
                        "time_period": "Q3 2024",
                        "currency": "USD",
                        "unit": "millions",
                        "is_valid": True,
                    }
                    with patch(
                        "app.routers.income_statement.extract_organic_growth"
                    ) as mock_organic_growth:
                        mock_organic_growth.return_value = {
                            "is_valid": True,
                            "acquisition_revenue_impact": 0,
                            "organic_revenue_growth": 5.0,
                        }
                        with patch(
                            "app.routers.income_statement.extract_shares_outstanding"
                        ) as mock_shares:
                            mock_shares.return_value = {
                                "is_valid": True,
                                "basic_shares_outstanding": 1000000,
                                "diluted_shares_outstanding": 1100000,
                            }
                            with patch(
                                "app.routers.income_statement.extract_gaap_reconciliation"
                            ) as mock_gaap:
                                mock_gaap.return_value = {
                                    "is_valid": True,
                                    "line_items": [],
                                }
                                with patch(
                                    "app.routers.income_statement.classify_non_operating_items"
                                ) as mock_classify:
                                    mock_classify.return_value = {
                                        "is_valid": True,
                                        "items": [],
                                    }
                                    with patch(
                                        "app.routers.income_statement.calculate_and_save_historical_calculations"
                                    ):
                                        # Process income statement
                                        process_income_statement_async(document_id, db_session)

                                        # Verify other-assets extractor was NOT called
                                        mock_extract_other_assets.assert_not_called()

                                        # Verify other-liabilities extractor was NOT called
                                        mock_extract_other_liabilities.assert_not_called()

    # Verify no other-assets data was created
    other_assets = (
        db_session.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    )
    assert other_assets is None

    # Verify no other-liabilities data was created
    other_liabilities = (
        db_session.query(OtherLiabilities)
        .filter(OtherLiabilities.document_id == document_id)
        .first()
    )
    assert other_liabilities is None


def test_quarterly_filing_extracts_other_assets_and_liabilities(
    db_session, quarterly_filing_document
):
    """Test that quarterly filings DO extract other-assets and other-liabilities"""
    document_id = quarterly_filing_document.id

    # Patch SessionLocal to return our test session
    # SessionLocal is a sessionmaker, so we need to make it return a callable that returns the session
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value = db_session
        # Mock the extractors
        with patch(
            "app.routers.income_statement.extract_other_assets"
        ) as mock_extract_other_assets:
            with patch(
                "app.routers.income_statement.extract_other_liabilities"
            ) as mock_extract_other_liabilities:
                with patch("app.routers.income_statement.extract_income_statement") as mock_income:
                    mock_income.return_value = {
                        "line_items": [
                            {
                                "line_name": "Revenue",
                                "line_value": 1000.0,
                                "line_category": "Revenue",
                                "is_operating": True,
                            }
                        ],
                        "time_period": "Q3 2024",
                        "currency": "USD",
                        "unit": "millions",
                        "is_valid": True,
                    }
                    with patch(
                        "app.routers.income_statement.extract_organic_growth"
                    ) as mock_organic_growth:
                        mock_organic_growth.return_value = {
                            "is_valid": True,
                            "acquisition_revenue_impact": 0,
                            "organic_revenue_growth": 5.0,
                        }
                        with patch(
                            "app.routers.income_statement.extract_shares_outstanding"
                        ) as mock_shares:
                            mock_shares.return_value = {
                                "is_valid": True,
                                "basic_shares_outstanding": 1000000,
                                "diluted_shares_outstanding": 1100000,
                            }
                            with patch(
                                "app.routers.income_statement.extract_amortization"
                            ) as mock_amortization:
                                mock_amortization.return_value = {
                                    "is_valid": True,
                                    "line_items": [],
                                }
                                mock_extract_other_assets.return_value = {
                                    "is_valid": True,
                                    "line_items": [
                                        {
                                            "line_name": "Prepaid Expenses",
                                            "line_value": 50.0,
                                            "unit": "millions",
                                            "is_operating": True,
                                            "category": "Current Assets",
                                        }
                                    ],
                                }
                                mock_extract_other_liabilities.return_value = {
                                    "is_valid": True,
                                    "line_items": [
                                        {
                                            "line_name": "Accrued Expenses",
                                            "line_value": 25.0,
                                            "unit": "millions",
                                            "is_operating": True,
                                            "category": "Current Liabilities",
                                        }
                                    ],
                                }
                                with patch(
                                    "app.routers.income_statement.classify_non_operating_items"
                                ) as mock_classify:
                                    mock_classify.return_value = {
                                        "is_valid": True,
                                        "items": [],
                                    }
                                    with patch(
                                        "app.routers.income_statement.calculate_and_save_historical_calculations"
                                    ):
                                        # Process income statement
                                        process_income_statement_async(document_id, db_session)

                                        # Verify other-assets extractor WAS called
                                        mock_extract_other_assets.assert_called_once()

                                        # Verify other-liabilities extractor WAS called
                                        mock_extract_other_liabilities.assert_called_once()

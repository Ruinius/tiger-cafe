"""
Test that other assets and other liabilities extractors are disabled for earnings announcements
and that no data is created (extraction is completely skipped).
"""

import os
import uuid
from decimal import Decimal
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
def earnings_announcement_document(db_session, test_user, test_company):
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="earnings.pdf",
        file_path="/tmp/earnings.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture()
def quarterly_filing_document(db_session, test_user, test_company):
    document = Document(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        company_id=test_company.id,
        filename="10q.pdf",
        file_path="/tmp/10q.pdf",
        document_type=DocumentType.QUARTERLY_FILING,
        time_period="Q3 2024",
        indexing_status=ProcessingStatus.INDEXED,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture()
def balance_sheet_with_other_items(db_session, earnings_announcement_document):
    balance_sheet = BalanceSheet(
        id=str(uuid.uuid4()),
        document_id=earnings_announcement_document.id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(balance_sheet)
    db_session.commit()
    db_session.refresh(balance_sheet)

    # Add line items including other assets and liabilities
    line_items = [
        BalanceSheetLineItem(
            id=str(uuid.uuid4()),
            balance_sheet_id=balance_sheet.id,
            line_name="Other Current Assets",
            line_value=Decimal("100.00"),
            line_category="Current Assets",
            is_operating=None,
            line_order=1,
        ),
        BalanceSheetLineItem(
            id=str(uuid.uuid4()),
            balance_sheet_id=balance_sheet.id,
            line_name="Other Non-Current Assets",
            line_value=Decimal("200.00"),
            line_category="Non-Current Assets",
            is_operating=None,
            line_order=2,
        ),
        BalanceSheetLineItem(
            id=str(uuid.uuid4()),
            balance_sheet_id=balance_sheet.id,
            line_name="Other Current Liabilities",
            line_value=Decimal("50.00"),
            line_category="Current Liabilities",
            is_operating=None,
            line_order=3,
        ),
        BalanceSheetLineItem(
            id=str(uuid.uuid4()),
            balance_sheet_id=balance_sheet.id,
            line_name="Other Non-Current Liabilities",
            line_value=Decimal("75.00"),
            line_category="Non-Current Liabilities",
            is_operating=None,
            line_order=4,
        ),
    ]
    for item in line_items:
        db_session.add(item)
    db_session.commit()
    return balance_sheet


def test_earnings_announcement_skips_extractors_and_creates_no_data(
    db_session, earnings_announcement_document, balance_sheet_with_other_items
):
    """Test that for earnings announcements, extractors are not called and no data is created"""
    # Store document_id before context ends to avoid DetachedInstanceError
    document_id = earnings_announcement_document.id

    # Patch SessionLocal to return our test session
    # SessionLocal is a sessionmaker, so we need to make it return a callable that returns the session
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value = db_session

        # Mock the extractor functions to verify they're not called
        with patch("app.routers.income_statement.extract_other_assets") as mock_other_assets:
            with patch(
                "app.routers.income_statement.extract_other_liabilities"
            ) as mock_other_liabilities:
                # Mock other dependencies that are needed
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
                with patch("app.routers.income_statement.extract_organic_growth"):
                    with patch("app.routers.income_statement.extract_gaap_reconciliation"):
                        with patch("app.routers.income_statement.classify_non_operating_items"):
                            with patch(
                                "app.routers.income_statement.calculate_and_save_historical_calculations"
                            ):
                                with patch(
                                    "app.routers.income_statement.extract_shares_outstanding"
                                ) as mock_shares:
                                    mock_shares.return_value = {
                                        "is_valid": True,
                                        "basic_shares_outstanding": 1000000,
                                        "basic_shares_outstanding_unit": "shares",
                                        "diluted_shares_outstanding": 1100000,
                                        "diluted_shares_outstanding_unit": "shares",
                                    }
                                    # Process income statement
                                    process_income_statement_async(document_id, db_session)

                                    # Verify extractors were NOT called
                                    mock_other_assets.assert_not_called()
                                    mock_other_liabilities.assert_not_called()

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


def test_quarterly_filing_uses_extractors(
    db_session, quarterly_filing_document, balance_sheet_with_other_items
):
    """Test that for non-earnings announcements, extractors are still called"""
    # Update balance sheet to belong to quarterly filing
    balance_sheet_with_other_items.document_id = quarterly_filing_document.id
    db_session.commit()

    # Store document_id before context ends
    document_id = quarterly_filing_document.id

    # Patch SessionLocal to return our test session
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value = db_session

        # Mock the extractor functions to verify they ARE called
        with patch("app.routers.income_statement.extract_other_assets") as mock_other_assets:
            mock_other_assets.return_value = {
                "line_items": [
                    {
                        "line_name": "Prepaid Expenses",
                        "line_value": 100.0,
                        "unit": "millions",
                        "category": "Current Assets",
                        "is_operating": True,
                    }
                ],
                "chunk_index": 5,
                "is_valid": True,
                "validation_errors": [],
            }
            with patch(
                "app.routers.income_statement.extract_other_liabilities"
            ) as mock_other_liabilities:
                mock_other_liabilities.return_value = {
                    "line_items": [
                        {
                            "line_name": "Accrued Expenses",
                            "line_value": 50.0,
                            "unit": "millions",
                            "category": "Current Liabilities",
                            "is_operating": False,
                        }
                    ],
                    "chunk_index": 6,
                    "is_valid": True,
                    "validation_errors": [],
                }
                # Mock other dependencies
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
                    with patch("app.routers.income_statement.extract_organic_growth"):
                        with patch("app.routers.income_statement.extract_amortization"):
                            with patch(
                                "app.routers.income_statement.extract_shares_outstanding"
                            ) as mock_shares:
                                mock_shares.return_value = {
                                    "is_valid": True,
                                    "basic_shares_outstanding": 1000000,
                                    "basic_shares_outstanding_unit": "shares",
                                    "diluted_shares_outstanding": 1100000,
                                    "diluted_shares_outstanding_unit": "shares",
                                }
                                with patch(
                                    "app.routers.income_statement.classify_non_operating_items"
                                ):
                                    with patch(
                                        "app.routers.income_statement.calculate_and_save_historical_calculations"
                                    ):
                                        # Process income statement
                                        process_income_statement_async(document_id, db_session)

                                        # Verify extractors WERE called
                                        mock_other_assets.assert_called_once()
                                        mock_other_liabilities.assert_called_once()


def test_earnings_announcement_no_data_with_zero_values(db_session, earnings_announcement_document):
    """Test that no other-assets/liabilities data is created when balance sheet values are zero or missing"""
    # Store document_id before context ends
    document_id = earnings_announcement_document.id

    # Create balance sheet without other assets/liabilities
    balance_sheet = BalanceSheet(
        id=str(uuid.uuid4()),
        document_id=document_id,
        time_period="Q3 2024",
        currency="USD",
        unit="millions",
        is_valid=True,
    )
    db_session.add(balance_sheet)
    db_session.commit()

    # Patch SessionLocal to return our test session
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value = db_session

        # Mock dependencies
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
            with patch("app.routers.income_statement.extract_organic_growth"):
                with patch("app.routers.income_statement.extract_gaap_reconciliation"):
                    with patch("app.routers.income_statement.classify_non_operating_items"):
                        with patch(
                            "app.routers.income_statement.calculate_and_save_historical_calculations"
                        ):
                            with patch(
                                "app.routers.income_statement.extract_shares_outstanding"
                            ) as mock_shares:
                                mock_shares.return_value = {
                                    "is_valid": True,
                                    "basic_shares_outstanding": 1000000,
                                    "basic_shares_outstanding_unit": "shares",
                                    "diluted_shares_outstanding": 1100000,
                                    "diluted_shares_outstanding_unit": "shares",
                                }
                                process_income_statement_async(document_id, db_session)

    # Verify no other assets/liabilities were created (query fresh from database)
    other_assets = (
        db_session.query(OtherAssets).filter(OtherAssets.document_id == document_id).first()
    )
    assert other_assets is None

    other_liabilities = (
        db_session.query(OtherLiabilities)
        .filter(OtherLiabilities.document_id == document_id)
        .first()
    )
    assert other_liabilities is None

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_status import DocumentStatus
from app.models.user import User
from app.services.extraction_orchestrator import (
    run_full_extraction_pipeline,
    run_ingestion_pipeline,
)
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    MilestoneStatus,
    get_progress,
)


@pytest.fixture
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


@pytest.fixture
def test_document(db_session):
    user = User(id="test-user", email="test@example.com", first_name="Test", last_name="User")
    db_session.add(user)

    company = Company(id=str(uuid.uuid4()), name="Test Company", ticker="TEST")
    db_session.add(company)

    document = Document(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=company.id,
        filename="failure_test.pdf",
        file_path="/tmp/failure_test.pdf",
        document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
        indexing_status=ProcessingStatus.PENDING,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.mark.asyncio
async def test_ingestion_pipeline_failure(db_session, test_document):
    """
    Test that ingestion failure (e.g., during indexing) moves the document
    to INDEXING_FAILED state and updates the milestone to ERROR.
    """
    # Simulate an error in process_document (which runs classification/indexing)
    with patch(
        "app.services.extraction_orchestrator.process_document",
        side_effect=Exception("Simulated Indexing Error"),
    ):
        with pytest.raises(Exception, match="Simulated Indexing Error"):
            await run_ingestion_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # 1. Document should be in a terminal error state
    assert test_document.status == DocumentStatus.INDEXING_FAILED
    assert test_document.indexing_status == ProcessingStatus.ERROR
    assert "Simulated Indexing Error" in test_document.error_message

    # 2. Milestone should reflect the error (CLASSIFICATION maps to ingestion phase in this catch block)
    progress = get_progress(test_document.id)
    # The general catch block in run_ingestion_pipeline updates CLASSIFICATION milestone
    classification_milestone = progress["milestones"][
        FinancialStatementMilestone.CLASSIFICATION.value
    ]
    assert classification_milestone["status"] == MilestoneStatus.ERROR.value
    assert "Simulated Indexing Error" in classification_milestone["message"]


@pytest.mark.asyncio
async def test_extraction_pipeline_partial_failure_balance_sheet(db_session, test_document):
    """
    Test that a failure in Balance Sheet extraction DOES NOT stop the pipeline.
    The document should complete processing with a WARNING/ERROR on that specific milestone,
    but the overall status should be PROCESSING_COMPLETE.
    """
    # Setup document as already indexed
    test_document.indexing_status = ProcessingStatus.INDEXED
    test_document.status = DocumentStatus.INDEXED
    db_session.commit()

    # Mock Balance Sheet extraction to fail
    with (
        patch(
            "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
            side_effect=Exception("BS Extraction Failed"),
        ),
        patch(
            "app.app_agents.income_statement_extractor.extract_income_statement",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
            return_value={},
        ),
        patch("app.app_agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch(
            "app.app_agents.non_operating_classifier.classify_non_operating_items", return_value={}
        ),
        patch(
            "app.models.document.Document.company_id", new_callable=lambda: test_document.company_id
        ),
        patch(
            "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
        ) as mock_analysis,
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # 1. Overall status should be COMPLETED because we want it to be visible in DocumentList
    # partial failures are acceptable in the extraction phase.
    assert test_document.status == DocumentStatus.PROCESSING_COMPLETE
    assert test_document.analysis_status == ProcessingStatus.PROCESSED

    # 2. Balance Sheet milestone should be ERROR
    progress = get_progress(test_document.id)
    bs_milestone = progress["milestones"][FinancialStatementMilestone.BALANCE_SHEET.value]
    assert bs_milestone["status"] == MilestoneStatus.ERROR.value
    assert "BS Extraction Failed" in bs_milestone["message"]

    mock_analysis.assert_called()


@pytest.mark.asyncio
async def test_extraction_pipeline_partial_failure_income_statement(db_session, test_document):
    """
    Test that failure in Income Statement extraction DOES NOT stop pipeline.
    """
    test_document.indexing_status = ProcessingStatus.INDEXED
    db_session.commit()

    with (
        patch(
            "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.income_statement_extractor.extract_income_statement",
            side_effect=Exception("IS Extraction Failed"),
        ),
        patch(
            "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
            return_value={},
        ),
        patch("app.app_agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch(
            "app.app_agents.non_operating_classifier.classify_non_operating_items", return_value={}
        ),
        patch(
            "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
        ) as mock_analysis,
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    assert test_document.status == DocumentStatus.PROCESSING_COMPLETE
    assert test_document.analysis_status == ProcessingStatus.PROCESSED

    progress = get_progress(test_document.id)
    is_milestone = progress["milestones"][FinancialStatementMilestone.INCOME_STATEMENT.value]
    assert is_milestone["status"] == MilestoneStatus.ERROR.value
    assert "IS Extraction Failed" in is_milestone["message"]

    mock_analysis.assert_called()


@pytest.mark.asyncio
async def test_extraction_pipeline_critical_failure(db_session, test_document):
    """
    Test a critical failure in the orchestration logic itself (e.g. analysis crash).
    This should mark the document as EXTRACTION_FAILED.
    """
    test_document.indexing_status = ProcessingStatus.INDEXED
    db_session.commit()

    # We use AsyncMock for run_analysis_pipeline and set side_effect to raise Exception
    with patch(
        "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
    ) as mock_analysis:
        mock_analysis.side_effect = Exception("Analysis Crashed")

        with (
            patch(
                "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
                return_value={"line_items": [], "is_valid": True},
            ),
            patch(
                "app.app_agents.income_statement_extractor.extract_income_statement",
                return_value={"line_items": [], "is_valid": True},
            ),
            patch(
                "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
                return_value={},
            ),
            patch(
                "app.app_agents.organic_growth_extractor.extract_organic_growth", return_value={}
            ),
            patch(
                "app.app_agents.non_operating_classifier.classify_non_operating_items",
                return_value={},
            ),
        ):
            with pytest.raises(Exception, match="Analysis Crashed"):
                await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # Verify critical failure outcome
    assert test_document.status == DocumentStatus.EXTRACTION_FAILED
    assert test_document.analysis_status == ProcessingStatus.ERROR


@pytest.mark.asyncio
async def test_shares_outstanding_failure_is_error(db_session, test_document):
    """
    Test that Shares Outstanding extraction failure results in ERROR status for that milestone,
    but the pipeline continues (Document Status: PROCESSING_COMPLETE).
    """
    test_document.indexing_status = ProcessingStatus.INDEXED
    test_document.status = DocumentStatus.INDEXED
    db_session.commit()

    with (
        patch(
            "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.income_statement_extractor.extract_income_statement",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
            side_effect=Exception("Shares Extraction Failed"),
        ),
        patch("app.app_agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch(
            "app.app_agents.non_operating_classifier.classify_non_operating_items", return_value={}
        ),
        patch(
            "app.models.document.Document.company_id", new_callable=lambda: test_document.company_id
        ),
        patch(
            "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
        ) as mock_analysis,
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # 1. Pipeline should complete
    assert test_document.status == DocumentStatus.PROCESSING_COMPLETE

    # 2. Shares milestone should be ERROR
    progress = get_progress(test_document.id)
    shares_milestone = progress["milestones"][FinancialStatementMilestone.SHARES_OUTSTANDING.value]
    assert shares_milestone["status"] == MilestoneStatus.ERROR.value
    assert (
        "Shares extraction failed" in shares_milestone["message"]
        or "Shares Extraction Failed" in shares_milestone["message"]
    )

    mock_analysis.assert_called()


@pytest.mark.asyncio
async def test_organic_growth_failure_is_error(db_session, test_document):
    """
    Test that Organic Growth extraction failure results in ERROR status for that milestone,
    but the pipeline continues (Document Status: PROCESSING_COMPLETE).
    """
    test_document.indexing_status = ProcessingStatus.INDEXED
    test_document.status = DocumentStatus.INDEXED
    db_session.commit()

    with (
        patch(
            "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.income_statement_extractor.extract_income_statement",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
            return_value={},
        ),
        patch(
            "app.app_agents.organic_growth_extractor.extract_organic_growth",
            side_effect=Exception("Organic Growth Extraction Failed"),
        ),
        patch(
            "app.app_agents.non_operating_classifier.classify_non_operating_items", return_value={}
        ),
        patch(
            "app.models.document.Document.company_id", new_callable=lambda: test_document.company_id
        ),
        patch(
            "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
        ) as mock_analysis,
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # 1. Pipeline should complete
    assert test_document.status == DocumentStatus.PROCESSING_COMPLETE

    # 2. Organic Growth milestone should be ERROR
    progress = get_progress(test_document.id)
    og_milestone = progress["milestones"][FinancialStatementMilestone.ORGANIC_GROWTH.value]
    assert og_milestone["status"] == MilestoneStatus.ERROR.value
    assert (
        "Organic growth extraction failed" in og_milestone["message"]
        or "Organic Growth Extraction Failed" in og_milestone["message"]
    )

    mock_analysis.assert_called()


@pytest.mark.asyncio
async def test_gaap_reconciliation_failure_is_warning(db_session, test_document):
    """
    Test that GAAP Reconciliation extraction failure results in WARNING status for that milestone,
    but the pipeline continues (Document Status: PROCESSING_COMPLETE).
    """
    test_document.indexing_status = ProcessingStatus.INDEXED
    test_document.status = DocumentStatus.INDEXED
    db_session.commit()

    with (
        patch(
            "app.app_agents.balance_sheet_extractor.extract_balance_sheet",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.income_statement_extractor.extract_income_statement",
            return_value={"line_items": [], "is_valid": True},
        ),
        patch(
            "app.app_agents.shares_outstanding_extractor.extract_shares_outstanding",
            return_value={},
        ),
        patch("app.app_agents.organic_growth_extractor.extract_organic_growth", return_value={}),
        patch(
            "app.app_agents.gaap_reconciliation_extractor.extract_gaap_reconciliation",
            side_effect=Exception("GAAP Extraction Failed"),
        ),
        patch(
            "app.app_agents.non_operating_classifier.classify_non_operating_items", return_value={}
        ),
        patch(
            "app.models.document.Document.company_id", new_callable=lambda: test_document.company_id
        ),
        patch(
            "app.services.extraction_orchestrator.run_analysis_pipeline", new_callable=AsyncMock
        ) as mock_analysis,
    ):
        await run_full_extraction_pipeline(test_document.id, db_session)

    db_session.refresh(test_document)

    # 1. Pipeline should complete
    assert test_document.status == DocumentStatus.PROCESSING_COMPLETE

    # 2. GAAP milestone should be WARNING
    progress = get_progress(test_document.id)
    gaap_milestone = progress["milestones"][FinancialStatementMilestone.GAAP_RECONCILIATION.value]
    assert gaap_milestone["status"] == MilestoneStatus.WARNING.value
    assert (
        "GAAP reconciliation extraction failed" in gaap_milestone["message"]
        or "GAAP Extraction Failed" in gaap_milestone["message"]
    )

    mock_analysis.assert_called()

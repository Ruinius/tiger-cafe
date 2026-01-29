from unittest.mock import patch

import pytest

from app.database import Base, SessionLocal, engine
from app.models.company import Company
from app.services.company_service import get_or_create_assumptions
from app.services.qualitative_service import run_qualitative_assessment


# Setup database for testing (if not using a global fixture)
@pytest.fixture(scope="module")
def db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    # Cleanup
    session.close()
    # Base.metadata.drop_all(bind=engine) # Optional cleanup


@pytest.fixture
def test_company(db):
    company = Company(name="Test Corp", ticker="TST")
    db.add(company)
    db.commit()
    db.refresh(company)
    yield company
    db.delete(company)
    db.commit()


def test_qualitative_assessment_flow(db, test_company):
    # Mock LLM response
    mock_llm_response = {
        "economic_moat_label": "Wide",
        "economic_moat_rationale": "Strong network effects.",
        "near_term_growth_label": "Faster",
        "near_term_growth_rationale": "New product launch.",
        "revenue_predictability_label": "High",
        "revenue_predictability_rationale": "Subscription model.",
    }

    with patch(
        "app.services.qualitative_service.extract_qualitative_assessment",
        return_value=mock_llm_response,
    ) as mock_agent:
        # 1. Run Assessment
        assessment = run_qualitative_assessment(db, test_company.id)

        assert assessment.company_id == test_company.id
        assert assessment.economic_moat_label == "Wide"
        assert assessment.near_term_growth_label == "Faster"
        assert assessment.revenue_predictability_label == "High"

        # Verify mocked agent was called with correct args
        mock_agent.assert_called_once_with("TST", "Test Corp")

        # 2. Check Assumptions Integration
        # Ensure no logical errors in assumption service
        # (Note: we might need to mock get_company_historical_data if we want to test exact math,
        # but here we just check if it runs and applies overrides if defaults allow)

        # We need to mock get_company_historical_data to return empty logic so defaults kick in
        with patch(
            "app.services.company_service.get_company_historical_data", return_value={"entries": []}
        ):
            # And mock market data to avoid external calls
            with (
                patch("app.services.company_service.get_beta", return_value=1.5),
                patch("app.services.company_service.get_market_cap", return_value=1000.0),
                patch("app.services.company_service.get_currency_rate", return_value=1.0),
            ):
                assumption = get_or_create_assumptions(db, test_company.id)

                # Check Terminal Growth Override (Wide Moat -> 4%)
                # Default is 3%, Wide is 4%
                assert float(assumption.revenue_growth_terminal) == 0.04

                # Check Stage 1 Growth Override (Faster -> +2%)
                # Default for empty history is 0.05 (5%). Faster adds 0.02. Result 0.07.
                # Use approx for float comparison
                assert abs(float(assumption.revenue_growth_stage1) - 0.07) < 0.0001

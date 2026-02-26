from unittest.mock import patch

import pytest

from app.app_agents.qualitative_extractor import extract_qualitative_assessment


@pytest.fixture
def mock_call_llm():
    with patch("app.app_agents.qualitative_extractor.call_llm_with_retry") as mock:
        yield mock


def test_extract_qualitative_assessment_two_step_flow(mock_call_llm):
    # Setup mock responses for the two steps

    # Step 1: Analysis response (structured JSON format)
    analysis_response = {
        "economic_moat": {
            "cases_for": ["Strong network effects", "High switching costs"],
            "cases_against": ["New entrants", "Regulatory risk"],
            "conclusion": "Wide moat due to network effects.",
        },
        "near_term_growth": {
            "cases_for": ["High demand", "Market expansion"],
            "cases_against": ["Supply chain issues"],
            "conclusion": "Faster growth expected.",
        },
        "revenue_predictability": {
            "cases_for": ["Long-term contracts"],
            "cases_against": ["Potential cancellations"],
            "conclusion": "High predictability.",
        },
    }

    # Step 2: Labeling response
    labeling_response = {
        "economic_moat_label": "Wide",
        "near_term_growth_label": "Faster",
        "revenue_predictability_label": "High",
    }

    # Using side_effect to return different values for each call
    mock_call_llm.side_effect = [analysis_response, labeling_response]

    ticker = "GOOGL"
    company_name = "Alphabet Inc."

    # Execute the function
    result = extract_qualitative_assessment(ticker, company_name)

    # Assertions

    # 1. Check that both steps were called
    assert mock_call_llm.call_count == 2

    # Check Step 1 arguments (Analysis Prompt)
    args1, kwargs1 = mock_call_llm.call_args_list[0]
    prompt1 = args1[0]
    assert "You are an expert equity research analyst" in prompt1
    assert "Cases For" in prompt1
    assert "Cases Against" in prompt1
    # Check temperature for step 1
    assert kwargs1.get("temperature") == 0.7

    # Check Step 2 arguments (Labeling Prompt)
    args2, kwargs2 = mock_call_llm.call_args_list[1]
    prompt2 = args2[0]
    assert "You are a strict grading assistant" in prompt2
    # Ensure rationales from step 1 were included in step 2's prompt
    assert "Strong network effects" in prompt2
    # Check temperature for step 2
    assert kwargs2.get("temperature") == 0.0

    # 3. Check Final Combined Result
    assert result["economic_moat_label"] == "Wide"
    assert "Strong network effects" in result["economic_moat_rationale"]
    assert "Wide moat" in result["economic_moat_rationale"]
    assert result["near_term_growth_label"] == "Faster"
    assert result["revenue_predictability_label"] == "High"


def test_extract_qualitative_assessment_missing_rationale(mock_call_llm):
    # Test fallback behavior when step 1 misses keys

    # Step 1: Partial Analysis (missing growth and predictability)
    analysis_response = {
        "economic_moat": {
            "cases_for": ["Moat stuff"],
            "cases_against": [],
            "conclusion": "Narrow moat.",
        }
        # near_term_growth missing
        # revenue_predictability missing
    }

    # Step 2: Labeling response
    labeling_response = {
        "economic_moat_label": "Narrow",
        "near_term_growth_label": "Steady",
        "revenue_predictability_label": "Mid",
    }

    mock_call_llm.side_effect = [analysis_response, labeling_response]

    result = extract_qualitative_assessment("TST", "Test")

    # Verify strict grading prompt received "No rationale."
    args2, _ = mock_call_llm.call_args_list[1]
    prompt2 = args2[0]
    assert "No rationale." in prompt2

    # Verify result merge
    assert result["economic_moat_label"] == "Narrow"
    assert "Moat stuff" in result["economic_moat_rationale"]

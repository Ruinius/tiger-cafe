from unittest.mock import MagicMock, patch

import pytest

from app.app_agents.organic_growth_extractor import (
    _reflect_on_prior_revenue,
    extract_organic_growth,
    extract_prior_year_revenue,
)


def test_reflect_on_prior_revenue_raises_error_on_failure():
    """Test that reflection raises RuntimeError instead of returning error string."""
    with patch(
        "app.app_agents.organic_growth_extractor.call_llm_with_retry",
        side_effect=Exception("LLM Error"),
    ):
        with pytest.raises(RuntimeError) as excinfo:
            _reflect_on_prior_revenue(100, "millions", "Q2 2024", "Q2 2023", 110, "Document text")
    assert "Reflection failed: LLM Error" in str(excinfo.value)


def test_extract_prior_year_revenue_raises_error_on_failure():
    """Test that extraction raises RuntimeError on exception."""
    with patch(
        "app.app_agents.organic_growth_extractor.call_llm_and_parse_json",
        side_effect=Exception("Parsing Error"),
    ):
        with pytest.raises(RuntimeError) as excinfo:
            extract_prior_year_revenue("text", "2024")
    assert "Prior year revenue extraction failed: Parsing Error" in str(excinfo.value)


def test_extract_organic_growth_returns_invalid_if_chunk_index_missing():
    """Test that extract_organic_growth returns invalid result if IS chunk index is missing."""

    mock_full_text = MagicMock(return_value="Full document text")
    mock_context = MagicMock(return_value="Organic Growth Text")

    with (
        patch("app.app_agents.organic_growth_extractor.load_full_document_text", mock_full_text),
        patch(
            "app.app_agents.organic_growth_extractor.extract_context_around_keywords", mock_context
        ),
        patch(
            "app.app_agents.organic_growth_extractor.extract_organic_growth_percentage_only",
            return_value=None,
        ),
        patch(
            "app.app_agents.organic_growth_extractor.find_revenue_line_value", return_value=100.0
        ),
        patch("app.app_agents.organic_growth_extractor.add_log"),
    ):
        # Missing chunk_index in income_statement_data
        income_statement_data = {
            "line_items": [],
            "unit": "millions",
            "revenue_prior_year": None,
            # "chunk_index": missing!
        }

        # Should NOT raise ValueError anymore, but return invalid result
        result = extract_organic_growth("doc_id", "path/to/file", "Q1 2024", income_statement_data)

        assert result["is_valid"] is False
        assert "Prior period revenue not found" in result["validation_errors"]


def test_extract_organic_growth_uses_provided_chunk_index():
    """Test that it uses the provided chunk_index and does not raise error."""

    mock_full_text = MagicMock(return_value="Full document text")
    mock_context = MagicMock(return_value="Organic Growth Text")
    mock_get_chunk = MagicMock(return_value=("IS Text", 2, 0.95))

    with (
        patch("app.app_agents.organic_growth_extractor.load_full_document_text", mock_full_text),
        patch(
            "app.app_agents.organic_growth_extractor.extract_context_around_keywords", mock_context
        ),
        patch(
            "app.app_agents.organic_growth_extractor.extract_organic_growth_percentage_only",
            return_value=5.5,
        ),
        patch(
            "app.app_agents.organic_growth_extractor.reflect_on_organic_growth",
            return_value={"is_valid": True, "reason": "Valid"},
        ),
        patch(
            "app.app_agents.organic_growth_extractor.find_revenue_line_value", return_value=100.0
        ),
        patch("app.app_agents.organic_growth_extractor.get_chunk_with_context", mock_get_chunk),
        patch(
            "app.app_agents.organic_growth_extractor.extract_prior_year_revenue",
            return_value=(90.0, "millions", None),
        ),
        patch("app.app_agents.organic_growth_extractor.add_log"),
    ):
        income_statement_data = {
            "line_items": [
                {"standardized_name": "total_revenue", "line_name": "Revenue", "line_value": 100}
            ],
            "unit": "millions",
            "revenue_prior_year": None,
            "chunk_index": 555,  # Provided!
        }

        result = extract_organic_growth("doc_id", "path/to/file", "Q1 2024", income_statement_data)

        assert result["is_valid"] is True
        # Verify get_chunk_with_context was called with the provided chunk index 555
        mock_get_chunk.assert_called_with(
            "doc_id", "path/to/file", 555, chars_before=2500, chars_after=2500
        )

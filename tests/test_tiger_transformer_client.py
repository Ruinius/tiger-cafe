"""
Unit tests for TigerTransformerClient
"""

import pytest

from app.services.tiger_transformer_client import TigerTransformerClient


class TestTigerTransformerClient:
    """Test suite for TigerTransformerClient"""

    @pytest.fixture(scope="class")
    def client(self):
        """Create a single client instance for all tests (model loading is expensive)"""
        return TigerTransformerClient()

    def test_client_singleton(self):
        """Test that TigerTransformerClient follows singleton pattern"""
        client1 = TigerTransformerClient()
        client2 = TigerTransformerClient()
        assert client1 is client2

    def test_model_loaded(self, client):
        """Test that model and tokenizer are loaded"""
        assert client._model is not None
        assert client._tokenizer is not None

    def test_mappings_loaded(self, client):
        """Test that mapping CSVs are loaded"""
        assert client._bs_mapping is not None
        assert client._is_mapping is not None
        assert len(client._bs_mapping) > 0
        assert len(client._is_mapping) > 0

    def test_balance_sheet_prediction_basic(self, client):
        """Test basic balance sheet prediction"""
        line_items = [
            {
                "line_name": "Cash and cash equivalents",
                "line_category": "current_assets",
                "line_order": 1,
            },
            {
                "line_name": "Accounts receivable",
                "line_category": "current_assets",
                "line_order": 2,
            },
            {
                "line_name": "Total current assets",
                "line_category": "current_assets",
                "line_order": 3,
            },
        ]

        results = client.predict_balance_sheet(line_items)

        assert len(results) == 3
        for result in results:
            assert "standardized_name" in result
            assert "is_calculated" in result
            assert "is_operating" in result
            # Original fields should be preserved
            assert "line_name" in result
            assert "line_category" in result
            assert "line_order" in result

    def test_income_statement_prediction_basic(self, client):
        """Test basic income statement prediction"""
        line_items = [
            {
                "line_name": "Total net revenue",
                "line_category": "income_statement",
                "line_order": 1,
            },
            {
                "line_name": "Cost of revenue",
                "line_category": "income_statement",
                "line_order": 2,
            },
            {
                "line_name": "Gross profit",
                "line_category": "income_statement",
                "line_order": 3,
            },
        ]

        results = client.predict_income_statement(line_items)

        assert len(results) == 3
        for result in results:
            assert "standardized_name" in result
            assert "is_calculated" in result
            assert "is_operating" in result
            assert "is_expense" in result
            # Original fields should be preserved
            assert "line_name" in result
            assert "line_category" in result
            assert "line_order" in result

    def test_empty_input(self, client):
        """Test that empty input returns empty output"""
        assert client.predict_balance_sheet([]) == []
        assert client.predict_income_statement([]) == []

    def test_single_item_context(self, client):
        """Test prediction with single item (edge case for context window)"""
        line_items = [
            {
                "line_name": "Cash",
                "line_category": "current_assets",
                "line_order": 1,
            }
        ]

        results = client.predict_balance_sheet(line_items)
        assert len(results) == 1
        assert "standardized_name" in results[0]

    def test_mapping_enrichment_bs(self, client):
        """Test that BS predictions are enriched with mapping data"""
        # Use a known standardized name from the mapping
        if "cash_and_equivalents" in client._bs_mapping:
            line_items = [
                {
                    "line_name": "Cash and cash equivalents",
                    "line_category": "current_assets",
                    "line_order": 1,
                }
            ]

            results = client.predict_balance_sheet(line_items)

            # If the model predicts "cash_and_equivalents", it should be enriched
            if results[0]["standardized_name"] == "cash_and_equivalents":
                assert results[0]["is_calculated"] is not None
                assert results[0]["is_operating"] is not None

    def test_mapping_enrichment_is(self, client):
        """Test that IS predictions are enriched with mapping data"""
        # Use a known standardized name from the mapping
        if "revenue" in client._is_mapping:
            line_items = [
                {
                    "line_name": "Total net revenue",
                    "line_category": "income_statement",
                    "line_order": 1,
                }
            ]

            results = client.predict_income_statement(line_items)

            # If the model predicts "revenue", it should be enriched
            if results[0]["standardized_name"] == "revenue":
                assert results[0]["is_calculated"] is not None
                assert results[0]["is_operating"] is not None
                assert results[0]["is_expense"] is not None

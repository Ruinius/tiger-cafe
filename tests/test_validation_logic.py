"""
Unit tests for validation logic including section fallback and calculation validation
"""

from agents.balance_sheet_extractor import (
    post_process_balance_sheet_line_items,
    validate_balance_sheet_calculations,
)


class TestBalanceSheetSectionFallback:
    """Test section tag fallback logic in post_process_balance_sheet_line_items"""

    def test_valid_tokens_unchanged(self):
        """Test that valid tokens are not modified"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "line_order": 1,
            },
            {
                "line_name": "Accounts Receivable",
                "line_value": 500,
                "line_category": "current_assets",
                "line_order": 2,
            },
        ]

        # Should not raise an error and should preserve valid tokens
        result = post_process_balance_sheet_line_items(line_items)
        assert all(item["line_category"] == "current_assets" for item in result)

    def test_missing_token_inferred_from_previous(self):
        """Test that missing tokens are inferred from previous item"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "line_order": 1,
            },
            {
                "line_name": "Marketable Securities",
                "line_value": 200,
                "line_category": "",  # Missing
                "line_order": 2,
            },
        ]

        result = post_process_balance_sheet_line_items(line_items)
        # Second item should inherit from first
        assert result[1]["line_category"] == "current_assets"

    def test_invalid_token_inferred_from_next(self):
        """Test that invalid tokens are inferred from next item"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "INVALID_TOKEN",  # Invalid
                "line_order": 1,
            },
            {
                "line_name": "Accounts Receivable",
                "line_value": 500,
                "line_category": "current_assets",
                "line_order": 2,
            },
        ]

        result = post_process_balance_sheet_line_items(line_items)
        # First item should inherit from second
        assert result[0]["line_category"] == "current_assets"

    def test_heuristic_fallback_for_assets(self):
        """Test heuristic fallback based on line name for assets"""
        line_items = [
            {
                "line_name": "Total Current Assets",
                "line_value": 1500,
                "line_category": "",  # Missing
                "line_order": 1,
            }
        ]

        result = post_process_balance_sheet_line_items(line_items)
        # Should infer current_assets from "current" and "asset" in name
        assert result[0]["line_category"] == "current_assets"

    def test_heuristic_fallback_for_liabilities(self):
        """Test heuristic fallback for liabilities"""
        line_items = [
            {
                "line_name": "Current Liabilities",
                "line_value": 800,
                "line_category": "",
                "line_order": 1,
            }
        ]

        result = post_process_balance_sheet_line_items(line_items)
        assert result[0]["line_category"] == "current_liabilities"

    def test_heuristic_fallback_for_equity(self):
        """Test heuristic fallback for equity"""
        line_items = [
            {
                "line_name": "Stockholders' Equity",
                "line_value": 5000,
                "line_category": "",
                "line_order": 1,
            }
        ]

        result = post_process_balance_sheet_line_items(line_items)
        assert result[0]["line_category"] == "stockholders_equity"


class TestBalanceSheetValidation:
    """Test balance sheet calculation validation using standardized_name"""

    def test_valid_balance_sheet(self):
        """Test validation passes for correct balance sheet"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "cash_and_equivalents",
                "is_calculated": False,
            },
            {
                "line_name": "Accounts Receivable",
                "line_value": 500,
                "line_category": "current_assets",
                "standardized_name": "accounts_receivable",
                "is_calculated": False,
            },
            {
                "line_name": "Total Current Assets",
                "line_value": 1500,
                "line_category": "current_assets",
                "standardized_name": "total_current_assets",
                "is_calculated": True,
            },
            {
                "line_name": "Total Assets",
                "line_value": 1500,
                "line_category": "current_assets",
                "standardized_name": "total_assets",
                "is_calculated": True,
            },
        ]

        is_valid, errors = validate_balance_sheet_calculations(line_items)
        assert is_valid
        assert len(errors) == 0

    def test_invalid_total_current_assets(self):
        """Test validation fails when total current assets doesn't match sum"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "cash_and_equivalents",
                "is_calculated": False,
            },
            {
                "line_name": "Accounts Receivable",
                "line_value": 500,
                "line_category": "current_assets",
                "standardized_name": "accounts_receivable",
                "is_calculated": False,
            },
            {
                "line_name": "Total Current Assets",
                "line_value": 2000,  # Wrong! Should be 1500
                "line_category": "current_assets",
                "standardized_name": "total_current_assets",
                "is_calculated": True,
            },
        ]

        is_valid, errors = validate_balance_sheet_calculations(line_items)
        assert not is_valid
        assert len(errors) > 0
        assert "Total current assets mismatch" in errors[0]

    def test_validation_uses_is_calculated_flag(self):
        """Test that validation only sums items where is_calculated=False"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "cash_and_equivalents",
                "is_calculated": False,
            },
            {
                "line_name": "Subtotal",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "other_subtotal",
                "is_calculated": True,  # Should be excluded from sum
            },
            {
                "line_name": "Total Current Assets",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "total_current_assets",
                "is_calculated": True,
            },
            {
                "line_name": "Total Assets",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "total_assets",
                "is_calculated": True,
            },
        ]

        is_valid, errors = validate_balance_sheet_calculations(line_items)
        # Should pass because subtotal is excluded from sum
        assert is_valid

    def test_missing_key_totals(self):
        """Test validation fails when key totals are missing"""
        line_items = [
            {
                "line_name": "Cash",
                "line_value": 1000,
                "line_category": "current_assets",
                "standardized_name": "cash_and_equivalents",
                "is_calculated": False,
            }
        ]

        is_valid, errors = validate_balance_sheet_calculations(line_items)
        assert not is_valid
        assert any("missing key totals" in error.lower() for error in errors)


class TestIncomeStatementValidation:
    """Test income statement validation with is_expense normalization"""

    def test_is_expense_normalization_logic(self):
        """Test that is_expense=True items with positive values are flipped to negative"""
        # Simulate what happens in post_process after transformer client returns
        items = [
            {"line_value": 1000, "is_expense": False},  # Revenue, stays positive
            {"line_value": 400, "is_expense": True},  # Cost, should flip to negative
            {"line_value": -50, "is_expense": True},  # Already negative, stays negative
            {"line_value": 100, "is_expense": None},  # Ambiguous, stays as is
        ]

        # Apply normalization logic
        for item in items:
            is_expense = item.get("is_expense")
            line_value = item.get("line_value", 0)

            if is_expense is True and line_value > 0:
                item["line_value"] = -line_value

        # Verify results
        assert items[0]["line_value"] == 1000, "Revenue should stay positive"
        assert items[1]["line_value"] == -400, "Positive expense should flip to negative"
        assert items[2]["line_value"] == -50, "Already negative expense should stay negative"
        assert items[3]["line_value"] == 100, "Ambiguous item should stay as extracted"

    def test_ambiguous_items_remain_unchanged(self):
        """Test that is_expense=None items are not modified during normalization"""
        items = [
            {"line_value": 50, "is_expense": None},
            {"line_value": -30, "is_expense": None},
        ]

        # Apply normalization logic (should not change anything)
        for item in items:
            is_expense = item.get("is_expense")
            line_value = item.get("line_value", 0)

            if is_expense is True and line_value > 0:
                item["line_value"] = -line_value

        # Verify no changes
        assert items[0]["line_value"] == 50
        assert items[1]["line_value"] == -30

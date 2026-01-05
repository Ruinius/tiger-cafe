"""
Tests for financial statement validation functions
"""

from agents.balance_sheet_extractor import validate_balance_sheet
from agents.income_statement_extractor import validate_income_statement


def test_validate_balance_sheet_minimum_lines():
    """Test that balance sheet validation requires at least 10 lines"""
    # Test with empty list
    is_valid, errors = validate_balance_sheet([])
    assert not is_valid
    assert any("empty" in error.lower() for error in errors)

    # Test with less than 10 lines
    line_items = [{"line_name": f"Item {i}", "line_value": 1000} for i in range(9)]
    is_valid, errors = validate_balance_sheet(line_items)
    assert not is_valid
    assert any("at least 10" in error for error in errors)

    # Test with exactly 10 lines (should pass minimum line check, may fail other validations)
    line_items = [{"line_name": f"Item {i}", "line_value": 1000} for i in range(10)]
    is_valid, errors = validate_balance_sheet(line_items)
    # May fail other validations, but should not fail minimum line check
    assert not any("at least 10" in error for error in errors)


def test_validate_balance_sheet_empty_line_names():
    """Test that balance sheet validation filters out items with empty line names"""
    # Test with mix of valid and invalid items
    line_items = [
        {"line_name": "Valid Item 1", "line_value": 1000},
        {"line_name": "", "line_value": 2000},  # Empty name
        {"line_name": "   ", "line_value": 3000},  # Whitespace only
        {"line_name": "Valid Item 2", "line_value": 4000},
    ]
    is_valid, errors = validate_balance_sheet(line_items)
    # Should only count valid items (2), so should fail minimum line check
    assert not is_valid
    assert any("at least 10" in error for error in errors)


def test_validate_income_statement_minimum_lines():
    """Test that income statement validation requires at least 5 lines"""
    # Test with empty list
    is_valid, errors = validate_income_statement([])
    assert not is_valid
    assert any("empty" in error.lower() for error in errors)

    # Test with less than 5 lines
    line_items = [{"line_name": f"Item {i}", "line_value": 1000} for i in range(4)]
    is_valid, errors = validate_income_statement(line_items)
    assert not is_valid
    assert any("at least 5" in error for error in errors)

    # Test with exactly 5 lines but missing required items
    line_items = [{"line_name": f"Item {i}", "line_value": 1000} for i in range(5)]
    is_valid, errors = validate_income_statement(line_items)
    # Should not fail minimum line check, but will fail required items check
    assert not is_valid
    assert not any("at least 5" in error for error in errors)


def test_validate_income_statement_required_items():
    """Test that income statement validation requires Total Net Revenue and Net Income"""
    # Test with 5 lines but missing Total Net Revenue
    line_items = [
        {"line_name": "Item 1", "line_value": 1000},
        {"line_name": "Item 2", "line_value": 2000},
        {"line_name": "Item 3", "line_value": 3000},
        {"line_name": "Item 4", "line_value": 4000},
        {"line_name": "Net Income", "line_value": 5000},
    ]
    is_valid, errors = validate_income_statement(line_items)
    assert not is_valid
    assert any("Total Net Revenue" in error for error in errors)

    # Test with 5 lines but missing Net Income
    line_items = [
        {"line_name": "Total Net Revenue", "line_value": 10000},
        {"line_name": "Item 2", "line_value": 2000},
        {"line_name": "Item 3", "line_value": 3000},
        {"line_name": "Item 4", "line_value": 4000},
        {"line_name": "Item 5", "line_value": 5000},
    ]
    is_valid, errors = validate_income_statement(line_items)
    assert not is_valid
    assert any("Net Income" in error for error in errors)

    # Test with 5 lines and both required items (with standardized names)
    line_items = [
        {"line_name": "Total Net Revenue (Revenue)", "line_value": 10000},
        {"line_name": "Item 2", "line_value": 2000},
        {"line_name": "Item 3", "line_value": 3000},
        {"line_name": "Item 4", "line_value": 4000},
        {"line_name": "Net Income (Net income)", "line_value": 5000},
    ]
    is_valid, errors = validate_income_statement(line_items)
    # Should pass required items check (may fail other validations)
    assert not any("Total Net Revenue" in error for error in errors)
    assert not any("Net Income" in error for error in errors)

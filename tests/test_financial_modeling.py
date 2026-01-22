from decimal import Decimal

from app.utils.financial_modeling import calculate_dcf


def test_calculate_dcf_basic():
    # Mock historical entries
    historical_entries = [
        {
            "time_period": "FY 2020",
            "revenue": Decimal("100"),
            "invested_capital": Decimal("50"),
            "capital_turnover": Decimal("2.0"),
        }
    ]

    # Mock assumptions
    assumptions = {
        "revenue_growth_stage1": 0.05,
        "ebita_margin_stage1": 0.20,
        "marginal_capital_turnover_stage1": 2.0,
        "adjusted_tax_rate": 0.25,
        "wacc": 0.08,
    }

    result = calculate_dcf(historical_entries, assumptions)

    assert "projections" in result
    assert len(result["projections"]) == 10

    # Check Year 1
    # Revenue = 100 * 1.05 = 105
    # EBITA = 105 * 0.20 = 21
    # NOPAT = 21 * (1 - 0.25) = 15.75
    # Delta Revenue = 5
    # Delta IC = 5 / 2.0 = 2.5
    # FCF = 15.75 - 2.5 = 13.25

    year1 = result["projections"][0]
    assert year1["year"] == 1
    assert float(year1["revenue"]) == 105.0
    assert float(year1["nopat"]) == 15.75
    assert float(year1["fcf"]) == 13.25

    # Check Enterprise Value exists
    assert result["enterprise_value"] > 0


def test_calculate_dcf_defaults():
    historical_entries = [
        {"time_period": "FY 2020", "revenue": Decimal("1000"), "invested_capital": Decimal("500")}
    ]

    # Empty assumptions should use defaults
    result = calculate_dcf(historical_entries, {})

    assert "projections" in result
    # Check default WACC 9%
    assert result["assumptions_used"]["wacc"] == Decimal("0.09")

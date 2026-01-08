"""
Financial modeling utilities
"""

from decimal import Decimal


def calculate_dcf(historical_entries: list, assumptions: dict) -> dict:
    """
    Calculate DCF model based on historical data and assumptions.

    assumptions dict should contain:
    - revenue_growth_stage1
    - revenue_growth_stage2
    - revenue_growth_terminal
    - ebita_margin_stage1
    - ebita_margin_stage2
    - ebita_margin_terminal
    - marginal_capital_turnover_stage1
    - marginal_capital_turnover_stage2
    - marginal_capital_turnover_terminal
    - adjusted_tax_rate
    - wacc
    """

    # Defaults
    defaults = {
        "revenue_growth_stage1": 0.05,
        "revenue_growth_stage2": 0.04,
        "revenue_growth_terminal": 0.03,
        "ebita_margin_stage1": 0.20,
        "ebita_margin_stage2": 0.20,
        "ebita_margin_terminal": 0.20,
        "marginal_capital_turnover_stage1": 1.0,
        "marginal_capital_turnover_stage2": 1.0,
        "marginal_capital_turnover_terminal": 1.0,
        "adjusted_tax_rate": 0.25,
        "wacc": 0.08,
    }

    # Helper to get assumption value or default
    def get_assumption(key):
        val = assumptions.get(key)
        if val is None:
            return Decimal(str(defaults[key]))
        return Decimal(str(val))

    # Extract latest historical data
    if not historical_entries:
        return {"error": "No historical data available"}

    latest_entry = historical_entries[-1]

    # Starting values
    start_revenue = latest_entry.get("revenue") or Decimal("0")
    start_invested_capital = latest_entry.get("invested_capital") or Decimal("0")

    # If starting revenue is quarterly, annualize it
    # We can infer if it's quarterly by looking at the time_period string
    time_period = latest_entry.get("time_period", "")
    is_quarterly = "Q" in time_period and "FY" not in time_period
    if is_quarterly:
        start_revenue *= 4

    # Calculate average capital turnover from recent 4 values if available
    recent_entries = historical_entries[-4:]
    capital_turnovers = [
        e.get("capital_turnover") for e in recent_entries if e.get("capital_turnover") is not None
    ]

    # If marginal capital turnover assumptions are missing, default to average historical capital turnover
    avg_capital_turnover = Decimal("1.0")
    if capital_turnovers:
        avg_capital_turnover = sum(capital_turnovers) / len(capital_turnovers)

    # Resolve assumptions with fallbacks
    wacc = get_assumption("wacc")
    tax_rate = get_assumption("adjusted_tax_rate")

    # Stage 1: Years 1-5
    # Stage 2: Years 6-10
    # Terminal: Year 11+

    projections = []

    current_revenue = start_revenue
    current_invested_capital = start_invested_capital

    # Discount Factor logic: 1 / (1 + WACC) ^ (Year - 0.5) for mid-year convention

    years_to_project = 10

    for year in range(1, years_to_project + 1):
        # Determine phase
        if year <= 5:
            growth_rate = get_assumption("revenue_growth_stage1")
            margin = get_assumption("ebita_margin_stage1")
            mct = assumptions.get("marginal_capital_turnover_stage1")
            if mct is None:
                mct = avg_capital_turnover
            else:
                mct = Decimal(str(mct))
        else:
            growth_rate = get_assumption("revenue_growth_stage2")
            margin = get_assumption("ebita_margin_stage2")
            mct = assumptions.get("marginal_capital_turnover_stage2")
            if mct is None:
                mct = avg_capital_turnover
            else:
                mct = Decimal(str(mct))

        # 1. Revenue
        prev_revenue = current_revenue
        current_revenue = prev_revenue * (1 + growth_rate)
        delta_revenue = current_revenue - prev_revenue

        # 2. EBITA & NOPAT
        ebita = current_revenue * margin
        nopat = ebita * (1 - tax_rate)

        # 3. Invested Capital
        # Delta IC = Delta Revenue / Marginal Capital Turnover
        if mct != 0:
            delta_ic = delta_revenue / mct
        else:
            delta_ic = 0

        current_invested_capital += delta_ic

        # 4. FCF = NOPAT - Delta IC
        fcf = nopat - delta_ic

        # 5. Discount Factor (Mid-year convention)
        discount_factor = 1 / ((1 + wacc) ** (Decimal(year) - Decimal("0.5")))
        pv_fcf = fcf * discount_factor

        projections.append(
            {
                "year": year,
                "revenue": current_revenue,
                "growth_rate": growth_rate,
                "ebita": ebita,
                "margin": margin,
                "nopat": nopat,
                "invested_capital": current_invested_capital,
                "delta_ic": delta_ic,
                "fcf": fcf,
                "discount_factor": discount_factor,
                "pv_fcf": pv_fcf,
                "roic": nopat / current_invested_capital if current_invested_capital else 0,
            }
        )

    # Terminal Value
    # Using formula: TV = NOPAT_t+1 * (1 - g/ROIC) / (WACC - g)
    # Or simpler perpetuity growth: TV = FCF_t+1 / (WACC - g)
    # But user asked for "more robust formula including ROIC" -> Value Driver Formula
    # TV = (NOPAT_t+1 * (1 - g/ROIC_new)) / (WACC - g)

    # Terminal Year Assumptions
    g_terminal = get_assumption("revenue_growth_terminal")
    margin_terminal = get_assumption("ebita_margin_terminal")
    mct_terminal = assumptions.get("marginal_capital_turnover_terminal")
    if mct_terminal is None:
        mct_terminal = avg_capital_turnover
    else:
        mct_terminal = Decimal(str(mct_terminal))

    # Year 11 values
    revenue_terminal_year = current_revenue * (1 + g_terminal)
    ebita_terminal_year = revenue_terminal_year * margin_terminal
    nopat_terminal_year = ebita_terminal_year * (1 - tax_rate)

    # Implied ROIC on new capital in terminal phase = Marginal Capital Turnover * Margin * (1-Tax) / Growth?
    # Actually ROIC = NOPAT / Invested Capital.
    # Marginal ROIC = Delta NOPAT / Delta IC ?
    # Let's use the explicit ROIC from the model?
    # Or simply:
    # Investment Rate = g / ROIC
    # FCF = NOPAT * (1 - Investment Rate) = NOPAT * (1 - g/ROIC)

    # We can calculate ROIC from the assumptions:
    # ROIC = NOPAT / IC.
    # In terminal state, ROIC should converge.
    # Let's use the ROIC from year 10 as the terminal ROIC?
    # Or calculate it implied by Marginal Capital Turnover?
    # New Capital = Delta Revenue / MCT
    # Return on New Capital = (Delta Revenue * Margin * (1-Tax)) / (Delta Revenue / MCT)
    # = Margin * (1-Tax) * MCT

    ronic = margin_terminal * (1 - tax_rate) * mct_terminal

    if ronic == 0:
        investment_rate = 0
    else:
        investment_rate = g_terminal / ronic

    fcf_terminal_year = nopat_terminal_year * (1 - investment_rate)

    # Terminal Value at end of Year 10
    if (wacc - g_terminal) == 0:
        terminal_value = 0  # Avoid div by zero
    else:
        terminal_value = fcf_terminal_year / (wacc - g_terminal)

    # Discount Terminal Value to PV
    # Discount factor for end of year 10 (not mid-year for TV usually, but let's be consistent with cash flow timing)
    # Usually TV is at end of year 10.
    discount_factor_tv = 1 / ((1 + wacc) ** Decimal(years_to_project))
    pv_terminal_value = terminal_value * discount_factor_tv

    sum_pv_fcf = sum(p["pv_fcf"] for p in projections)
    enterprise_value = sum_pv_fcf + pv_terminal_value

    return {
        "projections": projections,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "assumptions_used": {
            "wacc": wacc,
            "tax_rate": tax_rate,
            "terminal_growth": g_terminal,
            "terminal_roic": ronic,
        },
    }

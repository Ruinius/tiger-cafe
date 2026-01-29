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
        "wacc": 0.09,
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
    start_invested_capital = Decimal(str(latest_entry.get("invested_capital") or 0))

    # Check if latest entry is quarterly (for fallback logic)
    time_period = latest_entry.get("time_period", "")
    is_quarterly = "Q" in time_period and "FY" not in time_period

    # Check if base_revenue is provided in assumptions
    base_revenue_assumption = assumptions.get("base_revenue")
    if base_revenue_assumption is not None:
        start_revenue = Decimal(str(base_revenue_assumption))
    else:
        # Filter for quarterly data first (to satisfy L4Q logic)
        quarterly_entries = [e for e in historical_entries if "Q" in e.get("time_period", "")]

        if quarterly_entries:
            # Use last 4 quarters (or fewer if not available)
            l4q = quarterly_entries[-4:]
            revenues = [e.get("revenue") for e in l4q if e.get("revenue") is not None]

            if revenues:
                avg_revenue = sum(revenues) / len(revenues)
                start_revenue = Decimal(str(avg_revenue)) * 4
            else:
                # Fallback if specific revenue fields are missing
                start_revenue = Decimal(str(latest_entry.get("revenue") or 0))
                if is_quarterly:
                    start_revenue *= 4
        else:
            # Fallback to original logic if no quarterly data found
            start_revenue = Decimal(str(latest_entry.get("revenue") or 0))
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
        if year == 1:
            growth_rate = get_assumption("revenue_growth_stage1")
            margin = get_assumption("ebita_margin_stage1")
            mct = assumptions.get("marginal_capital_turnover_stage1")
        elif year <= 5:
            # Interpolate Growth between Year 1 (Stage 1) and Year 6 (Stage 2)
            g1 = get_assumption("revenue_growth_stage1")
            g2 = get_assumption("revenue_growth_stage2")
            growth_rate = g1 + ((g2 - g1) / 5) * (Decimal(year) - 1)

            # Keep Margin/MCT constant for Stage 1 (or we could smooth them too, but req only specified revenue)
            margin = get_assumption("ebita_margin_stage1")
            mct = assumptions.get("marginal_capital_turnover_stage1")
        elif year == 6:
            growth_rate = get_assumption("revenue_growth_stage2")
            margin = get_assumption("ebita_margin_stage2")
            mct = assumptions.get("marginal_capital_turnover_stage2")
        else:
            # Interpolate Growth between Year 6 (Stage 2) and Year 11 (Terminal)
            g2 = get_assumption("revenue_growth_stage2")
            g_terminal = get_assumption("revenue_growth_terminal")
            growth_rate = g2 + ((g_terminal - g2) / 5) * (Decimal(year) - 6)

            margin = get_assumption("ebita_margin_stage2")
            mct = assumptions.get("marginal_capital_turnover_stage2")

        # Fallback for MCT if not set
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
        # (Based on User input: Turnover = Rev/IC, so Delta IC = Delta Rev / MCT)
        if mct != 0:
            delta_ic = delta_revenue / mct
        else:
            delta_ic = Decimal(0)

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

    # Prepare base year data (Year 0)
    # Revenue, EBITA, NOPAT need to be derived from latest_entry or consistent with start_revenue
    # start_revenue is already prepared (annualized if needed)

    # We need EBITA and NOPAT for Year 0 to display complete column
    # Use latest entry's actuals if available, or derive from margin?
    # Ideally reuse logic from historical_calculations aggregator, but we only have latest_entry dict here.
    # Latest entry has 'ebita', 'nopat', 'invested_capital'?

    base_ebita = latest_entry.get("ebita")
    if base_ebita is None:
        # Fallback: estimate using latest margin?
        # But we don't have a "latest margin" assumption, we have Stage 1 assumption.
        # Let's derive from available revenue if possible, or leave None
        base_ebita = Decimal(0)
    else:
        base_ebita = Decimal(str(base_ebita))
        if is_quarterly:
            base_ebita *= 4  # Annualize if needed

    base_nopat = latest_entry.get("nopat")
    if base_nopat is None:
        # Fallback
        base_nopat = base_ebita * (1 - tax_rate)
    else:
        base_nopat = Decimal(str(base_nopat))
        if is_quarterly:
            base_nopat *= 4

    # Calculate base ROIC
    base_roic = 0
    if start_invested_capital and start_invested_capital != 0:
        base_roic = base_nopat / start_invested_capital

    base_year_data = {
        "year": "Base",  # or 0
        "revenue": start_revenue,
        "growth_rate": None,  # Growth from previous year not calculated here
        "ebita": base_ebita,
        "nopat": base_nopat,
        "invested_capital": start_invested_capital,
        "roic": base_roic,
        "fcf": None,  # FCF for base year usually not relevant for DCF sum
        "discount_factor": None,
        "pv_fcf": None,
    }

    # Terminal Value Calculation
    # User Request:
    # 1. Delta IC = Delta Revenue / MCT
    # 2. FCF = NOPAT - Delta IC

    # Terminal Year Assumptions
    g_terminal = get_assumption("revenue_growth_terminal")
    margin_terminal = get_assumption("ebita_margin_terminal")
    mct_terminal = assumptions.get("marginal_capital_turnover_terminal")
    if mct_terminal is None:
        mct_terminal = avg_capital_turnover
    else:
        mct_terminal = Decimal(str(mct_terminal))

    # Year 11 (Terminal Year) Values
    revenue_terminal = current_revenue * (1 + g_terminal)
    ebita_terminal = revenue_terminal * margin_terminal
    nopat_terminal = ebita_terminal * (1 - tax_rate)

    # Marginal ROIC (RONIC)
    # RONIC = Margin * (1 - Tax) * MCT (Turnover)
    ronic = margin_terminal * (1 - tax_rate) * mct_terminal

    # Reinvestment Rate Calculation
    # Formula: reinvestment_rate = terminal_g / (terminal_ebita_margin * (1 - tax_rate) * terminal_capital_turnover)
    # This matches exactly with IR = g / RONIC
    if ronic != 0:
        reinvestment_rate = g_terminal / ronic
    else:
        reinvestment_rate = 0

    # Terminal FCF using Value Driver Formula logic
    # Formula: fcf = nopat * (1 - reinvestment_rate)
    fcf_terminal = nopat_terminal * (1 - reinvestment_rate)

    # Calculate Terminal Invested Capital for display
    # If we assume FCF = NOPAT - Net Investment, then Net Investment = NOPAT * IR
    net_investment_terminal = nopat_terminal * reinvestment_rate
    invested_capital_terminal = current_invested_capital + net_investment_terminal

    # ROIC for Terminal Year display (Average ROIC)
    roic_terminal = nopat_terminal / invested_capital_terminal if invested_capital_terminal else 0

    # Terminal Value (at end of Year 10)
    # User Formula: terminal_value = (nopat * (1 + terminal_g) * (1 - reinvestment_rate)) / (wacc - terminal_g)
    # nopat_terminal is already (nopat_10 * (1+g)), so we just use nopat_terminal.
    if (wacc - g_terminal) == 0:
        terminal_value = 0
    else:
        terminal_value = fcf_terminal / (wacc - g_terminal)

    # Discount Factor for Terminal Value (Year 10 end)
    # Applying mid-year convention to align with Year 10 cash flow timing (9.5 years)
    discount_factor_tv = 1 / ((1 + wacc) ** (Decimal(years_to_project) - Decimal("0.5")))

    # PV of Terminal Value
    pv_terminal_value = terminal_value * discount_factor_tv

    sum_pv_fcf = sum(p["pv_fcf"] for p in projections)
    enterprise_value = sum_pv_fcf + pv_terminal_value

    return {
        "base_year": base_year_data,
        "projections": projections,
        "terminal_column": {
            "revenue": revenue_terminal,
            "growth_rate": g_terminal,
            "ebita": ebita_terminal,
            "nopat": nopat_terminal,
            "invested_capital": invested_capital_terminal,
            "roic": roic_terminal,
            "fcf": terminal_value,
            "discount_factor": discount_factor_tv,
            "pv_fcf": pv_terminal_value,
        },
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

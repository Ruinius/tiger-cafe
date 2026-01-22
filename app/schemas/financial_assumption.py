"""
Financial assumption schemas
"""

from decimal import Decimal

from pydantic import BaseModel


class FinancialAssumptionBase(BaseModel):
    revenue_growth_stage1: Decimal | None = None
    revenue_growth_stage2: Decimal | None = None
    revenue_growth_terminal: Decimal | None = None
    ebita_margin_stage1: Decimal | None = None
    ebita_margin_stage2: Decimal | None = None
    ebita_margin_terminal: Decimal | None = None
    marginal_capital_turnover_stage1: Decimal | None = None
    marginal_capital_turnover_stage2: Decimal | None = None
    marginal_capital_turnover_terminal: Decimal | None = None
    beta: Decimal | None = None
    adjusted_tax_rate: Decimal | None = None
    wacc: Decimal | None = None
    diluted_shares_outstanding: Decimal | None = None
    base_revenue: Decimal | None = None
    weight_of_equity: Decimal | None = None
    cost_of_debt: Decimal | None = None
    calculated_wacc: Decimal | None = None
    market_cap: Decimal | None = None
    currency_conversion_rate: Decimal | None = None
    adr_conversion_factor: Decimal | None = None


class FinancialAssumptionCreate(FinancialAssumptionBase):
    pass


class FinancialAssumption(FinancialAssumptionBase):
    id: str
    company_id: str

    class Config:
        from_attributes = True

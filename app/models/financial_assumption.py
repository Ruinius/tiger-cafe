"""
Financial assumption model
"""

import uuid

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class FinancialAssumption(Base):
    __tablename__ = "financial_assumptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True, unique=True)

    # Revenue Growth
    revenue_growth_stage1 = Column(Numeric(10, 4), nullable=True)  # First 5 years
    revenue_growth_stage2 = Column(Numeric(10, 4), nullable=True)  # Second 5 years
    revenue_growth_terminal = Column(Numeric(10, 4), nullable=True)  # Terminal

    # EBITA Margin
    ebita_margin_stage1 = Column(Numeric(10, 4), nullable=True)
    ebita_margin_stage2 = Column(Numeric(10, 4), nullable=True)
    ebita_margin_terminal = Column(Numeric(10, 4), nullable=True)

    # Marginal Capital Turnover
    marginal_capital_turnover_stage1 = Column(Numeric(10, 4), nullable=True)
    marginal_capital_turnover_stage2 = Column(Numeric(10, 4), nullable=True)
    marginal_capital_turnover_terminal = Column(Numeric(10, 4), nullable=True)

    # WACC Calculations
    beta = Column(Numeric(10, 4), nullable=True)  # Beta from Yahoo Finance

    # Other
    adjusted_tax_rate = Column(Numeric(10, 4), nullable=True)
    wacc = Column(Numeric(10, 4), nullable=True)
    diluted_shares_outstanding = Column(Numeric(20, 2), nullable=True)  # Shares in actual units
    base_revenue = Column(Numeric(20, 2), nullable=True)  # Revenue in actual units

    # Relationship
    company = relationship("Company", back_populates="financial_assumptions")

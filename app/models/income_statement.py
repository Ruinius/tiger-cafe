"""
Income statement model
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class IncomeStatement(Base):
    __tablename__ = "income_statements"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(
        String, ForeignKey("documents.id"), nullable=False, index=True, unique=True
    )

    # Metadata
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    currency = Column(String, nullable=True)  # Local currency code (e.g., "USD", "EUR")
    unit = Column(
        String, nullable=True
    )  # Unit: "ones", "thousands", "millions", "billions", or "ten_thousands" (for foreign stocks)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    # Additional extracted data
    revenue_prior_year = Column(
        Numeric(20, 2), nullable=True
    )  # Revenue for same period in prior year
    revenue_prior_year_unit = Column(String, nullable=True)  # Unit for revenue_prior_year
    revenue_growth_yoy = Column(
        Numeric(10, 4), nullable=True
    )  # Year-over-year revenue growth percentage
    basic_shares_outstanding = Column(Numeric(20, 2), nullable=True)
    basic_shares_outstanding_unit = Column(
        String, nullable=True
    )  # Unit for basic_shares_outstanding (usually "ones")
    diluted_shares_outstanding = Column(Numeric(20, 2), nullable=True)
    diluted_shares_outstanding_unit = Column(
        String, nullable=True
    )  # Unit for diluted_shares_outstanding (usually "ones")
    amortization = Column(Numeric(20, 2), nullable=True)
    amortization_unit = Column(String, nullable=True)  # Unit for amortization

    # Validation flags
    is_valid = Column(Boolean, default=False)  # Whether all validations passed
    validation_errors = Column(Text, nullable=True)  # JSON string of validation errors

    # Relationships
    document = relationship("Document", back_populates="income_statement")
    line_items = relationship(
        "IncomeStatementLineItem", back_populates="income_statement", cascade="all, delete-orphan"
    )


class IncomeStatementLineItem(Base):
    __tablename__ = "income_statement_line_items"

    id = Column(String, primary_key=True, index=True)
    income_statement_id = Column(
        String, ForeignKey("income_statements.id"), nullable=False, index=True
    )

    # Line item details
    line_name = Column(String, nullable=False)  # e.g., "Revenue", "Cost of goods sold"
    line_value = Column(Numeric(20, 2), nullable=False)  # Monetary value
    line_category = Column(String, nullable=True)  # e.g., "Revenue", "Costs", "Expenses", "Income"
    is_operating = Column(Boolean, nullable=True)  # Operating vs non-operating classification
    line_order = Column(
        Integer, nullable=False
    )  # Order in which line appears in the income statement

    # Relationships
    income_statement = relationship("IncomeStatement", back_populates="line_items")

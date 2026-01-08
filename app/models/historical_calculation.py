"""
Historical calculation model for storing calculated financial metrics
"""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class HistoricalCalculation(Base):
    __tablename__ = "historical_calculations"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(
        String, ForeignKey("documents.id"), nullable=False, index=True, unique=True
    )

    # Metadata
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    currency = Column(String, nullable=True)  # Currency code (e.g., "USD", "EUR")
    unit = Column(
        String, nullable=True
    )  # Unit: "ones", "thousands", "millions", "billions", or "ten_thousands"
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Calculated metrics
    net_working_capital = Column(Numeric(20, 2), nullable=True)
    net_long_term_operating_assets = Column(Numeric(20, 2), nullable=True)
    invested_capital = Column(Numeric(20, 2), nullable=True)
    capital_turnover = Column(Numeric(10, 4), nullable=True)
    ebita = Column(Numeric(20, 2), nullable=True)
    ebita_margin = Column(Numeric(10, 4), nullable=True)  # Stored as decimal (e.g., 0.15 for 15%)
    effective_tax_rate = Column(
        Numeric(10, 4), nullable=True
    )  # Stored as decimal (e.g., 0.25 for 25%)
    adjusted_tax_rate = Column(
        Numeric(10, 4), nullable=True
    )  # Stored as decimal (e.g., 0.25 for 25%)
    nopat = Column(Numeric(20, 2), nullable=True)  # Net Operating Profit After Tax
    roic = Column(Numeric(10, 4), nullable=True)  # Return on Invested Capital (decimal)

    # Calculation notes/errors
    calculation_notes = Column(Text, nullable=True)  # JSON string for any notes or warnings
    net_working_capital_breakdown = Column(
        Text, nullable=True
    )  # JSON string for net working capital breakdown
    net_long_term_operating_assets_breakdown = Column(
        Text, nullable=True
    )  # JSON string for net long term operating assets breakdown
    ebita_breakdown = Column(Text, nullable=True)  # JSON string for EBITA breakdown
    adjusted_tax_rate_breakdown = Column(
        Text, nullable=True
    )  # JSON string for adjusted tax rate breakdown

    # Relationships
    document = relationship("Document", back_populates="historical_calculation")

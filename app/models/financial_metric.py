"""
Financial Metric model for storing calculated metrics
"""

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    # Metric identification
    metric_name = Column(
        String, nullable=False, index=True
    )  # e.g., "organic_growth", "operating_margin", "capital_turnover"
    period = Column(String, nullable=False, index=True)  # e.g., "Q3 2023", "FY 2023"
    period_date = Column(Date, nullable=True, index=True)  # Specific date for the period

    # Metric value
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)  # e.g., "percentage", "ratio", "dollars"

    # Metadata
    source_document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    company = relationship("Company", back_populates="financial_metrics")
    source_document = relationship("Document")

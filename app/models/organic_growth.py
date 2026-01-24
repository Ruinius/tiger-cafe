"""
Organic growth extraction models
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class OrganicGrowth(Base):
    __tablename__ = "organic_growth"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    prior_period_revenue = Column(Numeric(20, 2), nullable=True)
    prior_period_revenue_unit = Column(String, nullable=True)
    current_period_revenue = Column(Numeric(20, 2), nullable=True)
    current_period_revenue_unit = Column(String, nullable=True)
    simple_revenue_growth = Column(Numeric(10, 4), nullable=True)
    acquisition_revenue_impact = Column(Numeric(20, 2), nullable=True)
    acquisition_revenue_impact_unit = Column(String, nullable=True)
    current_period_adjusted_revenue = Column(Numeric(20, 2), nullable=True)
    current_period_adjusted_revenue_unit = Column(String, nullable=True)
    organic_revenue_growth = Column(Numeric(10, 4), nullable=True)
    chunk_index = Column(Integer, nullable=True)
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(Text, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="organic_growth")

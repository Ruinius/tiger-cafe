"""
Analysis Result model for storing valuation and analysis results
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Analysis metadata
    analysis_type = Column(String, nullable=False, index=True)  # e.g., "intrinsic_value", "sensitivity", "market_belief"
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Results (stored as JSON for flexibility)
    assumptions = Column(JSON, nullable=True)  # Input assumptions
    results = Column(JSON, nullable=False)  # Calculation results
    
    # Summary
    summary = Column(Text, nullable=True)  # LLM-generated summary
    
    # Relationships
    company = relationship("Company", back_populates="analysis_results")


"""
Company model
"""

import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    ticker = Column(String, nullable=True, index=True, unique=True)  # Stock ticker symbol
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    documents = relationship("Document", back_populates="company", cascade="all, delete-orphan")
    financial_assumptions = relationship(
        "FinancialAssumption", back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
    financial_metrics = relationship(
        "FinancialMetric", back_populates="company", cascade="all, delete-orphan"
    )
    analysis_results = relationship(
        "AnalysisResult", back_populates="company", cascade="all, delete-orphan"
    )
    valuations = relationship("Valuation", back_populates="company", cascade="all, delete-orphan")
    qualitative_assessment = relationship(
        "QualitativeAssessment",
        back_populates="company",
        uselist=False,
        cascade="all, delete-orphan",
    )

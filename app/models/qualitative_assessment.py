"""
Qualitative assessment model
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class QualitativeAssessment(Base):
    __tablename__ = "qualitative_assessments"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True, unique=True)

    # Economic Moat
    economic_moat_label = Column(String, nullable=True)  # Wide, Narrow, None
    economic_moat_rationale = Column(Text, nullable=True)

    # Near-term Growth
    near_term_growth_label = Column(String, nullable=True)  # Faster, Steady, Slower
    near_term_growth_rationale = Column(Text, nullable=True)

    # Revenue Predictability
    revenue_predictability_label = Column(String, nullable=True)  # High, Mid, Low
    revenue_predictability_rationale = Column(Text, nullable=True)

    # Metadata
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="qualitative_assessment")

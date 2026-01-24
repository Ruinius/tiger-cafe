"""
Amortization extraction models
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Amortization(Base):
    __tablename__ = "amortizations"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    chunk_index = Column(Integer, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(String, nullable=True)

    document = relationship("Document", back_populates="amortization")
    line_items = relationship(
        "AmortizationLineItem",
        back_populates="amortization",
        cascade="all, delete-orphan",
    )


class AmortizationLineItem(Base):
    __tablename__ = "amortization_line_items"

    id = Column(String, primary_key=True, index=True)
    amortization_id = Column(String, ForeignKey("amortizations.id"), nullable=False, index=True)

    line_name = Column(String, nullable=False)
    line_value = Column(Numeric(20, 2), nullable=False)
    unit = Column(String, nullable=True)
    is_operating = Column(Boolean, nullable=True)
    category = Column(String, nullable=True)
    line_order = Column(Integer, nullable=False)

    amortization = relationship("Amortization", back_populates="line_items")

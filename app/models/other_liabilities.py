"""
Other liabilities extraction models
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class OtherLiabilities(Base):
    __tablename__ = "other_liabilities"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    chunk_index = Column(Integer, nullable=True)
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(Text, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="other_liabilities")
    line_items = relationship(
        "OtherLiabilitiesLineItem",
        back_populates="other_liabilities",
        cascade="all, delete-orphan",
    )


class OtherLiabilitiesLineItem(Base):
    __tablename__ = "other_liabilities_line_items"

    id = Column(String, primary_key=True, index=True)
    other_liabilities_id = Column(
        String, ForeignKey("other_liabilities.id"), nullable=False, index=True
    )

    line_name = Column(String, nullable=False)
    line_value = Column(Numeric(20, 2), nullable=False)
    unit = Column(String, nullable=True)
    is_operating = Column(Boolean, nullable=True)
    category = Column(String, nullable=True)
    line_order = Column(Integer, nullable=False)

    other_liabilities = relationship("OtherLiabilities", back_populates="line_items")

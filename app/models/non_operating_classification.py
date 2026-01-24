"""
Non-operating classification models
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NonOperatingClassification(Base):
    __tablename__ = "non_operating_classifications"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="non_operating_classification")
    line_items = relationship(
        "NonOperatingClassificationItem",
        back_populates="classification",
        cascade="all, delete-orphan",
    )


class NonOperatingClassificationItem(Base):
    __tablename__ = "non_operating_classification_items"

    id = Column(String, primary_key=True, index=True)
    classification_id = Column(
        String, ForeignKey("non_operating_classifications.id"), nullable=False, index=True
    )

    line_name = Column(String, nullable=False)  # Used to match back to balance sheet
    category = Column(String, nullable=True)  # Non-operating category (cash, debt, equity, etc.)
    source = Column(
        String, nullable=True
    )  # Source table (balance_sheet, other_assets, other_liabilities)
    line_order = Column(Integer, nullable=False)

    classification = relationship("NonOperatingClassification", back_populates="line_items")

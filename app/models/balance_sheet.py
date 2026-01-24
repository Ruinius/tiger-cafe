"""
Balance sheet model
"""

import enum

import sqlalchemy
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class LineItemType(str, enum.Enum):
    OPERATING = "operating"
    NON_OPERATING = "non_operating"


class BalanceSheet(Base):
    __tablename__ = "balance_sheets"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    # Metadata
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    period_end_date = Column(String, nullable=True)  # e.g., "2024-03-31" (YYYY-MM-DD)
    currency = Column(String, nullable=True)  # Local currency code (e.g., "USD", "EUR")
    unit = Column(
        String, nullable=True
    )  # Unit: "ones", "thousands", "millions", "billions", or "ten_thousands" (for foreign stocks)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    # Validation flags
    is_valid = Column(Boolean, default=False)  # Whether all validations passed
    validation_errors = Column(Text, nullable=True)  # JSON string of validation errors

    # Extraction metadata
    chunk_index = Column(
        Integer, nullable=True
    )  # Chunk index used for extraction (for traceability and observability)

    # Relationships
    document = relationship("Document", back_populates="balance_sheet")
    line_items = relationship(
        "BalanceSheetLineItem", back_populates="balance_sheet", cascade="all, delete-orphan"
    )


class BalanceSheetLineItem(Base):
    __tablename__ = "balance_sheet_line_items"

    id = Column(String, primary_key=True, index=True)
    balance_sheet_id = Column(String, ForeignKey("balance_sheets.id"), nullable=False, index=True)

    # Line item details
    line_name = Column(String, nullable=False)  # e.g., "Cash and cash equivalents"
    line_value = Column(Numeric(20, 2), nullable=False)  # Monetary value
    line_category = Column(
        String, nullable=True
    )  # Section token (e.g., "current_assets", "stockholders_equity") - input to transformer
    standardized_name = Column(
        String, nullable=True
    )  # Standardized key from transformer (e.g., "cash_and_equivalents")
    is_calculated = Column(
        Boolean, nullable=True
    )  # Flag indicating if value is a calculated total/subtotal
    is_operating = Column(Boolean, nullable=True)  # Operating vs non-operating classification
    line_order = Column(Integer, nullable=False)  # Order in which line appears in the balance sheet

    # Relationships
    balance_sheet = relationship("BalanceSheet", back_populates="line_items")

    __table_args__ = (
        # Ensure line_order is unique per balance sheet to prevent duplicates
        # This prevents application bugs from double-inserting line items
        sqlalchemy.UniqueConstraint("balance_sheet_id", "line_order", name="uq_bs_line_item_order"),
    )

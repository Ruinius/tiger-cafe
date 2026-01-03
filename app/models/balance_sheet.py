"""
Balance sheet model
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Numeric, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class LineItemType(enum.Enum):
    OPERATING = "operating"
    NON_OPERATING = "non_operating"


class BalanceSheet(Base):
    __tablename__ = "balance_sheets"
    
    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    
    # Metadata
    time_period = Column(String, nullable=True)  # e.g., "Q3 2023", "FY 2023"
    currency = Column(String, nullable=True)  # Local currency code (e.g., "USD", "EUR")
    unit = Column(String, nullable=True)  # Unit: "ones", "thousands", "millions", "billions", or "ten_thousands" (for foreign stocks)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Validation flags
    is_valid = Column(Boolean, default=False)  # Whether all validations passed
    validation_errors = Column(Text, nullable=True)  # JSON string of validation errors
    
    # Relationships
    document = relationship("Document", back_populates="balance_sheet")
    line_items = relationship("BalanceSheetLineItem", back_populates="balance_sheet", cascade="all, delete-orphan")


class BalanceSheetLineItem(Base):
    __tablename__ = "balance_sheet_line_items"
    
    id = Column(String, primary_key=True, index=True)
    balance_sheet_id = Column(String, ForeignKey("balance_sheets.id"), nullable=False, index=True)
    
    # Line item details
    line_name = Column(String, nullable=False)  # e.g., "Cash and cash equivalents"
    line_value = Column(Numeric(20, 2), nullable=False)  # Monetary value
    line_category = Column(String, nullable=True)  # e.g., "Current Assets", "Total Assets", "Current Liabilities"
    is_operating = Column(Boolean, nullable=True)  # Operating vs non-operating classification
    line_order = Column(Integer, nullable=False)  # Order in which line appears in the balance sheet
    
    # Relationships
    balance_sheet = relationship("BalanceSheet", back_populates="line_items")



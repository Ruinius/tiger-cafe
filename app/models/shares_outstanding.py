"""
Shares outstanding model
"""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SharesOutstanding(Base):
    __tablename__ = "shares_outstanding"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(
        String, ForeignKey("documents.id"), nullable=False, index=True, unique=True
    )

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)

    # Values from extractor
    basic_shares_outstanding = Column(Numeric(20, 2), nullable=True)
    basic_shares_outstanding_unit = Column(String, nullable=True)
    diluted_shares_outstanding = Column(Numeric(20, 2), nullable=True)
    diluted_shares_outstanding_unit = Column(String, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="shares_outstanding")

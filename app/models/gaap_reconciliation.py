"""
GAAP Reconciliation extraction models
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GAAPReconciliation(Base):
    __tablename__ = "gaap_reconciliations"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    time_period = Column(String, nullable=True)
    period_end_date = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    chunk_index = Column(Integer, nullable=True)
    extraction_date = Column(DateTime(timezone=True), server_default=func.now())
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(String, nullable=True)

    document = relationship("Document", back_populates="gaap_reconciliation")
    line_items = relationship(
        "GAAPReconciliationLineItem",
        back_populates="gaap_reconciliation",
        cascade="all, delete-orphan",
    )


class GAAPReconciliationLineItem(Base):
    __tablename__ = "gaap_reconciliation_line_items"

    id = Column(String, primary_key=True, index=True)
    gaap_reconciliation_id = Column(
        String, ForeignKey("gaap_reconciliations.id"), nullable=False, index=True
    )

    line_name = Column(String, nullable=False)
    line_value = Column(Numeric(20, 2), nullable=False)
    unit = Column(String, nullable=True)
    is_operating = Column(Boolean, nullable=True)
    category = Column(String, nullable=True)
    line_order = Column(Integer, nullable=False)

    gaap_reconciliation = relationship("GAAPReconciliation", back_populates="line_items")

    __table_args__ = (
        UniqueConstraint(
            "gaap_reconciliation_id", "line_order", name="uq_gaap_recon_id_line_order"
        ),
    )

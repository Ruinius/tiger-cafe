from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Valuation(Base):
    __tablename__ = "valuations"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    date = Column(DateTime(timezone=True), server_default=func.now())
    fair_value = Column(Numeric(20, 2), nullable=False)
    share_price_at_time = Column(Numeric(20, 2), nullable=True)
    percent_undervalued = Column(Numeric(10, 4), nullable=True)

    company = relationship("Company", back_populates="valuations")
    user = relationship("User", back_populates="valuations")

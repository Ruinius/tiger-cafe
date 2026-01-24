"""
Organic growth schemas
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrganicGrowthBase(BaseModel):
    time_period: str | None = None
    period_end_date: str | None = None
    currency: str | None = None
    prior_period_revenue: Decimal | None = None
    prior_period_revenue_unit: str | None = None
    current_period_revenue: Decimal | None = None
    current_period_revenue_unit: str | None = None
    simple_revenue_growth: Decimal | None = None
    acquisition_revenue_impact: Decimal | None = None
    acquisition_revenue_impact_unit: str | None = None
    current_period_adjusted_revenue: Decimal | None = None
    current_period_adjusted_revenue_unit: str | None = None
    organic_revenue_growth: Decimal | None = None
    chunk_index: int | None = None
    is_valid: bool = False
    validation_errors: str | None = None


class OrganicGrowthCreate(OrganicGrowthBase):
    document_id: str


class OrganicGrowth(OrganicGrowthBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    extraction_date: datetime | None = None

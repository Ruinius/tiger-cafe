from datetime import datetime

from pydantic import BaseModel


class ValuationBase(BaseModel):
    fair_value: float
    share_price_at_time: float | None = None
    percent_undervalued: float | None = None


class ValuationCreate(ValuationBase):
    pass


class Valuation(ValuationBase):
    id: str
    company_id: str
    user_id: str | None = None
    date: datetime
    user_email: str | None = None  # To display user name/email
    user_name: str | None = None  # To display user name

    class Config:
        from_attributes = True

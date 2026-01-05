"""
User schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None
    picture: str | None = None


class UserCreate(UserBase):
    id: str  # Google user ID


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool

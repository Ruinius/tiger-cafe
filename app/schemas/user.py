"""
User schemas
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = None
    picture: str | None = None


class UserCreate(UserBase):
    id: str  # Google user ID


class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool

    class Config:
        from_attributes = True

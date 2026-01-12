"""
User schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    auth_provider: str
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool

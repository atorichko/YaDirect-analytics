from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserPublic(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool


class UserCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    role: UserRole = UserRole.specialist
    password: str = Field(min_length=8, max_length=128)


class UserCreateResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool


class UserUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=128)

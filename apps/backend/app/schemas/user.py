from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserPublic(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    role: UserRole
    is_active: bool

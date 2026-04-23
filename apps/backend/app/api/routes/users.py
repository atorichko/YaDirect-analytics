from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin, get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserListItem, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def read_me(user: CurrentUser) -> User:
    return user


@router.get("", response_model=list[UserListItem])
async def list_users(
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserListItem]:
    repo = UserRepository(session)
    users = await repo.list_users()
    return [UserListItem.model_validate(u) for u in users]

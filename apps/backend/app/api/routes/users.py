from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin, get_db
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreateRequest, UserCreateResponse, UserListItem, UserPublic, UserUpdateRequest

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


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserCreateResponse:
    repo = UserRepository(session)
    existing = await repo.get_by_email(body.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    user = await repo.create(
        full_name=body.full_name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    await session.commit()
    return UserCreateResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await repo.delete(user)
    await session.commit()


@router.put("/{user_id}", response_model=UserCreateResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserCreateResponse:
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    duplicate = await repo.get_by_email(body.email)
    if duplicate is not None and duplicate.id != user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    user.full_name = body.full_name.strip()
    user.email = body.email.lower().strip()
    if body.password:
        user.hashed_password = hash_password(body.password)
    await session.commit()
    await session.refresh(user)
    return UserCreateResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )

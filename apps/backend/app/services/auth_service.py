from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    parse_user_id_from_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPairResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def login(self, email: str, password: str) -> TokenPairResponse:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            msg = "Incorrect email or password"
            raise PermissionError(msg)
        if not verify_password(password, user.hashed_password):
            msg = "Incorrect email or password"
            raise PermissionError(msg)
        return TokenPairResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> TokenPairResponse:
        user_id = parse_user_id_from_token(refresh_token, "refresh")
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            msg = "Invalid refresh token"
            raise PermissionError(msg)
        return TokenPairResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def get_active_user(self, user_id: UUID) -> User | None:
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user

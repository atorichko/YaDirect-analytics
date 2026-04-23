from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.get(User, user_id)
        return result

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, *, full_name: str, email: str, hashed_password: str, role: UserRole) -> User:
        user = User(
            full_name=full_name.strip(),
            email=email.lower().strip(),
            hashed_password=hashed_password,
            role=role,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self._session.delete(user)

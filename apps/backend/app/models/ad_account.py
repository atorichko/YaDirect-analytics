from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ad_accounts"

    external_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    login: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="yandex_direct")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Moscow")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

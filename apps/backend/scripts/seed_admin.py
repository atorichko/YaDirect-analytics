"""Create or update the bootstrap admin user (idempotent)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def main() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com").lower().strip()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMeNow123!")
    if len(password) < 8:
        msg = "SEED_ADMIN_PASSWORD must be at least 8 characters"
        raise SystemExit(msg)

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with SessionLocal() as session:
        stmt = select(User).where(User.email == email)
        user = session.execute(stmt).scalar_one_or_none()
        hashed = hash_password(password)
        if user is None:
            user = User(
                email=email,
                hashed_password=hashed,
                role=UserRole.admin,
                is_active=True,
            )
            session.add(user)
            print(f"Created admin user {email}")
        else:
            user.hashed_password = hashed
            user.role = UserRole.admin
            user.is_active = True
            print(f"Updated admin user {email}")
        session.commit()


if __name__ == "__main__":
    main()

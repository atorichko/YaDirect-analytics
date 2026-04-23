from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    data = plain.encode("utf-8")
    hashed = bcrypt.hashpw(data, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _encode_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any]) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **extra,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return _encode_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.jwt_access_expire_minutes),
        {},
    )


def create_refresh_token(user_id: UUID) -> str:
    return _encode_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.jwt_refresh_expire_days),
        {},
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def parse_user_id_from_token(token: str, expected_type: str) -> UUID:
    try:
        payload = decode_token(token)
    except JWTError as exc:
        msg = "Invalid token"
        raise ValueError(msg) from exc
    if payload.get("type") != expected_type:
        msg = "Invalid token type"
        raise ValueError(msg)
    sub = payload.get("sub")
    if not sub:
        msg = "Missing subject"
        raise ValueError(msg)
    return UUID(str(sub))

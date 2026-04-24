import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

ENCRYPTED_PREFIX = "enc:v1:"


def _raw_secret() -> str:
    return (settings.oauth_token_encryption_key or settings.jwt_secret_key).strip()


def _fernet() -> Fernet:
    digest = hashlib.sha256(_raw_secret().encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token(value: str) -> str:
    if not value:
        return value
    if value.startswith(ENCRYPTED_PREFIX):
        return value
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{encrypted}"


def decrypt_token(value: str | None) -> str | None:
    if value is None:
        return None
    if not value:
        return value
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    cipher = value[len(ENCRYPTED_PREFIX) :]
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt OAuth token") from exc

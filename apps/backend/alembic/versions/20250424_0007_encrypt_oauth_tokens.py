"""encrypt existing oauth tokens in account_credentials

Revision ID: 20250424_0007
Revises: 20250423_0006
Create Date: 2025-04-24
"""

import base64
import hashlib
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision: str = "20250424_0007"
down_revision: Union[str, Sequence[str], None] = "20250423_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENCRYPTED_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw_secret = (os.getenv("OAUTH_TOKEN_ENCRYPTION_KEY") or os.getenv("JWT_SECRET_KEY") or "").strip()
    if not raw_secret:
        raise RuntimeError(
            "OAUTH_TOKEN_ENCRYPTION_KEY or JWT_SECRET_KEY must be set to encrypt existing OAuth tokens"
        )
    digest = hashlib.sha256(raw_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_if_needed(value: str | None, fernet: Fernet) -> str | None:
    if value is None or value == "" or value.startswith(ENCRYPTED_PREFIX):
        return value
    return f"{ENCRYPTED_PREFIX}{fernet.encrypt(value.encode('utf-8')).decode('utf-8')}"


def _decrypt_if_needed(value: str | None, fernet: Fernet) -> str | None:
    if value is None or value == "":
        return value
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    cipher = value[len(ENCRYPTED_PREFIX) :]
    return fernet.decrypt(cipher.encode("utf-8")).decode("utf-8")


def upgrade() -> None:
    bind = op.get_bind()
    fernet = _fernet()
    rows = bind.execute(sa.text("SELECT id, access_token_encrypted, refresh_token_encrypted FROM account_credentials"))
    for row in rows:
        access_token = _encrypt_if_needed(row.access_token_encrypted, fernet)
        refresh_token = _encrypt_if_needed(row.refresh_token_encrypted, fernet)
        bind.execute(
            sa.text(
                """
                UPDATE account_credentials
                SET access_token_encrypted = :access_token,
                    refresh_token_encrypted = :refresh_token
                WHERE id = :id
                """
            ),
            {"id": row.id, "access_token": access_token, "refresh_token": refresh_token},
        )


def downgrade() -> None:
    bind = op.get_bind()
    fernet = _fernet()
    rows = bind.execute(sa.text("SELECT id, access_token_encrypted, refresh_token_encrypted FROM account_credentials"))
    for row in rows:
        access_token = _decrypt_if_needed(row.access_token_encrypted, fernet)
        refresh_token = _decrypt_if_needed(row.refresh_token_encrypted, fernet)
        bind.execute(
            sa.text(
                """
                UPDATE account_credentials
                SET access_token_encrypted = :access_token,
                    refresh_token_encrypted = :refresh_token
                WHERE id = :id
                """
            ),
            {"id": row.id, "access_token": access_token, "refresh_token": refresh_token},
        )

from app.core.security import create_access_token, hash_password, parse_user_id_from_token, verify_password
from app.core.oauth_token_crypto import decrypt_token, encrypt_token


def test_hash_and_verify_roundtrip() -> None:
    plain = "correct horse battery staple"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip() -> None:
    from uuid import uuid4

    user_id = uuid4()
    token = create_access_token(user_id)
    parsed = parse_user_id_from_token(token, "access")
    assert parsed == user_id


def test_oauth_token_encryption_roundtrip() -> None:
    token = "y0_AQAAAABCD123_example"
    encrypted = encrypt_token(token)
    assert encrypted != token
    assert encrypted.startswith("enc:v1:")
    assert decrypt_token(encrypted) == token


def test_oauth_token_plaintext_backward_compatibility() -> None:
    legacy_plaintext = "legacy-plain-token"
    assert decrypt_token(legacy_plaintext) == legacy_plaintext

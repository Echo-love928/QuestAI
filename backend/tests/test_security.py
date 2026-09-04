from datetime import timedelta

import pytest
import jwt

from app.core.security import TokenError, TokenManager


def test_token_round_trip() -> None:
    manager = TokenManager("test-secret-with-at-least-32-characters")

    token = manager.create_access_token(user_id=42)

    claims = manager.decode_access_token(token)
    assert claims.user_id == 42
    assert claims.token_version == 0
    unverified = jwt.decode(token, options={"verify_signature": False})
    assert "openid" not in unverified


def test_tampered_token_is_rejected() -> None:
    manager = TokenManager("test-secret-with-at-least-32-characters")
    token = manager.create_access_token(user_id=42)

    with pytest.raises(TokenError):
        manager.decode_access_token(f"{token}broken")


def test_expired_token_is_rejected() -> None:
    manager = TokenManager(
        "test-secret-with-at-least-32-characters",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenError):
        manager.decode_access_token(manager.create_access_token(user_id=42))

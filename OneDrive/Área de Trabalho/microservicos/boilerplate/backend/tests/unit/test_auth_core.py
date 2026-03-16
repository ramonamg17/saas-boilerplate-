"""
Unit tests for core/auth.py — JWT, token hashing, expiry.
"""

import time
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.auth import (
    create_jwt,
    decode_jwt,
    hash_token,
    create_magic_link_token,
    verify_magic_link_token,
)


# ── JWT ───────────────────────────────────────────────────────────────

def test_create_and_decode_jwt():
    token = create_jwt({"sub": "42", "email": "a@b.com"})
    payload = decode_jwt(token)
    assert payload["sub"] == "42"
    assert payload["email"] == "a@b.com"
    assert "exp" in payload


def test_decode_invalid_jwt_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt("not.a.token")
    assert exc_info.value.status_code == 401


def test_decode_expired_jwt_raises():
    from fastapi import HTTPException
    import os
    os.environ["JWT_EXPIRE_MINUTES"] = "-1"  # Already expired

    # Create a token with a past expiry manually
    from jose import jwt as jose_jwt
    import backend.config as cfg
    # Reload settings to pick up env change isn't easy; use jose directly
    from datetime import timedelta
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    token = jose_jwt.encode(payload, "test-secret-key", algorithm="HS256")

    with pytest.raises(HTTPException):
        decode_jwt(token)


# ── Token hashing ─────────────────────────────────────────────────────

def test_hash_token_deterministic():
    raw = "my-raw-token"
    assert hash_token(raw) == hash_token(raw)


def test_hash_token_length():
    result = hash_token("abc")
    assert len(result) == 64  # SHA-256 hex


def test_hash_token_different_inputs_differ():
    assert hash_token("token-a") != hash_token("token-b")


# ── Magic link (mocked DB) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_magic_link_token_returns_string():
    from backend.models.user import User, MagicLinkToken

    mock_user = User(id=1, email="test@example.com", plan="free")
    mock_db = AsyncMock()

    # Mock create_or_get_user
    with patch("backend.core.auth.create_or_get_user", return_value=mock_user):
        token = await create_magic_link_token("test@example.com", mock_db)

    assert isinstance(token, str)
    assert len(token) > 20
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called()


@pytest.mark.asyncio
async def test_verify_magic_link_invalid_token():
    from fastapi import HTTPException

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await verify_magic_link_token("invalid-token", mock_db)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_magic_link_used_token():
    from fastapi import HTTPException
    from backend.models.user import MagicLinkToken
    from datetime import timedelta

    used_token = MagicLinkToken(
        id=1,
        user_id=1,
        token_hash=hash_token("raw"),
        used=True,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = used_token
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await verify_magic_link_token("raw", mock_db)
    assert exc_info.value.status_code == 400
    assert "used" in exc_info.value.detail.lower()

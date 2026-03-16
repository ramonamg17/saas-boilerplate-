"""
Integration tests for auth routes.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.models.user import User
from backend.tests.conftest import auth_headers, make_token


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_send_magic_link(client):
    with (
        patch("backend.routers.auth.create_magic_link_token", return_value="raw-token"),
        patch("backend.routers.auth.send_magic_link", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/auth/magic-link", json={"email": "test@example.com"})
    assert resp.status_code == 200
    assert "Magic link sent" in resp.json()["message"]


@pytest.mark.asyncio
async def test_verify_magic_link(client, db):
    # Create a user
    user = User(email="verify@example.com", plan="free")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with (
        patch("backend.routers.auth.verify_magic_link_token", return_value="verify@example.com"),
        patch("backend.routers.auth.send_welcome", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/auth/verify", json={"token": "raw-token"})

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_me_authenticated(client, regular_user):
    resp = await client.get("/api/auth/me", headers=auth_headers(regular_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == regular_user.email
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guest_migrate(client, regular_user):
    resp = await client.post(
        "/api/auth/guest/migrate",
        json={"guest_session_id": "guest-123"},
        headers=auth_headers(regular_user),
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == regular_user.id


@pytest.mark.asyncio
async def test_google_auth_redirect_no_client_id(client):
    resp = await client.get("/api/auth/google")
    assert resp.status_code == 400

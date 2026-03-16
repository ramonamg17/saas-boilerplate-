"""
Integration tests for user routes.
"""

import pytest
from unittest.mock import AsyncMock, patch

from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_get_settings(client, regular_user):
    resp = await client.get("/api/user/settings", headers=auth_headers(regular_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == regular_user.email
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_get_settings_unauthenticated(client):
    resp = await client.get("/api/user/settings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_settings(client, regular_user):
    resp = await client.patch(
        "/api/user/settings",
        json={"name": "New Name"},
        headers=auth_headers(regular_user),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Settings updated"


@pytest.mark.asyncio
async def test_update_settings_name_persists(client, regular_user, db):
    await client.patch(
        "/api/user/settings",
        json={"name": "Updated Name"},
        headers=auth_headers(regular_user),
    )
    await db.refresh(regular_user)
    assert regular_user.name == "Updated Name"


@pytest.mark.asyncio
async def test_contact_sends_email(client, regular_user):
    with patch("backend.core.email.send_support_received", new_callable=AsyncMock):
        resp = await client.post(
            "/api/user/contact",
            json={"message": "I need help with X"},
            headers=auth_headers(regular_user),
        )
    assert resp.status_code == 200
    assert "sent" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_contact_requires_auth(client):
    resp = await client.post("/api/user/contact", json={"message": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_confirmation(client, regular_user):
    resp = await client.request(
        "DELETE",
        "/api/user/account",
        json={"confirmation": "WRONG"},
        headers=auth_headers(regular_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_account_correct_confirmation(client, regular_user, db):
    resp = await client.request(
        "DELETE",
        "/api/user/account",
        json={"confirmation": "DELETE"},
        headers=auth_headers(regular_user),
    )
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_plans(client, regular_user):
    resp = await client.get("/api/user/plans", headers=auth_headers(regular_user))
    assert resp.status_code == 200
    assert "plans" in resp.json()

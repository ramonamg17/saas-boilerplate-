"""
Integration tests for admin routes.
"""

import pytest
from unittest.mock import patch

from backend.models.user import User
from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_list_users_as_admin(client, admin_user, regular_user):
    resp = await client.get("/api/admin/users", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    emails = [u["email"] for u in data["users"]]
    assert regular_user.email in emails


@pytest.mark.asyncio
async def test_list_users_forbidden_for_regular_user(client, regular_user):
    resp = await client.get("/api/admin/users", headers=auth_headers(regular_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthenticated(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_user_detail(client, admin_user, regular_user):
    resp = await client.get(
        f"/api/admin/users/{regular_user.id}",
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == regular_user.email


@pytest.mark.asyncio
async def test_get_user_detail_not_found(client, admin_user):
    resp = await client.get("/api/admin/users/99999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_override_plan(client, admin_user, regular_user, db):
    resp = await client.post(
        f"/api/admin/users/{regular_user.id}/plan",
        json={"plan_key": "pro"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    await db.refresh(regular_user)
    assert regular_user.plan == "pro"


@pytest.mark.asyncio
async def test_impersonate_user(client, admin_user, regular_user):
    resp = await client.post(
        f"/api/admin/users/{regular_user.id}/impersonate",
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["impersonating"] == regular_user.email


@pytest.mark.asyncio
async def test_impersonate_token_has_context(client, admin_user, regular_user):
    resp = await client.post(
        f"/api/admin/users/{regular_user.id}/impersonate",
        headers=auth_headers(admin_user),
    )
    token = resp.json()["access_token"]
    from backend.core.auth import decode_jwt
    payload = decode_jwt(token)
    assert payload["impersonating"] is True
    assert payload["admin_id"] == admin_user.id


@pytest.mark.asyncio
async def test_admin_stats(client, admin_user, regular_user):
    resp = await client.get("/api/admin/stats", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] >= 2
    assert "active_subscriptions" in data
    assert "new_users_today" in data


@pytest.mark.asyncio
async def test_filter_users_by_plan(client, admin_user, regular_user):
    resp = await client.get(
        "/api/admin/users?plan=free",
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    users = resp.json()["users"]
    assert all(u["plan"] == "free" for u in users)


@pytest.mark.asyncio
async def test_search_users_by_email(client, admin_user, regular_user):
    resp = await client.get(
        f"/api/admin/users?search={regular_user.email[:5]}",
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    users = resp.json()["users"]
    assert any(u["email"] == regular_user.email for u in users)

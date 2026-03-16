"""
Integration tests for billing routes.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.user import User
from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_list_plans_public(client):
    resp = await client.get("/api/billing/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert "plans" in data
    assert len(data["plans"]) >= 2


@pytest.mark.asyncio
async def test_billing_status_authenticated(client, regular_user):
    resp = await client.get("/api/billing/status", headers=auth_headers(regular_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_billing_status_unauthenticated(client):
    resp = await client.get("/api/billing/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_checkout_creates_session(client, regular_user):
    with patch(
        "backend.routers.billing.create_checkout_session",
        new_callable=AsyncMock,
        return_value="https://checkout.stripe.com/test",
    ):
        resp = await client.post(
            "/api/billing/checkout",
            json={"plan_key": "pro"},
            headers=auth_headers(regular_user),
        )
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.com/test"


@pytest.mark.asyncio
async def test_checkout_requires_auth(client):
    resp = await client.post("/api/billing/checkout", json={"plan_key": "pro"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cancel_no_subscription_raises(client, regular_user):
    from fastapi import HTTPException

    with patch(
        "backend.routers.billing.cancel_subscription",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=400, detail="No active subscription"),
    ):
        resp = await client.post(
            "/api/billing/cancel",
            json={"reason": "too_expensive"},
            headers=auth_headers(regular_user),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_invalid_signature(client):
    resp = await client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "invalid"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_checkout_completed(client, db, regular_user):
    # Give user a stripe customer ID
    regular_user.stripe_customer_id = "cus_test"
    await db.commit()

    event_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test",
                "subscription": "sub_test123",
                "metadata": {"user_id": str(regular_user.id), "plan_key": "pro"},
            }
        },
    }

    with (
        patch("stripe.Webhook.construct_event", return_value=event_payload),
        patch("backend.core.email.send_subscription_confirmed", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/billing/webhook",
            content=json.dumps(event_payload).encode(),
            headers={"stripe-signature": "test"},
        )

    assert resp.status_code == 200
    assert resp.json()["received"] is True

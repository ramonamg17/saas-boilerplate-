"""
Unit tests for billing — plan lookup, limit checks (mocked Stripe).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.plans import get_plan, get_plan_limit, all_plans, PLANS


# ── Plan lookup ───────────────────────────────────────────────────────

def test_get_plan_known_key():
    plan = get_plan("free")
    assert plan["key"] == "free"
    assert plan["price"] == 0.0


def test_get_plan_pro():
    plan = get_plan("pro")
    assert plan["key"] == "pro"
    assert plan["price"] > 0


def test_get_plan_unknown_falls_back_to_free():
    plan = get_plan("nonexistent")
    assert plan["key"] == "free"


def test_all_plans_returns_list():
    plans = all_plans()
    assert isinstance(plans, list)
    assert len(plans) >= 2


# ── Limit checks ──────────────────────────────────────────────────────

def test_get_plan_limit_free():
    limit = get_plan_limit("free", "requests_per_hour")
    assert limit == 20


def test_get_plan_limit_pro():
    limit = get_plan_limit("pro", "requests_per_hour")
    assert limit == 500


def test_get_plan_limit_unknown_limit_returns_zero():
    result = get_plan_limit("pro", "nonexistent_limit")
    assert result == 0


# ── Billing functions (mocked Stripe) ────────────────────────────────

@pytest.mark.asyncio
async def test_create_stripe_customer():
    with patch("stripe.Customer.create") as mock_create:
        mock_create.return_value = MagicMock(id="cus_test123")
        from backend.core.billing import create_stripe_customer
        cid = await create_stripe_customer("test@example.com")
    assert cid == "cus_test123"
    mock_create.assert_called_once_with(email="test@example.com")


@pytest.mark.asyncio
async def test_create_checkout_session():
    from backend.models.user import User

    user = User(id=1, email="u@example.com", stripe_customer_id="cus_existing", plan="free")

    with patch("stripe.checkout.Session.create") as mock_session:
        mock_session.return_value = MagicMock(url="https://checkout.stripe.com/test")
        from backend.core.billing import create_checkout_session
        url = await create_checkout_session(user, "pro")

    assert url == "https://checkout.stripe.com/test"
    mock_session.assert_called_once()


@pytest.mark.asyncio
async def test_create_checkout_session_no_price_id_raises():
    from fastapi import HTTPException
    from backend.models.user import User

    user = User(id=1, email="u@example.com", stripe_customer_id="cus_x", plan="free")

    # Temporarily wipe price ID
    original = PLANS["pro"]["stripe_price_id"]
    PLANS["pro"]["stripe_price_id"] = ""
    try:
        # "free" plan has no price ID
        from backend.core.billing import create_checkout_session
        with pytest.raises(HTTPException):
            await create_checkout_session(user, "free")
    finally:
        PLANS["pro"]["stripe_price_id"] = original


@pytest.mark.asyncio
async def test_create_billing_portal_no_customer_raises():
    from fastapi import HTTPException
    from backend.models.user import User

    user = User(id=1, email="u@example.com", stripe_customer_id=None, plan="free")

    from backend.core.billing import create_billing_portal
    with pytest.raises(HTTPException) as exc_info:
        await create_billing_portal(user)
    assert exc_info.value.status_code == 400

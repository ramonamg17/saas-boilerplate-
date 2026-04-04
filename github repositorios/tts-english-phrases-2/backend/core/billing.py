"""
core/billing.py — All Stripe interactions.

DO NOT EDIT PER PROJECT — configure via config.py and plans.py.
"""

from datetime import datetime, timezone

import stripe
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.user import User
from plans import get_plan

stripe.api_key = settings.STRIPE_SECRET_KEY


# ── Customer ──────────────────────────────────────────────────────────

async def create_stripe_customer(email: str) -> str:
    """Create a Stripe customer and return the customer ID."""
    customer = stripe.Customer.create(email=email)
    return customer.id


# ── Checkout ──────────────────────────────────────────────────────────

async def create_checkout_session(user: User, plan_key: str) -> str:
    """Create a Stripe Checkout session and return the URL."""
    plan = get_plan(plan_key)
    if not plan["stripe_price_id"]:
        raise HTTPException(status_code=400, detail="Plan has no Stripe price")

    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = await create_stripe_customer(user.email)

    trial_days = plan["trial_days"] or None

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
        subscription_data={"trial_period_days": trial_days} if trial_days else {},
        success_url=f"{settings.FRONTEND_URL}/billing.html?success=1",
        cancel_url=f"{settings.FRONTEND_URL}/billing.html?canceled=1",
        metadata={"user_id": str(user.id), "plan_key": plan_key},
    )
    return session.url


# ── Elements (Payment Intent) ─────────────────────────────────────────

async def create_payment_intent(user: User, plan_key: str) -> str:
    """Create a PaymentIntent for use with Stripe Elements. Returns client_secret."""
    plan = get_plan(plan_key)
    amount = int(plan["price"] * 100)  # cents

    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = await create_stripe_customer(user.email)

    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency="usd",
        customer=customer_id,
        metadata={"user_id": str(user.id), "plan_key": plan_key},
    )
    return intent.client_secret


# ── Billing portal ────────────────────────────────────────────────────

async def create_billing_portal(user: User) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/billing.html",
    )
    return session.url


# ── Subscription management ───────────────────────────────────────────

async def cancel_subscription(user: User, db: AsyncSession) -> None:
    """Schedule subscription to cancel at period end."""
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription")

    stripe.Subscription.modify(
        user.stripe_subscription_id,
        cancel_at_period_end=True,
    )
    user.subscription_status = "canceled"
    await db.flush()


async def reactivate_subscription(user: User) -> None:
    """Remove the cancel-at-period-end flag to reactivate a subscription."""
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No subscription found")

    stripe.Subscription.modify(
        user.stripe_subscription_id,
        cancel_at_period_end=False,
    )


# ── Webhook ───────────────────────────────────────────────────────────

async def handle_webhook(payload: bytes, sig: str, db: AsyncSession) -> dict:
    """
    Verify the Stripe webhook signature and route the event.

    Handled events:
      - checkout.session.completed
      - customer.subscription.updated
      - customer.subscription.deleted
      - invoice.payment_failed
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _on_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await _on_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await _on_subscription_deleted(data, db)
    elif event_type == "invoice.payment_failed":
        await _on_payment_failed(data, db)

    return {"received": True}


# ── Internal webhook handlers ─────────────────────────────────────────

async def _get_user_by_customer(customer_id: str, db: AsyncSession) -> User | None:
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    return result.scalar_one_or_none()


async def _on_checkout_completed(data: dict, db: AsyncSession) -> None:
    from core.email import send_subscription_confirmed
    from plans import get_plan

    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    metadata = data.get("metadata", {})
    plan_key = metadata.get("plan_key", "pro")

    user = await _get_user_by_customer(customer_id, db)
    if not user:
        return

    user.stripe_subscription_id = subscription_id
    user.plan = plan_key
    user.subscription_status = "active"
    await db.flush()

    plan = get_plan(plan_key)
    await send_subscription_confirmed(user, plan["name"])


async def _on_subscription_updated(data: dict, db: AsyncSession) -> None:
    customer_id = data.get("customer")
    user = await _get_user_by_customer(customer_id, db)
    if not user:
        return

    status = data.get("status")
    user.subscription_status = status

    period_end = data.get("current_period_end")
    if period_end:
        user.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)

    plan_key = data.get("metadata", {}).get("plan_key")
    if plan_key:
        user.plan = plan_key

    await db.flush()


async def _on_subscription_deleted(data: dict, db: AsyncSession) -> None:
    customer_id = data.get("customer")
    user = await _get_user_by_customer(customer_id, db)
    if not user:
        return

    user.subscription_status = "canceled"
    user.plan = "free"
    user.stripe_subscription_id = None
    await db.flush()


async def _on_payment_failed(data: dict, db: AsyncSession) -> None:
    from core.email import send_payment_failed

    customer_id = data.get("customer")
    user = await _get_user_by_customer(customer_id, db)
    if not user:
        return

    user.subscription_status = "past_due"
    await db.flush()
    await send_payment_failed(user)

"""
routers/billing.py — Billing endpoints and Stripe webhook.
"""

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.billing import (
    cancel_subscription,
    create_billing_portal,
    create_checkout_session,
    create_payment_intent,
    handle_webhook,
    reactivate_subscription,
)
from database import get_db
from middleware.auth_guard import get_current_user
from models.user import User
from plans import all_plans

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────

class PlanSelectRequest(BaseModel):
    plan_key: str


class CancelRequest(BaseModel):
    reason: str = ""
    feedback: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/checkout")
async def checkout(
    body: PlanSelectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session (BILLING_MODE=checkout)."""
    url = await create_checkout_session(user, body.plan_key, db)
    return {"url": url}


@router.post("/payment-intent")
async def payment_intent(
    body: PlanSelectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a PaymentIntent client secret (BILLING_MODE=elements)."""
    client_secret = await create_payment_intent(user, body.plan_key)
    return {"client_secret": client_secret}


@router.post("/portal")
async def billing_portal(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a Stripe Customer Portal URL."""
    url = await create_billing_portal(user, db)
    return {"url": url}


@router.post("/cancel")
async def cancel(
    body: CancelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the current user's subscription at period end."""
    from core.email import send_cancellation_confirmed
    from models.user import UserCancellation

    await cancel_subscription(user, db)

    cancellation = UserCancellation(
        user_id=user.id,
        reason=body.reason,
        feedback=body.feedback,
        period_end=user.current_period_end,
    )
    db.add(cancellation)
    await db.flush()

    period_end_str = (
        user.current_period_end.strftime("%B %d, %Y")
        if user.current_period_end
        else "end of current period"
    )
    await send_cancellation_confirmed(user, period_end_str)

    return {"message": "Subscription cancelled", "period_end": period_end_str}


@router.post("/reactivate")
async def reactivate(
    user: User = Depends(get_current_user),
):
    """Reactivate a subscription scheduled for cancellation."""
    await reactivate_subscription(user)
    return {"message": "Subscription reactivated"}


@router.get("/status")
async def billing_status(user: User = Depends(get_current_user)):
    """Return the current user's billing status."""
    return {
        "plan": user.plan,
        "subscription_status": user.subscription_status,
        "trial_ends_at": user.trial_ends_at,
        "current_period_end": user.current_period_end,
        "stripe_customer_id": user.stripe_customer_id,
    }


@router.get("/plans")
async def list_plans():
    """Return all available plans (public)."""
    return {"plans": all_plans()}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """Stripe webhook receiver."""
    payload = await request.body()
    result = await handle_webhook(payload, stripe_signature, db)
    return result

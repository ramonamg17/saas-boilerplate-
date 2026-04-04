"""
services/limit_checker.py — Enforce per-plan session generation limits.

Called from generate_session() before the session is created.
Raises HTTPException 401 if user is not authenticated.
Raises HTTPException 403 if duration exceeds the plan's max.
Raises HTTPException 429 if the monthly minute budget is exceeded.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session_model import TtsSession
from models.user import User
from plans import get_plan


async def check_generation_limits(
    db: AsyncSession,
    duration_minutes: int,
    user: User | None,
    guest_id: str | None,
) -> None:
    """
    Enforce limits before creating a new TTS session.

    - user=None → 401 (authentication required)
    - user set, plan="free" → free plan (30 min/month, max 15 min/session)
    - user set, plan="pro"  → pro plan (120 min/month, max 30 min/session)
    """
    # 0. Require authentication
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    plan_key = user.plan
    plan = get_plan(plan_key)
    limits = plan["limits"]

    # 1. Duration check
    max_duration = limits["max_duration_minutes"]
    if duration_minutes > max_duration:
        if plan_key == "free":
            msg = f"Free plan allows up to {max_duration} min sessions. Upgrade to Pro for up to 30 min."
        else:
            msg = f"Maximum session duration is {max_duration} minutes."
        raise HTTPException(status_code=403, detail=msg)

    # 2. Monthly minute budget
    minutes_limit = limits["minutes_per_month"]
    if minutes_limit > 0:
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        result = await db.execute(
            select(func.coalesce(func.sum(TtsSession.duration_minutes), 0)).where(
                TtsSession.user_id == user.id,
                TtsSession.created_at >= month_start,
                TtsSession.status != "error",
            )
        )
        minutes_used = result.scalar_one()
        if minutes_used + duration_minutes > minutes_limit:
            remaining = max(0, minutes_limit - minutes_used)
            if plan_key == "free":
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Free plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                        f"{remaining} min remaining. Upgrade to Pro for 120 min/month."
                    ),
                )
            else:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Pro plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                        f"{remaining} min remaining."
                    ),
                )

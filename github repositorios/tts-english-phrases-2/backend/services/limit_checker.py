"""
services/limit_checker.py — Enforce per-plan session generation limits.

Called from generate_session() before the session is created.
Raises HTTPException 403 if duration exceeds the plan's max.
Raises HTTPException 429 if the session count limit is exceeded.
Raises HTTPException 400 if guest requests without a guest_id.
"""

from datetime import datetime, timezone, timedelta

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

    - user=None, guest_id set  → guest plan (1 session/day, max 5 min)
    - user set, plan="free"    → free plan (5 sessions/month, max 15 min)
    - user set, plan="pro"     → pro plan (unlimited, max 30 min)
    """
    plan_key = "guest" if user is None else user.plan
    plan = get_plan(plan_key)
    limits = plan["limits"]

    # 1. Duration check
    max_duration = limits["max_duration_minutes"]
    if duration_minutes > max_duration:
        if plan_key == "guest":
            msg = f"Guests can generate up to {max_duration} min sessions. Sign up for longer sessions."
        elif plan_key == "free":
            msg = f"Free plan allows up to {max_duration} min sessions. Upgrade to Pro for up to 30 min."
        else:
            msg = f"Maximum session duration is {max_duration} minutes."
        raise HTTPException(status_code=403, detail=msg)

    # 2. Session count check
    if plan_key == "guest":
        if not guest_id:
            raise HTTPException(
                status_code=400,
                detail="X-Guest-ID header required for unauthenticated requests",
            )

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        count_result = await db.execute(
            select(func.count(TtsSession.id)).where(
                TtsSession.guest_id == guest_id,
                TtsSession.created_at >= today_start,
            )
        )
        count = count_result.scalar_one()
        daily_limit = limits["sessions_per_day"]
        if count >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Guest limit reached: {daily_limit} session(s) per day. Sign up for a free account.",
            )

    elif plan_key == "free":
        monthly_limit = limits["sessions_per_month"]
        if monthly_limit > 0:  # 0 = unlimited
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            count_result = await db.execute(
                select(func.count(TtsSession.id)).where(
                    TtsSession.user_id == user.id,
                    TtsSession.created_at >= month_start,
                )
            )
            count = count_result.scalar_one()
            if count >= monthly_limit:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Free plan limit reached: {monthly_limit} sessions per month. "
                        "Upgrade to Pro for unlimited sessions."
                    ),
                )

    # pro: no session count limit (duration already validated above)

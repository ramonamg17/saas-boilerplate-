"""
middleware/rate_limit.py — Sliding window rate limiter via DB.

DO NOT EDIT PER PROJECT — configure limits in plans.py.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.middleware.auth_guard import get_current_user
from backend.models.user import RateLimitLog, User
from backend.plans import get_plan_limit


def rate_limit(action: str) -> Callable:
    """
    Factory that returns a FastAPI dependency enforcing a sliding-window
    rate limit for `action`.

    Limit is read from the user's current plan via plans.get_plan_limit().
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        limit = get_plan_limit(user.plan, "requests_per_hour")

        if limit <= 0:
            # 0 = unlimited
            return

        window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

        count_result = await db.execute(
            select(func.count(RateLimitLog.id)).where(
                RateLimitLog.user_id == user.id,
                RateLimitLog.action == action,
                RateLimitLog.requested_at >= window_start,
            )
        )
        count = count_result.scalar_one()

        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for action '{action}'. Limit: {limit} per hour.",
                headers={"Retry-After": str(window_seconds)},
            )

        # Log the request
        db.add(RateLimitLog(user_id=user.id, action=action))
        await db.flush()

    return Depends(_check)

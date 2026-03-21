"""
routers/admin.py — Admin-only endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import create_jwt
from database import get_db
from middleware.auth_guard import require_admin
from models.user import User
from plans import get_plan

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────

class PlanOverrideRequest(BaseModel):
    plan_key: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    plan: str
    is_admin: bool
    is_active: bool
    subscription_status: str | None
    stripe_customer_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    plan: str | None = Query(None),
    search: str | None = Query(None),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with optional filtering."""
    query = select(User)

    if plan:
        query = query.where(User.plan == plan)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    return {"users": [UserOut.model_validate(u) for u in users], "page": page}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user's details."""
    from fastapi import HTTPException
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/plan")
async def override_plan(
    user_id: int,
    body: PlanOverrideRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Override a user's plan (admin only)."""
    from fastapi import HTTPException
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = get_plan(body.plan_key)
    user.plan = plan["key"]
    await db.flush()

    return {"message": f"Plan updated to '{plan['name']}' for user {user.email}"}


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an impersonation JWT for the target user.
    The token includes impersonation context for audit logging.
    """
    from fastapi import HTTPException
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_jwt({
        "sub": str(target.id),
        "email": target.email,
        "impersonating": True,
        "target_user_id": target.id,
        "admin_id": admin.id,
    })
    return {"access_token": token, "token_type": "bearer", "impersonating": target.email}


@router.get("/stats")
async def get_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return high-level platform statistics."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_subs = (await db.execute(
        select(func.count(User.id)).where(User.subscription_status == "active")
    )).scalar_one()
    pro_users = (await db.execute(
        select(func.count(User.id)).where(User.plan == "pro")
    )).scalar_one()
    new_today = (await db.execute(
        select(func.count(User.id)).where(
            User.created_at >= datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        )
    )).scalar_one()

    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "pro_users": pro_users,
        "new_users_today": new_today,
    }

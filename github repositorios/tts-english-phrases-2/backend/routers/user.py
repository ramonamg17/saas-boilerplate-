"""
routers/user.py — User settings, account management, and contact.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_guard import get_current_user
from models.user import User
from plans import all_plans

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    name: str | None = None
    avatar_url: str | None = None


class ContactRequest(BaseModel):
    message: str


class DeleteRequest(BaseModel):
    confirmation: str  # must equal "DELETE"


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(user: User = Depends(get_current_user)):
    """Return the current user's settings."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "plan": user.plan,
        "is_admin": user.is_admin,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at,
    }


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile settings."""
    if body.name is not None:
        user.name = body.name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.flush()
    return {"message": "Settings updated"}


@router.post("/contact")
async def contact(
    body: ContactRequest,
    user: User = Depends(get_current_user),
):
    """Send a support message from the authenticated user."""
    from core.email import send_support_received
    await send_support_received(user, body.message)
    return {"message": "Your message has been sent. We'll get back to you soon."}


@router.delete("/account")
async def delete_account(
    body: DeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete the current user's account.
    Requires the request body to contain confirmation="DELETE".
    """
    if body.confirmation != "DELETE":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Confirmation text must be 'DELETE'")

    await db.delete(user)
    await db.flush()
    return {"message": "Account deleted"}


@router.get("/plans")
async def get_plans():
    """Return all available plans."""
    return {"plans": all_plans()}

"""
routers/user.py — User settings, account management, and contact.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_guard import get_current_user
from models.session_model import TtsSession
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


@router.get("/sessions")
async def get_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all completed sessions for the authenticated user, newest first."""
    from services.storage_service import get_signed_url

    result = await db.execute(
        select(TtsSession)
        .where(TtsSession.user_id == user.id, TtsSession.status == "done")
        .order_by(TtsSession.created_at.desc())
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        audio_url = s.audio_url
        if audio_url:
            try:
                audio_url = get_signed_url(s.id, ttl=86400)  # fresh 24h URL
            except Exception:
                pass  # keep stored URL as fallback
        items.append({
            "id": s.id,
            "topic": s.topic,
            "language": s.language,
            "duration_minutes": s.duration_minutes,
            "audio_url": audio_url,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"sessions": items}


@router.post("/sessions/{session_id}/played")
async def mark_session_played(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset the 30-day expiration timer for a session when it is played."""
    result = await db.execute(
        select(TtsSession).where(
            TtsSession.id == session_id,
            TtsSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    session.last_played_at = now
    session.expires_at = now + timedelta(days=30)
    await db.flush()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and its audio file."""
    from services.storage_service import delete_session_file

    result = await db.execute(
        select(TtsSession).where(
            TtsSession.id == session_id,
            TtsSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        delete_session_file(session_id)
    except Exception:
        pass  # proceed even if storage deletion fails

    await db.delete(session)
    await db.flush()
    return {"ok": True}


@router.get("/plans")
async def get_plans():
    """Return all available plans."""
    return {"plans": all_plans()}

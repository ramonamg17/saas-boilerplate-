"""
routers/auth.py — Authentication endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.auth import (
    create_jwt,
    create_magic_link_token,
    create_or_get_user,
    exchange_google_code,
    get_google_auth_url,
    verify_magic_link_token,
)
from core.email import send_magic_link, send_welcome
from database import get_db
from middleware.auth_guard import get_current_user
from models.user import User

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: EmailStr


class VerifyTokenRequest(BaseModel):
    token: str


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str = ""


class GuestMigrateRequest(BaseModel):
    guest_session_id: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    plan: str
    is_admin: bool
    subscription_status: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/magic-link")
async def send_magic_link_endpoint(
    body: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a magic link to the provided email address."""
    raw_token = await create_magic_link_token(body.email, db)
    await send_magic_link(body.email, raw_token)
    return {"message": "Magic link sent. Check your email."}


@router.post("/verify")
async def verify_magic_link(
    body: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify a magic link token and return a JWT."""
    email = await verify_magic_link_token(body.token, db)
    user = await create_or_get_user(email, None, db)

    # Send welcome email only on first login (no prior last_login)
    is_new = user.last_login_at is None
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    if is_new:
        await send_welcome(user)

    jwt_token = create_jwt({"sub": str(user.id), "email": user.email})
    return {"access_token": jwt_token, "token_type": "bearer"}


@router.get("/google")
async def google_auth_redirect(state: str = ""):
    """Return the Google OAuth2 authorization URL."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    return {"url": get_google_auth_url(state)}


@router.post("/google/callback")
async def google_callback(
    body: GoogleCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a Google OAuth2 code for a JWT."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")

    email, name = await exchange_google_code(body.code)
    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google")

    user = await create_or_get_user(email, name, db)
    if not user.auth_provider or user.auth_provider == "magic_link":
        user.auth_provider = "google"
        await db.flush()

    jwt_token = create_jwt({"sub": str(user.id), "email": user.email})
    return {"access_token": jwt_token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return user


@router.post("/guest/migrate")
async def migrate_guest(
    body: GuestMigrateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Associate a guest session with the authenticated user account.
    Migrates any TTS sessions created under the guest_id to this user.
    """
    from sqlalchemy import update
    from models.session_model import TtsSession

    await db.execute(
        update(TtsSession)
        .where(TtsSession.guest_id == body.guest_session_id, TtsSession.user_id.is_(None))
        .values(user_id=user.id, guest_id=None)
    )
    await db.flush()
    return {"message": "Guest session migrated", "user_id": user.id}

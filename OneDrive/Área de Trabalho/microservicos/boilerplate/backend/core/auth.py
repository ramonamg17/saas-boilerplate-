"""
core/auth.py — JWT, magic link, and Google OAuth logic.

DO NOT EDIT PER PROJECT — configure via config.py only.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from jose import JWTError, jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.user import MagicLinkToken, User


# ── JWT ───────────────────────────────────────────────────────────────

def create_jwt(payload: dict) -> str:
    """Create a signed JWT with expiry."""
    data = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    data["exp"] = expire
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


# ── Token hashing ─────────────────────────────────────────────────────

def hash_token(raw: str) -> str:
    """Return SHA-256 hex digest of a raw token."""
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Magic link ────────────────────────────────────────────────────────

async def create_magic_link_token(email: str, db: AsyncSession) -> str:
    """
    Generate a secure random token, store its hash in the DB,
    and return the raw token to be included in the email link.
    """
    # Ensure user exists (create if new)
    user = await create_or_get_user(email, None, db)

    raw = secrets.token_urlsafe(32)
    token_hash = hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.MAGIC_LINK_EXPIRE_MINUTES
    )

    db_token = MagicLinkToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()
    return raw


async def verify_magic_link_token(raw: str, db: AsyncSession) -> str:
    """
    Validate a raw magic link token.
    Returns the user's email on success; raises HTTPException on failure.
    Marks the token as used.
    """
    token_hash = hash_token(raw)
    result = await db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(status_code=400, detail="Invalid magic link token")
    if db_token.used:
        raise HTTPException(status_code=400, detail="Magic link already used")
    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Magic link expired")

    db_token.used = True
    await db.flush()

    # Load associated user
    result = await db.execute(select(User).where(User.id == db_token.user_id))
    user = result.scalar_one()
    return user.email


# ── Google OAuth ──────────────────────────────────────────────────────

def get_google_auth_url(state: str = "") -> str:
    """Return the Google OAuth2 authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def exchange_google_code(code: str) -> tuple[str, str]:
    """
    Exchange an OAuth2 authorization code for user info.
    Returns (email, name).
    """
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()

    email = info.get("email", "")
    name = info.get("name", "")
    return email, name


# ── User creation ─────────────────────────────────────────────────────

async def create_or_get_user(
    email: str, name: str | None, db: AsyncSession
) -> User:
    """Return existing user or create a new one."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email, name=name, plan="free")
        db.add(user)
        await db.flush()

    elif name and not user.name:
        user.name = name

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user

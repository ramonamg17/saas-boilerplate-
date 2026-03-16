"""
middleware/auth_guard.py — Route protection dependencies.

DO NOT EDIT PER PROJECT.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import decode_jwt
from backend.database import get_db
from backend.models.user import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validates Bearer JWT and returns the authenticated User.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency — requires the current user to be an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Dependency — returns User if a valid token is provided, else None.
    Useful for guest-tolerant routes.
    """
    if not credentials:
        return None

    try:
        payload = decode_jwt(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        return user if (user and user.is_active) else None
    except HTTPException:
        return None


def get_impersonation_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> Optional[dict]:
    """
    Returns the impersonation context from the JWT if present.
    An impersonation token includes {"impersonating": true, "target_user_id": <id>, "admin_id": <id>}.
    Returns None for regular tokens.
    """
    if not credentials:
        return None

    try:
        payload = decode_jwt(credentials.credentials)
        if payload.get("impersonating"):
            return {
                "target_user_id": payload.get("target_user_id"),
                "admin_id": payload.get("admin_id"),
            }
    except HTTPException:
        pass
    return None

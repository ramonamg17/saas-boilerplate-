"""
Unit tests for services/limit_checker.py.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException


def _make_db_with_value(value: int = 0) -> AsyncMock:
    """Return a mock DB whose scalar_one() returns `value`.

    Used for both guest session counts (COUNT query) and
    free/pro minute sums (SUM query).
    """
    scalar_result = MagicMock()
    scalar_result.scalar_one = MagicMock(return_value=value)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)
    return db


def _make_user(plan: str = "free") -> MagicMock:
    user = MagicMock()
    user.plan = plan
    user.id = 1
    return user


# ── Guest plan tests ──────────────────────────────────────────────────────────

async def test_guest_first_session_allowed():
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    await check_generation_limits(db, 5, user=None, guest_id="guest-abc")


async def test_guest_second_session_rejected():
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(1)
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 5, user=None, guest_id="guest-abc")
    assert exc_info.value.status_code == 429


async def test_guest_duration_exceeded():
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 10, user=None, guest_id="guest-abc")
    assert exc_info.value.status_code == 403


async def test_guest_no_id_raises_400():
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 5, user=None, guest_id=None)
    assert exc_info.value.status_code == 400


# ── Free plan tests ───────────────────────────────────────────────────────────

async def test_free_user_under_monthly_limit():
    """15 min used + 5 requested = 20 <= 30 — allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(15)
    user = _make_user("free")
    await check_generation_limits(db, 5, user=user, guest_id=None)


async def test_free_user_exactly_at_monthly_limit():
    """25 min used + 5 requested = 30 = 30 — allowed (not over)."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(25)
    user = _make_user("free")
    await check_generation_limits(db, 5, user=user, guest_id=None)


async def test_free_user_over_monthly_limit():
    """25 min used + 10 requested = 35 > 30 — 429."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(25)
    user = _make_user("free")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 10, user=user, guest_id=None)
    assert exc_info.value.status_code == 429
    assert "Free plan limit reached" in exc_info.value.detail
    assert "Upgrade to Pro" in exc_info.value.detail


async def test_free_user_max_duration_exceeded():
    """Requesting 20 min > max_duration(15) — 403."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("free")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 20, user=user, guest_id=None)
    assert exc_info.value.status_code == 403


# ── Pro plan tests ────────────────────────────────────────────────────────────

async def test_pro_user_under_monthly_limit():
    """60 min used + 30 requested = 90 <= 120 — allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(60)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_exactly_at_monthly_limit():
    """90 min used + 30 requested = 120 = 120 — allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(90)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_over_monthly_limit():
    """100 min used + 30 requested = 130 > 120 — 429."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(100)
    user = _make_user("pro")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 30, user=user, guest_id=None)
    assert exc_info.value.status_code == 429
    assert "Pro plan limit reached" in exc_info.value.detail


async def test_pro_user_max_duration_allowed():
    """30 min is the max duration for pro — allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_duration_exceeded():
    """Pro max is 30 min; 31 — 403."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("pro")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 31, user=user, guest_id=None)
    assert exc_info.value.status_code == 403

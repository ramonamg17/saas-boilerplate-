"""
Unit tests for rate limit sliding window logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def test_get_plan_limit_for_rate_limit():
    """Rate limit uses plans.get_plan_limit under the hood."""
    from backend.plans import get_plan_limit
    assert get_plan_limit("free", "requests_per_hour") == 20
    assert get_plan_limit("pro", "requests_per_hour") == 500


@pytest.mark.asyncio
async def test_rate_limit_dependency_allows_under_limit():
    from backend.middleware.rate_limit import rate_limit
    from backend.models.user import User

    user = User(id=1, email="a@b.com", plan="pro")

    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 10  # well under 500
    mock_db.execute = AsyncMock(return_value=count_result)

    # Extract the inner _check function
    dep = rate_limit("test_action")
    inner = dep.dependency  # Depends wraps the function

    # Should not raise
    await inner(user=user, db=mock_db)
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_dependency_blocks_over_limit():
    from fastapi import HTTPException
    from backend.middleware.rate_limit import rate_limit
    from backend.models.user import User

    user = User(id=1, email="a@b.com", plan="free")

    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 20  # exactly at limit (>= triggers block)
    mock_db.execute = AsyncMock(return_value=count_result)

    dep = rate_limit("test_action")
    inner = dep.dependency

    with pytest.raises(HTTPException) as exc_info:
        await inner(user=user, db=mock_db)
    assert exc_info.value.status_code == 429
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_zero_means_unlimited():
    from backend.middleware.rate_limit import rate_limit
    from backend.models.user import User
    from unittest.mock import patch

    user = User(id=1, email="a@b.com", plan="free")
    mock_db = AsyncMock()

    dep = rate_limit("test_action")
    inner = dep.dependency

    with patch("backend.middleware.rate_limit.get_plan_limit", return_value=0):
        await inner(user=user, db=mock_db)  # Should not raise or query DB
    mock_db.execute.assert_not_called()

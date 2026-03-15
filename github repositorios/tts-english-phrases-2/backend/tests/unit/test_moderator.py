"""
Unit tests for services/moderator.py
OpenAI Moderation API is mocked — no real API calls.
"""
import pytest
from unittest.mock import AsyncMock, patch

from services.moderator import filter_phrases
from tests.conftest import make_moderation_result, make_moderation_response


# ── All safe ──────────────────────────────────────────────────────────────────

async def test_all_safe_phrases_pass_through():
    phrases = ["I love learning languages", "The food is delicious today"]
    mock_resp = make_moderation_response([False, False])

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=mock_resp)
        result = await filter_phrases(phrases)

    assert result == phrases


# ── Flagged phrases ───────────────────────────────────────────────────────────

async def test_single_flagged_phrase_removed():
    phrases = ["safe phrase one here", "violent content removed", "safe phrase two here"]
    mock_resp = make_moderation_response([False, True, False])

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=mock_resp)
        result = await filter_phrases(phrases)

    assert len(result) == 2
    assert "violent content removed" not in result


async def test_all_flagged_returns_empty():
    phrases = ["bad one", "bad two", "bad three"]
    mock_resp = make_moderation_response([True, True, True])

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=mock_resp)
        result = await filter_phrases(phrases)

    assert result == []


async def test_order_preserved_after_filtering():
    phrases = ["alpha", "beta", "gamma", "delta"]
    # Remove beta (index 1)
    mock_resp = make_moderation_response([False, True, False, False])

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=mock_resp)
        result = await filter_phrases(phrases)

    assert result == ["alpha", "gamma", "delta"]


# ── Regeneration on heavy removal ─────────────────────────────────────────────

async def test_regeneration_triggered_when_too_many_removed():
    """If > 20% removed, regenerate_fn should be called."""
    phrases = [f"phrase {i}" for i in range(10)]
    # Flag 5 out of 10 (50% removed — above 20% threshold)
    flags = [True, True, True, True, True, False, False, False, False, False]
    mock_resp = make_moderation_response(flags)

    regen_mock = AsyncMock(return_value=["new safe phrase one", "new safe phrase two"])
    safe_for_new = make_moderation_response([False, False])

    call_count = 0

    async def side_effect(input):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_resp  # first batch — 5 flagged
        return safe_for_new  # regen batch — all safe

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(side_effect=side_effect)
        result = await filter_phrases(
            phrases,
            regenerate_fn=regen_mock,
            language="Spanish",
            topic="food",
        )

    assert regen_mock.call_count >= 1  # called at least once (loop retries until threshold met)
    assert len(result) > 5  # original safe + new safe phrases


async def test_no_regeneration_when_few_removed():
    """If ≤ 20% removed, regenerate_fn should NOT be called."""
    phrases = [f"phrase {i}" for i in range(10)]
    # Flag only 1 out of 10 (10% — below threshold)
    flags = [False] * 9 + [True]
    mock_resp = make_moderation_response(flags)

    regen_mock = AsyncMock(return_value=[])

    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=mock_resp)
        await filter_phrases(phrases, regenerate_fn=regen_mock)

    regen_mock.assert_not_called()


# ── Edge cases ────────────────────────────────────────────────────────────────

async def test_empty_input_returns_empty():
    with patch("services.moderator.client") as mock_client:
        mock_client.moderations.create = AsyncMock(return_value=make_moderation_response([]))
        result = await filter_phrases([])
    assert result == []

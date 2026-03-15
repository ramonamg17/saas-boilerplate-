"""
Unit tests for services/phrase_generator.py
OpenAI client is mocked — no real API calls.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.phrase_generator import calc_num_phrases, generate_phrases, interpret_topic
from tests.conftest import make_phrases_response, make_chat_response


# ── calc_num_phrases ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("minutes,expected", [
    (5,  40),
    (10, 80),
    (15, 120),
    (20, 160),
    (30, 240),
])
def test_calc_num_phrases(minutes, expected):
    assert calc_num_phrases(minutes) == expected


def test_calc_num_phrases_minimum_is_one():
    assert calc_num_phrases(0) == 1
    assert calc_num_phrases(-5) == 1


def test_calc_num_phrases_returns_int():
    assert isinstance(calc_num_phrases(10), int)


# ── generate_phrases ──────────────────────────────────────────────────────────

async def test_generate_phrases_returns_list():
    phrases = ["Quiero pedir la cuenta", "Me trae la carta por favor"]
    mock_resp = make_phrases_response(phrases)

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await generate_phrases("Spanish", "food", 2)

    assert isinstance(result, list)
    assert result == phrases


async def test_generate_phrases_strips_whitespace():
    phrases = ["  hola mundo  ", "  buenos días  "]
    mock_resp = make_phrases_response(phrases)

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await generate_phrases("Spanish", "greetings", 2)

    assert result == ["hola mundo", "buenos días"]


async def test_generate_phrases_handles_direct_array():
    """GPT sometimes returns a top-level JSON array."""
    mock_resp = make_chat_response(json.dumps(["phrase one", "phrase two"]))

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await generate_phrases("French", "travel", 2)

    assert result == ["phrase one", "phrase two"]


async def test_generate_phrases_calls_gpt4o_mini():
    """Ensure the cheaper model is always used."""
    mock_resp = make_phrases_response(["une phrase test ici"])

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        await generate_phrases("French", "travel", 1)

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"


async def test_generate_phrases_invalid_response_raises():
    """A response that can't be parsed as a list should raise after retries."""
    mock_resp = make_chat_response("not valid json {{{")

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        with pytest.raises(Exception):
            await generate_phrases("Spanish", "food", 5)


# ── interpret_topic ───────────────────────────────────────────────────────────

async def test_interpret_topic_returns_string():
    mock_resp = make_chat_response("I'll generate 18 practical Spanish phrases about ordering food.")

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await interpret_topic("ordering food", "Spanish")

    assert isinstance(result, str)
    assert len(result) > 0


async def test_interpret_topic_strips_whitespace():
    mock_resp = make_chat_response("  Some interpretation text.  ")

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        result = await interpret_topic("travel", "French")

    assert result == "Some interpretation text."


async def test_interpret_topic_uses_gpt4o_mini():
    mock_resp = make_chat_response("Test interpretation")

    with patch("services.phrase_generator.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        await interpret_topic("cooking", "Italian")

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini"

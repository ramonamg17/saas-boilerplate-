"""
Shared fixtures for all test layers.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock


# ── OpenAI chat completion factory ────────────────────────────────────────────

def make_chat_response(content: str) -> MagicMock:
    """Build a mock openai ChatCompletion response."""
    msg = MagicMock()
    msg.content = content

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def make_phrases_response(phrases: list[str]) -> MagicMock:
    return make_chat_response(json.dumps({"phrases": phrases}))


# ── OpenAI moderation factory ─────────────────────────────────────────────────

def make_moderation_result(
    flagged: bool = False,
    violence: bool = False,
    sexual: bool = False,
    hate: bool = False,
    harassment: bool = False,
) -> MagicMock:
    cats = MagicMock()
    cats.violence = violence
    cats.sexual = sexual
    cats.hate = hate
    cats.harassment = harassment

    result = MagicMock()
    result.flagged = flagged
    result.categories = cats
    return result


def make_moderation_response(flags: list[bool]) -> MagicMock:
    resp = MagicMock()
    resp.results = [make_moderation_result(flagged=f) for f in flags]
    return resp


# ── Kokoro TTS HTTP response factory ─────────────────────────────────────────

def make_kokoro_response(audio_bytes: bytes = b"FAKE_AUDIO") -> MagicMock:
    resp = MagicMock()
    resp.content = audio_bytes
    resp.raise_for_status = MagicMock()
    return resp


# ── Common env fixture ────────────────────────────────────────────────────────

@pytest.fixture(autouse=False)
def api_keys(monkeypatch):
    """Set all required API keys in the environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("TTS_SERVICE_URL", "http://localhost:8880")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
    monkeypatch.setenv("SUPABASE_BUCKET", "audio-sessions")
    monkeypatch.setenv("SESSION_TTL_HOURS", "3")

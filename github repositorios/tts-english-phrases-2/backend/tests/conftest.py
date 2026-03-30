"""
Shared fixtures for all test layers.
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# ── Set test env vars BEFORE any config imports ───────────────────────────────
# These are only applied if not already set (respects real .env values)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_placeholder")
os.environ.setdefault("RESEND_API_KEY", "re_test_placeholder")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-supabase-key")


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
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
    monkeypatch.setenv("SUPABASE_BUCKET", "audio-sessions")
    monkeypatch.setenv("SESSION_TTL_HOURS", "3")


# ── DB fixtures for auth/billing/admin tests ─────────────────────────────────

@pytest.fixture
def mock_db():
    """A mock async DB session for use in integration tests."""
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.delete = AsyncMock()
    return db

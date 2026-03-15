"""
Unit tests for services/tts_service.py
Kokoro TTS HTTP calls are mocked — no real API calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.tts_service import (
    VOICE_POOLS,
    TTS_SERVICE_URL,
    generate_audio_for_phrase,
    generate_all_audio,
)
from tests.conftest import make_kokoro_response


# ── TTS_SERVICE_URL ───────────────────────────────────────────────────────────

def test_tts_service_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("TTS_SERVICE_URL", "http://my-tts-server:9000")
    import importlib
    import services.tts_service as mod
    importlib.reload(mod)
    assert mod.TTS_SERVICE_URL == "http://my-tts-server:9000"
    # restore
    importlib.reload(mod)


# ── VOICE_POOLS ───────────────────────────────────────────────────────────────

def test_voice_pools_covers_all_supported_languages():
    supported = {"English", "Spanish", "Portuguese (Brazil)", "French", "German", "Italian", "Japanese", "Russian"}
    assert supported == set(VOICE_POOLS.keys())


def test_voice_pools_all_non_empty():
    assert all(len(pool) > 0 for pool in VOICE_POOLS.values())


def test_voice_pools_all_strings():
    for pool in VOICE_POOLS.values():
        assert all(isinstance(v, str) and len(v) > 0 for v in pool)


def test_voice_pools_english_contains_expected_voices():
    assert "af_heart" in VOICE_POOLS["English"]
    assert "af_bella" in VOICE_POOLS["English"]
    assert "am_adam" in VOICE_POOLS["English"]


# ── generate_audio_for_phrase ─────────────────────────────────────────────────

async def test_generate_audio_returns_bytes():
    fake_audio = b"FAKE_MP3_AUDIO_DATA"

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response(fake_audio))

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        result = await generate_audio_for_phrase("Hello world", "af_heart")

    assert result == fake_audio


async def test_generate_audio_sends_phrase_text():
    phrase = "Je voudrais un café s'il vous plaît"

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response())

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        await generate_audio_for_phrase(phrase, "af_heart")

    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"] == phrase


async def test_generate_audio_sends_correct_model():
    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response())

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        await generate_audio_for_phrase("test phrase", "af_heart")

    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["model"] == "kokoro"


async def test_generate_audio_sends_voice_id():
    voice_id = "am_adam"

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response())

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        await generate_audio_for_phrase("test", voice_id)

    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["voice"] == voice_id


async def test_generate_audio_sends_speed_param():
    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response())

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        await generate_audio_for_phrase("test", "af_heart", speed=0.7)

    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["speed"] == 0.7


async def test_generate_audio_calls_correct_endpoint():
    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)
    mock_http.post = AsyncMock(return_value=make_kokoro_response())

    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        await generate_audio_for_phrase("test", "af_heart")

    url_arg = mock_http.post.call_args.args[0]
    assert url_arg.endswith("/v1/audio/speech")


# ── generate_all_audio ────────────────────────────────────────────────────────

async def test_generate_all_audio_returns_one_tuple_per_phrase():
    phrases = ["phrase one", "phrase two", "phrase three"]

    with patch(
        "services.tts_service.generate_audio_for_phrase",
        new=AsyncMock(return_value=b"AUDIO"),
    ):
        result = await generate_all_audio(phrases)

    assert len(result) == 3
    assert all(isinstance(r, tuple) and len(r) == 2 for r in result)
    assert all(r == (b"AUDIO", b"AUDIO") for r in result)


async def test_generate_all_audio_empty_list():
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"")):
        result = await generate_all_audio([])
    assert result == []


async def test_generate_all_audio_uses_same_voice_for_normal_and_slow():
    """Each phrase uses the same voice for both normal and slow versions."""
    phrases = ["alpha", "beta", "gamma"]
    calls = []  # list of (phrase, voice_id, speed)

    async def mock_gen(phrase, voice_id, speed=1.0):
        calls.append((phrase, voice_id, speed))
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases)

    # 2 calls per phrase (normal + slow)
    assert len(calls) == 6
    # For each phrase, both calls must use the same voice_id
    for phrase in phrases:
        phrase_calls = [c for c in calls if c[0] == phrase]
        assert len(phrase_calls) == 2
        assert phrase_calls[0][1] == phrase_calls[1][1]  # same voice
        speeds = {c[2] for c in phrase_calls}
        assert 1.0 in speeds and 0.7 in speeds  # one normal, one slow


async def test_generate_all_audio_voices_from_english_pool_by_default():
    """With no language arg, voices must come from the English pool."""
    phrases = ["alpha", "beta", "gamma"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases)

    assert all(v in VOICE_POOLS["English"] for v in used_voices)


async def test_generate_all_audio_uses_correct_pool_for_language():
    """Voices must come from the pool matching the requested language."""
    phrases = ["une phrase", "deux phrases"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="French")

    assert all(v in VOICE_POOLS["French"] for v in used_voices)


async def test_generate_all_audio_falls_back_to_english_for_unknown_language():
    """Unknown language must fall back to English voice pool."""
    phrases = ["hello"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="Klingon")

    assert all(v in VOICE_POOLS["English"] for v in used_voices)

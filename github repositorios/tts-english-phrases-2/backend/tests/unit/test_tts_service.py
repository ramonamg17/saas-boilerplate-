"""
Unit tests for services/tts_service.py
Google Cloud TTS calls are mocked — no real API calls.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from services.tts_service import (
    VOICE_POOLS,
    LANGUAGE_CODES,
    SLOW_RATE,
    generate_audio_for_phrase,
    generate_all_audio,
    generate_audio_streaming,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_synthesize_mock(audio: bytes = b"FAKE_MP3") -> MagicMock:
    """Sync mock for _synthesize_sync that returns fake audio bytes."""
    return MagicMock(return_value=audio)


# ── VOICE_POOLS ───────────────────────────────────────────────────────────────

def test_voice_pools_covers_all_supported_languages():
    expected = {
        "English", "English (UK)", "Spanish", "Portuguese (Brazil)",
        "French", "Italian", "Japanese", "Chinese",
        "German", "Korean", "Hindi", "Arabic",
        "Russian", "Dutch", "Polish", "Swedish", "Turkish", "Vietnamese",
    }
    assert expected == set(VOICE_POOLS.keys())


def test_voice_pools_all_non_empty():
    assert all(len(pool) > 0 for pool in VOICE_POOLS.values())


def test_voice_pools_all_strings():
    for pool in VOICE_POOLS.values():
        assert all(isinstance(v, str) and len(v) > 0 for v in pool)


def test_voice_pools_english_contains_neural2_voices():
    assert all("Neural2" in v or "Wavenet" in v for v in VOICE_POOLS["English"])
    assert any("en-US" in v for v in VOICE_POOLS["English"])


def test_voice_pools_new_languages_present():
    assert "German" in VOICE_POOLS
    assert "Korean" in VOICE_POOLS
    assert "Hindi" in VOICE_POOLS
    assert "Arabic" in VOICE_POOLS
    assert "Russian" in VOICE_POOLS
    assert "Dutch" in VOICE_POOLS
    assert "Polish" in VOICE_POOLS
    assert "Swedish" in VOICE_POOLS
    assert "Turkish" in VOICE_POOLS
    assert "Vietnamese" in VOICE_POOLS


# ── LANGUAGE_CODES ────────────────────────────────────────────────────────────

def test_language_codes_covers_all_supported_languages():
    assert set(LANGUAGE_CODES.keys()) == set(VOICE_POOLS.keys())


def test_language_codes_correct_bcp47_values():
    assert LANGUAGE_CODES["English"] == "en-US"
    assert LANGUAGE_CODES["English (UK)"] == "en-GB"
    assert LANGUAGE_CODES["Spanish"] == "es-ES"
    assert LANGUAGE_CODES["Portuguese (Brazil)"] == "pt-BR"
    assert LANGUAGE_CODES["French"] == "fr-FR"
    assert LANGUAGE_CODES["Italian"] == "it-IT"
    assert LANGUAGE_CODES["Japanese"] == "ja-JP"
    assert LANGUAGE_CODES["Chinese"] == "cmn-CN"
    assert LANGUAGE_CODES["German"] == "de-DE"
    assert LANGUAGE_CODES["Korean"] == "ko-KR"
    assert LANGUAGE_CODES["Arabic"] == "ar-XA"


# ── SLOW_RATE ─────────────────────────────────────────────────────────────────

def test_slow_rate_is_string_percentage():
    assert isinstance(SLOW_RATE, str)
    assert SLOW_RATE.endswith("%")


# ── generate_audio_for_phrase ─────────────────────────────────────────────────

async def test_generate_audio_returns_bytes():
    fake_audio = b"FAKE_MP3_AUDIO_DATA"
    with patch("services.tts_service._synthesize_sync", return_value=fake_audio):
        result = await generate_audio_for_phrase("Hello world", "en-US-Neural2-A", lang="en-US")
    assert result == fake_audio


async def test_generate_audio_normal_speed_calls_synthesize_with_slow_false():
    mock_synth = make_synthesize_mock()
    with patch("services.tts_service._synthesize_sync", mock_synth):
        await generate_audio_for_phrase("Hello", "en-US-Neural2-A", speed=1.0, lang="en-US")
    args = mock_synth.call_args[0]
    # _synthesize_sync(text, voice_name, lang_code, slow)
    assert args[0] == "Hello"
    assert args[1] == "en-US-Neural2-A"
    assert args[2] == "en-US"
    assert args[3] is False  # slow=False


async def test_generate_audio_slow_speed_calls_synthesize_with_slow_true():
    mock_synth = make_synthesize_mock()
    with patch("services.tts_service._synthesize_sync", mock_synth):
        await generate_audio_for_phrase("Hello", "en-US-Neural2-A", speed=0.7, lang="en-US")
    args = mock_synth.call_args[0]
    assert args[3] is True  # slow=True


async def test_generate_audio_passes_voice_id():
    mock_synth = make_synthesize_mock()
    with patch("services.tts_service._synthesize_sync", mock_synth):
        await generate_audio_for_phrase("test", "pt-BR-Neural2-A", lang="pt-BR")
    assert mock_synth.call_args[0][1] == "pt-BR-Neural2-A"


async def test_generate_audio_passes_lang_code():
    mock_synth = make_synthesize_mock()
    with patch("services.tts_service._synthesize_sync", mock_synth):
        await generate_audio_for_phrase("test", "fr-FR-Neural2-A", lang="fr-FR")
    assert mock_synth.call_args[0][2] == "fr-FR"


# ── _synthesize_sync SSML wrapping ────────────────────────────────────────────

def _make_httpx_mock(audio: bytes = b"AUDIO") -> MagicMock:
    import base64
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"audioContent": base64.b64encode(audio).decode()}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_synthesize_sync_wraps_slow_audio_in_ssml():
    """When slow=True, the text sent to Google must be SSML with prosody rate."""
    from services.tts_service import _synthesize_sync, SLOW_RATE

    mock_resp = _make_httpx_mock()
    with patch("services.tts_service.httpx.post", return_value=mock_resp) as mock_post:
        _synthesize_sync("Hello world", "en-US-Neural2-A", "en-US", slow=True)

    payload = mock_post.call_args[1]["json"]
    ssml = payload["input"]["ssml"]
    assert SLOW_RATE in ssml
    assert "Hello world" in ssml


def test_synthesize_sync_uses_plain_text_for_normal_speed():
    """When slow=False, text input must NOT use SSML."""
    from services.tts_service import _synthesize_sync

    mock_resp = _make_httpx_mock()
    with patch("services.tts_service.httpx.post", return_value=mock_resp) as mock_post:
        _synthesize_sync("Hello world", "en-US-Neural2-A", "en-US", slow=False)

    payload = mock_post.call_args[1]["json"]
    assert payload["input"]["text"] == "Hello world"
    assert "ssml" not in payload["input"]


def test_synthesize_sync_returns_audio_content():
    from services.tts_service import _synthesize_sync

    mock_resp = _make_httpx_mock(b"REAL_AUDIO")
    with patch("services.tts_service.httpx.post", return_value=mock_resp):
        result = _synthesize_sync("Hi", "en-US-Neural2-A", "en-US", slow=False)

    assert result == b"REAL_AUDIO"


# ── generate_all_audio ────────────────────────────────────────────────────────

async def test_generate_all_audio_returns_one_tuple_per_phrase():
    phrases = ["phrase one", "phrase two", "phrase three"]
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"AUDIO")):
        result = await generate_all_audio(phrases)
    assert len(result) == 3
    assert all(isinstance(r, tuple) and len(r) == 2 for r in result)


async def test_generate_all_audio_empty_list():
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"")):
        result = await generate_all_audio([])
    assert result == []


async def test_generate_all_audio_uses_same_voice_for_normal_and_slow():
    phrases = ["alpha", "beta", "gamma"]
    calls = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        calls.append((phrase, voice_id, speed))
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases)

    assert len(calls) == 6
    for phrase in phrases:
        phrase_calls = [c for c in calls if c[0] == phrase]
        assert len(phrase_calls) == 2
        assert phrase_calls[0][1] == phrase_calls[1][1]  # same voice
        speeds = {c[2] for c in phrase_calls}
        assert 1.0 in speeds and 0.7 in speeds


async def test_generate_all_audio_voices_from_english_pool_by_default():
    phrases = ["alpha", "beta"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases)

    assert all(v in VOICE_POOLS["English"] for v in used_voices)


async def test_generate_all_audio_uses_correct_pool_for_language():
    phrases = ["une phrase", "deux phrases"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="fr-FR"):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="French")

    assert all(v in VOICE_POOLS["French"] for v in used_voices)


async def test_generate_all_audio_falls_back_to_english_for_unknown_language():
    phrases = ["hello"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="Klingon")

    assert all(v in VOICE_POOLS["English"] for v in used_voices)


async def test_generate_all_audio_passes_correct_bcp47_lang_code():
    phrases = ["une phrase"]
    received_langs = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        received_langs.append(lang)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="French")

    assert all(lang == "fr-FR" for lang in received_langs)


async def test_generate_all_audio_unknown_language_passes_en_us_lang_code():
    phrases = ["hello"]
    received_langs = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        received_langs.append(lang)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="Klingon")

    assert all(lang == "en-US" for lang in received_langs)


# ── generate_audio_streaming ──────────────────────────────────────────────────

async def test_generate_audio_streaming_yields_all_phrases():
    phrases = ["alpha", "beta", "gamma"]
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"AUDIO")):
        results = []
        async for idx, total, chunk in generate_audio_streaming(phrases):
            results.append((idx, total, chunk))
    assert len(results) == 3
    assert all(total == 3 for _, total, _ in results)
    assert sorted(idx for idx, _, _ in results) == [0, 1, 2]


async def test_generate_audio_streaming_yields_normal_and_slow_tuple():
    phrases = ["hello"]
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"AUDIO")):
        results = []
        async for idx, total, chunk in generate_audio_streaming(phrases):
            results.append(chunk)
    assert len(results) == 1
    normal, slow = results[0]
    assert normal == b"AUDIO"
    assert slow == b"AUDIO"


async def test_generate_audio_streaming_uses_same_voice_per_phrase():
    phrases = ["alpha", "beta"]
    calls = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        calls.append((phrase, voice_id, speed))
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        async for _ in generate_audio_streaming(phrases):
            pass

    for phrase in phrases:
        phrase_calls = [c for c in calls if c[0] == phrase]
        assert len(phrase_calls) == 2
        assert phrase_calls[0][1] == phrase_calls[1][1]


async def test_generate_audio_streaming_uses_correct_language_pool():
    phrases = ["une phrase"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="fr-FR"):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        async for _ in generate_audio_streaming(phrases, language="French"):
            pass

    assert all(v in VOICE_POOLS["French"] for v in used_voices)


async def test_generate_audio_streaming_falls_back_to_english_for_unknown_language():
    phrases = ["hello"]
    used_voices = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en-US"):
        used_voices.append(voice_id)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        async for _ in generate_audio_streaming(phrases, language="Klingon"):
            pass

    assert all(v in VOICE_POOLS["English"] for v in used_voices)


async def test_generate_audio_streaming_empty_list():
    with patch("services.tts_service.generate_audio_for_phrase", new=AsyncMock(return_value=b"")):
        results = []
        async for item in generate_audio_streaming([]):
            results.append(item)
    assert results == []

# Google TTS Migration & Monthly Minute Cap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RunPod/Kokoro TTS with Google Cloud TTS, add monthly minute caps per plan, and add a paywall upgrade flow — reducing per-session TTS cost ~6-7x.

**Architecture:** `tts_service.py` is fully replaced (same public interfaces, new provider). `plans.py` gains `minutes_per_month`. `limit_checker.py` enforces it via a SUM query. `routers/user.py` exposes usage data. Frontend gains a usage bar, pre-submit guard, and 429 upgrade modal.

**Tech Stack:** `google-cloud-texttospeech` (Python SDK), Google Cloud TTS Neural2/WaveNet, Stripe (existing), FastAPI (existing), vanilla JS (existing frontend).

---

## File Map

| File | Change |
|---|---|
| `backend/requirements.txt` | Add `google-cloud-texttospeech` |
| `backend/config.py` | Add `GOOGLE_TTS_API_KEY` |
| `backend/.env.example` | Swap RunPod vars for Google var |
| `backend/services/tts_service.py` | Full rewrite — Google TTS |
| `backend/tests/unit/test_tts_service.py` | Full rewrite — new mocks |
| `backend/plans.py` | Add `minutes_per_month` to TypedDict + all plans |
| `backend/services/limit_checker.py` | Replace session-count with minute-sum for free/pro |
| `backend/tests/unit/test_limit_checker.py` | Update free/pro tests; add pro monthly cap tests |
| `backend/tests/conftest.py` | Add `GOOGLE_TTS_API_KEY` env default; remove Kokoro helper |
| `backend/routers/user.py` | Extend `GET /settings` with `minutes_used_this_month` + `minutes_limit` |
| `frontend/index.html` | Add language options, usage bar, 429 modal, pre-submit guard |

---

## Task 1: Add dependency and config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add `google-cloud-texttospeech` to requirements**

In `backend/requirements.txt`, add after `tenacity`:
```
google-cloud-texttospeech
```

- [ ] **Step 2: Add `GOOGLE_TTS_API_KEY` to `config.py`**

In `backend/config.py`, replace the TTS App specific block:
```python
    # ── TTS App specific ──────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GOOGLE_TTS_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "audio-sessions"
    SESSION_TTL_HOURS: int = 3
    MAX_GENERATION_TIMEOUT_SECONDS: int = 120
    FRONTEND_ORIGIN: str = "*"
```
(Remove `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`, `TTS_API_KEY`.)

- [ ] **Step 3: Update `.env.example`**

Replace:
```
OPENAI_API_KEY=
RUNPOD_ENDPOINT_ID=2r9htace1yaroi
RUNPOD_API_KEY=<your RunPod API key>
TTS_API_KEY=<shared secret — must match TTS_API_KEY configured in the RunPod worker>
MAX_GENERATION_TIMEOUT_SECONDS=120
```

With:
```
OPENAI_API_KEY=
# Google Cloud TTS — create a key at console.cloud.google.com → APIs & Services → Credentials
GOOGLE_TTS_API_KEY=<your Google Cloud TTS API key>
MAX_GENERATION_TIMEOUT_SECONDS=120
```

- [ ] **Step 4: Install the new dependency**

```bash
cd backend
pip install google-cloud-texttospeech
```

- [ ] **Step 5: Run tests to confirm nothing broke**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests pass (config change is backward-compatible; old env vars are just ignored now).

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/.env.example
git commit -m "feat: add google-cloud-texttospeech dependency and GOOGLE_TTS_API_KEY config"
```

---

## Task 2: Rewrite `test_tts_service.py` (TDD — failing tests first)

**Files:**
- Modify: `backend/tests/unit/test_tts_service.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Update `conftest.py`**

Replace the Kokoro helper and add Google TTS env default. The new `conftest.py` block at the top (`os.environ.setdefault` section) should add:
```python
os.environ.setdefault("GOOGLE_TTS_API_KEY", "test-google-tts-key")
```

Also remove the `make_kokoro_response` function (it is not used by any test).

- [ ] **Step 2: Fully replace `test_tts_service.py`**

Write this complete file:

```python
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

def test_synthesize_sync_wraps_slow_audio_in_ssml():
    """When slow=True, the text sent to Google must be SSML with prosody rate."""
    from services.tts_service import _synthesize_sync, SLOW_RATE
    from google.cloud import texttospeech

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.audio_content = b"AUDIO"
    mock_client.synthesize_speech.return_value = mock_response

    with patch("services.tts_service._get_client", return_value=mock_client):
        _synthesize_sync("Hello world", "en-US-Neural2-A", "en-US", slow=True)

    call_kwargs = mock_client.synthesize_speech.call_args[1]
    input_arg = call_kwargs["input"]
    # Proto-plus: ssml is set (non-empty) for slow audio
    assert input_arg.ssml  # non-empty
    assert SLOW_RATE in input_arg.ssml
    assert "Hello world" in input_arg.ssml


def test_synthesize_sync_uses_plain_text_for_normal_speed():
    """When slow=False, text input must NOT use SSML."""
    from services.tts_service import _synthesize_sync
    from google.cloud import texttospeech

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.audio_content = b"AUDIO"
    mock_client.synthesize_speech.return_value = mock_response

    with patch("services.tts_service._get_client", return_value=mock_client):
        _synthesize_sync("Hello world", "en-US-Neural2-A", "en-US", slow=False)

    call_kwargs = mock_client.synthesize_speech.call_args[1]
    input_arg = call_kwargs["input"]
    # Proto-plus: text is set (non-empty), ssml is empty for normal audio
    assert input_arg.text == "Hello world"
    assert not input_arg.ssml  # empty for plain text


def test_synthesize_sync_returns_audio_content():
    from services.tts_service import _synthesize_sync

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.audio_content = b"REAL_AUDIO"
    mock_client.synthesize_speech.return_value = mock_response

    with patch("services.tts_service._get_client", return_value=mock_client):
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
```

- [ ] **Step 3: Run tests to confirm they fail (expected)**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v
```

Expected: FAIL — `ImportError` or `AssertionError` because `tts_service.py` still uses RunPod, `SLOW_RATE` doesn't exist, `_synthesize_sync` doesn't exist, voice names are wrong.

---

## Task 3: Implement new `tts_service.py` (make Task 2 tests pass)

**Files:**
- Modify: `backend/services/tts_service.py`

- [ ] **Step 1: Replace `tts_service.py` entirely**

```python
import asyncio
import logging
import random
from typing import AsyncGenerator

from google.cloud import texttospeech
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

VOICE_POOLS = {
    "English":             ["en-US-Neural2-A", "en-US-Neural2-C", "en-US-Neural2-D", "en-US-Neural2-F", "en-US-Neural2-H"],
    "English (UK)":        ["en-GB-Neural2-A", "en-GB-Neural2-B", "en-GB-Neural2-C", "en-GB-Neural2-D"],
    "Spanish":             ["es-ES-Neural2-A", "es-ES-Neural2-B", "es-US-Neural2-A"],
    "Portuguese (Brazil)": ["pt-BR-Neural2-A", "pt-BR-Neural2-B", "pt-BR-Neural2-C"],
    "French":              ["fr-FR-Neural2-A", "fr-FR-Neural2-B", "fr-FR-Neural2-C"],
    "Italian":             ["it-IT-Neural2-A", "it-IT-Neural2-C"],
    "Japanese":            ["ja-JP-Neural2-B", "ja-JP-Neural2-C", "ja-JP-Neural2-D"],
    "Chinese":             ["cmn-CN-Wavenet-A", "cmn-CN-Wavenet-B", "cmn-CN-Wavenet-C", "cmn-CN-Wavenet-D"],
    "German":              ["de-DE-Neural2-A", "de-DE-Neural2-B", "de-DE-Neural2-C", "de-DE-Neural2-D"],
    "Korean":              ["ko-KR-Neural2-A", "ko-KR-Neural2-B", "ko-KR-Neural2-C"],
    "Hindi":               ["hi-IN-Neural2-A", "hi-IN-Neural2-B", "hi-IN-Neural2-C", "hi-IN-Neural2-D"],
    "Arabic":              ["ar-XA-Wavenet-A", "ar-XA-Wavenet-B", "ar-XA-Wavenet-C", "ar-XA-Wavenet-D"],
    "Russian":             ["ru-RU-Wavenet-A", "ru-RU-Wavenet-B", "ru-RU-Wavenet-C", "ru-RU-Wavenet-D"],
    "Dutch":               ["nl-NL-Neural2-A", "nl-NL-Neural2-B", "nl-NL-Neural2-C", "nl-NL-Neural2-D"],
    "Polish":              ["pl-PL-Wavenet-A", "pl-PL-Wavenet-B", "pl-PL-Wavenet-C"],
    "Swedish":             ["sv-SE-Wavenet-A", "sv-SE-Wavenet-B", "sv-SE-Wavenet-C", "sv-SE-Wavenet-D"],
    "Turkish":             ["tr-TR-Wavenet-A", "tr-TR-Wavenet-B", "tr-TR-Wavenet-C", "tr-TR-Wavenet-D"],
    "Vietnamese":          ["vi-VN-Wavenet-A", "vi-VN-Wavenet-B", "vi-VN-Wavenet-C", "vi-VN-Wavenet-D"],
}

LANGUAGE_CODES = {
    "English":             "en-US",
    "English (UK)":        "en-GB",
    "Spanish":             "es-ES",
    "Portuguese (Brazil)": "pt-BR",
    "French":              "fr-FR",
    "Italian":             "it-IT",
    "Japanese":            "ja-JP",
    "Chinese":             "cmn-CN",
    "German":              "de-DE",
    "Korean":              "ko-KR",
    "Hindi":               "hi-IN",
    "Arabic":              "ar-XA",
    "Russian":             "ru-RU",
    "Dutch":               "nl-NL",
    "Polish":              "pl-PL",
    "Swedish":             "sv-SE",
    "Turkish":             "tr-TR",
    "Vietnamese":          "vi-VN",
}

SLOW_SPEED = 0.7
SLOW_RATE = "75%"


def _get_client() -> texttospeech.TextToSpeechClient:
    return texttospeech.TextToSpeechClient()


def _synthesize_sync(text: str, voice_name: str, lang_code: str, slow: bool) -> bytes:
    """Synchronous Google TTS call. Runs in a thread pool via asyncio.to_thread."""
    client = _get_client()
    if slow:
        input_ = texttospeech.SynthesisInput(
            ssml=f'<speak><prosody rate="{SLOW_RATE}">{text}</prosody></speak>'
        )
    else:
        input_ = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = client.synthesize_speech(input=input_, voice=voice, audio_config=audio_config)
    return response.audio_content


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def generate_audio_for_phrase(
    phrase: str, voice_id: str, speed: float = 1.0, lang: str = "en-US"
) -> bytes:
    slow = speed < 1.0
    return await asyncio.to_thread(_synthesize_sync, phrase, voice_id, lang, slow)


async def generate_audio_streaming(
    phrases: list[str],
    language: str = "English",
) -> AsyncGenerator[tuple[int, int, tuple[bytes, bytes]], None]:
    """Yields (index, total, (normal_bytes, slow_bytes)) as each phrase completes."""
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    lang = LANGUAGE_CODES.get(language, "en-US")
    total = len(phrases)
    sem = asyncio.Semaphore(4)

    async def _bounded(i: int, phrase: str) -> tuple[int, tuple[bytes, bytes]]:
        voice = random.choice(voice_pool)
        async with sem:
            normal = await generate_audio_for_phrase(phrase, voice, speed=1.0, lang=lang)
            slow = await generate_audio_for_phrase(phrase, voice, speed=SLOW_SPEED, lang=lang)
        return i, (normal, slow)

    tasks = [asyncio.create_task(_bounded(i, p)) for i, p in enumerate(phrases)]
    for fut in asyncio.as_completed(tasks):
        i, chunk = await fut
        yield i, total, chunk


async def generate_all_audio(phrases: list[str], language: str = "English") -> list[tuple[bytes, bytes]]:
    """Generate normal and slow audio for each phrase using the same voice."""
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    lang = LANGUAGE_CODES.get(language, "en-US")
    sem = asyncio.Semaphore(4)

    async def _bounded(phrase: str) -> tuple[bytes, bytes]:
        voice = random.choice(voice_pool)
        async with sem:
            normal = await generate_audio_for_phrase(phrase, voice, speed=1.0, lang=lang)
        async with sem:
            slow = await generate_audio_for_phrase(phrase, voice, speed=SLOW_SPEED, lang=lang)
        return normal, slow

    return await asyncio.gather(*[_bounded(p) for p in phrases])
```

- [ ] **Step 2: Run `test_tts_service.py` and confirm it passes**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run full suite to confirm no regressions**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests PASS. (Integration tests patch `generate_audio_for_phrase` directly — unchanged interface.)

- [ ] **Step 4: Commit**

```bash
git add backend/services/tts_service.py backend/tests/unit/test_tts_service.py backend/tests/conftest.py
git commit -m "feat: replace RunPod/Kokoro TTS with Google Cloud TTS Neural2/WaveNet"
```

---

## Task 4: Update `plans.py` — add `minutes_per_month`

**Files:**
- Modify: `backend/plans.py`

- [ ] **Step 1: Add `minutes_per_month` to `PlanLimits` TypedDict**

In `plans.py`, update the TypedDict:
```python
class PlanLimits(TypedDict):
    requests_per_hour: int
    sessions_per_day: int
    sessions_per_month: int
    max_duration_minutes: int
    minutes_per_month: int
```

- [ ] **Step 2: Update plan definitions**

Replace the `PLANS` dict with:
```python
PLANS: dict[str, Plan] = {
    "guest": {
        "key": "guest",
        "name": "Guest",
        "price": 0.0,
        "stripe_price_id": "",
        "trial_days": 0,
        "limits": {
            "requests_per_hour": 10,
            "sessions_per_day": 1,
            "sessions_per_month": 0,
            "max_duration_minutes": 5,
            "minutes_per_month": 5,
        },
    },
    "free": {
        "key": "free",
        "name": "Free",
        "price": 0.0,
        "stripe_price_id": "",
        "trial_days": 0,
        "limits": {
            "requests_per_hour": 20,
            "sessions_per_day": 0,
            "sessions_per_month": 0,
            "max_duration_minutes": 15,
            "minutes_per_month": 30,
        },
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price": 9.0,
        "stripe_price_id": "price_placeholder_pro",  # EDIT: replace with real Stripe price ID
        "trial_days": 14,
        "limits": {
            "requests_per_hour": 500,
            "sessions_per_day": 0,
            "sessions_per_month": 0,
            "max_duration_minutes": 30,
            "minutes_per_month": 120,
        },
    },
}
```

- [ ] **Step 3: Run full test suite**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests PASS (no test directly checks the plan values except indirectly).

- [ ] **Step 4: Commit**

```bash
git add backend/plans.py
git commit -m "feat: add minutes_per_month limits to all plans; set pro price to 9.00"
```

---

## Task 5: Rewrite `test_limit_checker.py` (TDD — failing tests first)

**Files:**
- Modify: `backend/tests/unit/test_limit_checker.py`

- [ ] **Step 1: Replace `test_limit_checker.py` entirely**

```python
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
    """15 min used + 5 requested = 20 ≤ 30 → allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(15)  # 15 minutes used this month
    user = _make_user("free")
    await check_generation_limits(db, 5, user=user, guest_id=None)


async def test_free_user_exactly_at_monthly_limit():
    """25 min used + 5 requested = 30 = 30 → allowed (not over)."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(25)
    user = _make_user("free")
    await check_generation_limits(db, 5, user=user, guest_id=None)


async def test_free_user_over_monthly_limit():
    """25 min used + 10 requested = 35 > 30 → 429."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(25)
    user = _make_user("free")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 10, user=user, guest_id=None)
    assert exc_info.value.status_code == 429
    assert "Free plan limit reached" in exc_info.value.detail
    assert "Upgrade to Pro" in exc_info.value.detail


async def test_free_user_max_duration_exceeded():
    """Requesting 20 min > max_duration(15) → 403 (duration check, before monthly check)."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("free")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 20, user=user, guest_id=None)
    assert exc_info.value.status_code == 403


# ── Pro plan tests ────────────────────────────────────────────────────────────

async def test_pro_user_under_monthly_limit():
    """60 min used + 30 requested = 90 ≤ 120 → allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(60)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_exactly_at_monthly_limit():
    """90 min used + 30 requested = 120 = 120 → allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(90)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_over_monthly_limit():
    """100 min used + 30 requested = 130 > 120 → 429."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(100)
    user = _make_user("pro")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 30, user=user, guest_id=None)
    assert exc_info.value.status_code == 429
    assert "Pro plan limit reached" in exc_info.value.detail


async def test_pro_user_max_duration_allowed():
    """30 min is the max duration for pro → allowed."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("pro")
    await check_generation_limits(db, 30, user=user, guest_id=None)


async def test_pro_user_duration_exceeded():
    """Pro max is 30 min; 31 → 403."""
    from services.limit_checker import check_generation_limits
    db = _make_db_with_value(0)
    user = _make_user("pro")
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_limits(db, 31, user=user, guest_id=None)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: Run tests to confirm they fail (expected)**

```bash
cd backend
python -m pytest tests/unit/test_limit_checker.py -v
```

Expected: FAIL — the new pro monthly limit tests and updated free tests fail because `limit_checker.py` still uses session count logic.

---

## Task 6: Implement updated `limit_checker.py`

**Files:**
- Modify: `backend/services/limit_checker.py`

- [ ] **Step 1: Replace the free/pro enforcement block**

Replace the entire content of `limit_checker.py` with:

```python
"""
services/limit_checker.py — Enforce per-plan session generation limits.

Called from generate_session() before the session is created.
Raises HTTPException 403 if duration exceeds the plan's max.
Raises HTTPException 429 if the monthly minute budget is exceeded.
Raises HTTPException 400 if guest requests without a guest_id.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session_model import TtsSession
from models.user import User
from plans import get_plan


async def check_generation_limits(
    db: AsyncSession,
    duration_minutes: int,
    user: User | None,
    guest_id: str | None,
) -> None:
    """
    Enforce limits before creating a new TTS session.

    - user=None, guest_id set  → guest plan (1 session/day, max 5 min)
    - user set, plan="free"    → free plan (30 min/month, max 15 min/session)
    - user set, plan="pro"     → pro plan (120 min/month, max 30 min/session)
    """
    plan_key = "guest" if user is None else user.plan
    plan = get_plan(plan_key)
    limits = plan["limits"]

    # 1. Duration check (applies to all plans)
    max_duration = limits["max_duration_minutes"]
    if duration_minutes > max_duration:
        if plan_key == "guest":
            msg = f"Guests can generate up to {max_duration} min sessions. Sign up for longer sessions."
        elif plan_key == "free":
            msg = f"Free plan allows up to {max_duration} min sessions. Upgrade to Pro for up to 30 min."
        else:
            msg = f"Maximum session duration is {max_duration} minutes."
        raise HTTPException(status_code=403, detail=msg)

    # 2. Guest: session count per day
    if plan_key == "guest":
        if not guest_id:
            raise HTTPException(
                status_code=400,
                detail="X-Guest-ID header required for unauthenticated requests",
            )
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await db.execute(
            select(func.count(TtsSession.id)).where(
                TtsSession.guest_id == guest_id,
                TtsSession.created_at >= today_start,
            )
        )
        count = count_result.scalar_one()
        daily_limit = limits["sessions_per_day"]
        if count >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Guest limit reached: {daily_limit} session(s) per day. Sign up for a free account.",
            )

    # 3. Free / Pro: monthly minute budget
    elif plan_key in ("free", "pro"):
        minutes_limit = limits["minutes_per_month"]
        if minutes_limit > 0:
            month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            result = await db.execute(
                select(func.coalesce(func.sum(TtsSession.duration_minutes), 0)).where(
                    TtsSession.user_id == user.id,
                    TtsSession.created_at >= month_start,
                    TtsSession.status != "error",
                )
            )
            minutes_used = result.scalar_one()
            if minutes_used + duration_minutes > minutes_limit:
                remaining = max(0, minutes_limit - minutes_used)
                if plan_key == "free":
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Free plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                            f"{remaining} min remaining. Upgrade to Pro for 120 min/month."
                        ),
                    )
                else:
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Pro plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                            f"{remaining} min remaining."
                        ),
                    )
```

- [ ] **Step 2: Run `test_limit_checker.py` and confirm it passes**

```bash
cd backend
python -m pytest tests/unit/test_limit_checker.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run full test suite**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/services/limit_checker.py backend/tests/unit/test_limit_checker.py
git commit -m "feat: enforce monthly minute budget for free/pro plans in limit_checker"
```

---

## Task 7: Extend user settings endpoint with usage data

**Files:**
- Modify: `backend/routers/user.py`

The `GET /api/user/settings` endpoint needs to return `minutes_used_this_month` and `minutes_limit` so the frontend can render the usage bar and pre-submit guard.

- [ ] **Step 1: Update `GET /settings` in `routers/user.py`**

Replace the `get_settings` function:

```python
@router.get("/settings")
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's settings including monthly usage."""
    from datetime import datetime, timezone
    from sqlalchemy import func, select
    from models.session_model import TtsSession
    from plans import get_plan

    plan = get_plan(user.plan)
    minutes_limit = plan["limits"]["minutes_per_month"]

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.coalesce(func.sum(TtsSession.duration_minutes), 0)).where(
            TtsSession.user_id == user.id,
            TtsSession.created_at >= month_start,
            TtsSession.status != "error",
        )
    )
    minutes_used = result.scalar_one()

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "plan": user.plan,
        "is_admin": user.is_admin,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at,
        "minutes_used_this_month": minutes_used,
        "minutes_limit": minutes_limit,
    }
```

- [ ] **Step 2: Run full test suite**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/user.py
git commit -m "feat: expose minutes_used_this_month and minutes_limit in user settings endpoint"
```

---

## Task 8: Frontend — language list, usage bar, and paywall

**Files:**
- Modify: `frontend/index.html`

### Part A — Add new languages to `<select>`

- [ ] **Step 1: Expand the language dropdown**

Find the `<select id="language-select">` block and replace its content with:

```html
<select id="language-select">
  <option value="English" selected>English</option>
  <option value="English (UK)">English (UK)</option>
  <option value="Spanish">Spanish</option>
  <option value="Portuguese (Brazil)">Portuguese (Brazil)</option>
  <option value="French">French</option>
  <option value="German">German</option>
  <option value="Italian">Italian</option>
  <option value="Japanese">Japanese</option>
  <option value="Chinese">Chinese</option>
  <option value="Korean">Korean</option>
  <option value="Russian">Russian</option>
  <option value="Hindi">Hindi</option>
  <option value="Arabic">Arabic</option>
  <option value="Dutch">Dutch</option>
  <option value="Polish">Polish</option>
  <option value="Swedish">Swedish</option>
  <option value="Turkish">Turkish</option>
  <option value="Vietnamese">Vietnamese</option>
</select>
```

### Part B — Usage bar (authenticated users only)

- [ ] **Step 2: Add usage bar HTML**

After the `<select id="language-select">` field div (and before the topic field div), add:

```html
<!-- Usage bar — shown only for authenticated users -->
<div id="usage-bar-container" style="display:none; margin-bottom:12px;">
  <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted); margin-bottom:4px;">
    <span id="usage-bar-label">0 / 120 min used this month</span>
    <a id="usage-upgrade-link" href="#" style="display:none; color:var(--accent); text-decoration:none; font-size:0.75rem;">Upgrade for more</a>
  </div>
  <div style="height:4px; background:var(--border); border-radius:2px; overflow:hidden;">
    <div id="usage-bar-fill" style="height:100%; background:var(--accent); width:0%; transition:width 0.3s;"></div>
  </div>
</div>
```

### Part C — Upgrade modal HTML

- [ ] **Step 3: Add upgrade modal markup**

Before the closing `</body>` tag (or after the last `</div>` of the last view), add:

```html
<!-- ═══════════════════════════════════════════
     Upgrade Modal
════════════════════════════════════════════════ -->
<div id="upgrade-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:1000; align-items:center; justify-content:center;">
  <div style="background:var(--card-bg,#1e1e1e); border:1px solid var(--border); border-radius:12px; padding:32px; max-width:380px; width:90%; text-align:center;">
    <h3 style="margin:0 0 12px; font-size:1.1rem;" id="upgrade-modal-title">Monthly limit reached</h3>
    <p style="margin:0 0 24px; font-size:0.9rem; color:var(--text-muted);" id="upgrade-modal-body"></p>
    <div style="display:flex; gap:10px; justify-content:center; flex-wrap:wrap;">
      <button class="btn" id="upgrade-modal-cta" style="min-width:160px;">Upgrade to Pro — $9/mo</button>
      <button class="btn btn-secondary" id="upgrade-modal-dismiss">Dismiss</button>
    </div>
  </div>
</div>
```

### Part D — JavaScript: fetch usage, render bar, guard, and 429 handler

- [ ] **Step 4: Add usage-related JS**

Find the JS section starting with `// ─── Guest ID` and add before it:

```javascript
    // ─── Usage bar ────────────────────────────────────────────────────────────
    let userMinutesUsed = 0;
    let userMinutesLimit = 120;

    async function loadUserUsage() {
      const token = localStorage.getItem('auth_token');
      if (!token) return;
      try {
        const res = await fetch(`${API_URL}/api/user/settings`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        userMinutesUsed = data.minutes_used_this_month || 0;
        userMinutesLimit = data.minutes_limit || 120;
        renderUsageBar();
      } catch (_) {}
    }

    function renderUsageBar() {
      const container = document.getElementById('usage-bar-container');
      if (!localStorage.getItem('auth_token')) return;
      container.style.display = 'block';
      const pct = userMinutesLimit > 0 ? Math.min(100, (userMinutesUsed / userMinutesLimit) * 100) : 0;
      document.getElementById('usage-bar-fill').style.width = `${pct}%`;
      document.getElementById('usage-bar-label').textContent =
        `${userMinutesUsed} / ${userMinutesLimit} min used this month`;
      const upgradeLink = document.getElementById('usage-upgrade-link');
      if (pct >= 80) {
        upgradeLink.style.display = 'inline';
        upgradeLink.onclick = (e) => { e.preventDefault(); triggerUpgrade(); };
      }
    }

    function getRemainingMinutes() {
      return Math.max(0, userMinutesLimit - userMinutesUsed);
    }
```

- [ ] **Step 5: Add upgrade modal JS**

Add after the `renderUsageBar` and `getRemainingMinutes` functions:

```javascript
    // ─── Upgrade modal ────────────────────────────────────────────────────────
    function showUpgradeModal(title, body) {
      document.getElementById('upgrade-modal-title').textContent = title;
      document.getElementById('upgrade-modal-body').textContent = body;
      const modal = document.getElementById('upgrade-modal');
      modal.style.display = 'flex';
    }

    function triggerUpgrade() {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        window.location.href = '/login.html';
        return;
      }
      fetch(`${API_URL}/api/billing/checkout/pro`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(d => { if (d.url) window.location.href = d.url; })
        .catch(() => alert('Could not start checkout. Please try again.'));
    }

    document.getElementById('upgrade-modal-cta').addEventListener('click', triggerUpgrade);
    document.getElementById('upgrade-modal-dismiss').addEventListener('click', () => {
      document.getElementById('upgrade-modal').style.display = 'none';
    });
```

- [ ] **Step 6: Add pre-submit guard to duration button handler**

Find the duration button click handler:
```javascript
    document.getElementById('duration-group').addEventListener('click', e => {
      const btn = e.target.closest('.duration-btn');
      if (!btn) return;
      document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedDuration = parseInt(btn.dataset.min, 10);
    });
```

Replace with:
```javascript
    document.getElementById('duration-group').addEventListener('click', e => {
      const btn = e.target.closest('.duration-btn');
      if (!btn) return;
      document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedDuration = parseInt(btn.dataset.min, 10);
      checkDurationAgainstBudget();
    });

    function checkDurationAgainstBudget() {
      const token = localStorage.getItem('auth_token');
      if (!token) return; // guests get server-side error
      const errEl = document.getElementById('form-error');
      const remaining = getRemainingMinutes();
      const generateBtn = document.getElementById('btn-generate');
      if (selectedDuration > remaining) {
        errEl.textContent = `You've used ${userMinutesUsed} of ${userMinutesLimit} min this month. `
          + `Select a shorter duration or upgrade your plan.`;
        errEl.style.display = 'block';
        generateBtn.disabled = true;
      } else {
        errEl.style.display = 'none';
        generateBtn.disabled = false;
      }
    }
```

- [ ] **Step 7: Update the `btn-confirm` 429 handler**

Find the confirm button handler and replace the `if (!res.ok) throw new Error(...)` line inside it with:

```javascript
        if (!res.ok) {
          if (res.status === 429) {
            const errData = await res.json().catch(() => ({}));
            const plan = localStorage.getItem('user_plan') || 'free';
            showUpgradeModal(
              'Monthly limit reached',
              errData.detail || (plan === 'pro'
                ? 'You have used all your Pro plan minutes this month.'
                : 'You have used all 30 minutes included in your Free plan. Upgrade to Pro for 120 min/month.')
            );
            btn.disabled = false;
            btn.textContent = 'Start Generating';
            return;
          }
          throw new Error(`Server error: ${res.status}`);
        }
```

- [ ] **Step 8: Call `loadUserUsage()` on page load**

Find the script's initialization section (where `guestId` is set) and add at the end of the init block:

```javascript
    loadUserUsage();
```

- [ ] **Step 9: Manual smoke test**

Open the frontend at `http://localhost:8000` and verify:
- New languages appear in the dropdown
- Usage bar appears when logged in
- Usage bar shows correct values
- Selecting a duration larger than remaining minutes shows inline error and disables Generate

- [ ] **Step 10: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add language options, usage bar, and paywall upgrade modal to frontend"
```

---

## Final verification

- [ ] **Run complete test suite one last time**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests PASS with no failures.

- [ ] **Check CLAUDE.md compliance**

Verify the following are done:
- All tests pass
- `GOOGLE_TTS_API_KEY` is in `.env.example` but NOT committed to `.env`
- `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, `TTS_API_KEY` removed from `config.py` and `.env.example`
- Real Stripe price ID must be inserted into `plans.py` before going live (placeholder remains until then)

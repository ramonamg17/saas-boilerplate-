# RunPod Kokoro TTS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the abandoned in-repo RunPod worker, update `tts_service.py` to the new endpoint's API contract, fix VOICE_POOLS/LANGUAGE_CODES, and update tests and docs.

**Architecture:** `tts_service.py` calls RunPod's async `/run` endpoint, polls `/status/{job_id}` until COMPLETED, and returns decoded MP3 bytes. Language names are resolved to lang codes via a new `LANGUAGE_CODES` dict before being passed to the API.

**Tech Stack:** Python 3.11, httpx, tenacity, RunPod REST API (`api.runpod.ai/v2`)

---

## File Map

| File | Action | What changes |
|---|---|---|
| `runpod_serverless/` | **Delete** | Entire directory (handler.py + Dockerfile) |
| `backend/config.py` | **Modify** | Add `TTS_API_KEY: str = ""` |
| `backend/.env.example` | **Modify** | Remove `TTS_SERVICE_URL`, add `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, `TTS_API_KEY` |
| `backend/services/tts_service.py` | **Modify** | New VOICE_POOLS, LANGUAGE_CODES, updated `generate_audio_for_phrase`, updated callers |
| `backend/tests/unit/test_tts_service.py` | **Modify** | Update/add/remove tests to match new API |
| `CLAUDE.md` | **Modify** | Add Kokoro TTS service section, update env vars list |

---

## Task 1: Delete dead code, add TTS_API_KEY to config

**Files:**
- Delete: `runpod_serverless/` (whole directory)
- Modify: `backend/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Delete the runpod_serverless directory**

```bash
rm -rf runpod_serverless
```

- [ ] **Step 2: Add TTS_API_KEY to config.py**

In `backend/config.py`, add after `RUNPOD_ENDPOINT_ID: str = ""`:
```python
TTS_API_KEY: str = ""
```

The relevant block after the change (lines ~53-63):
```python
    # ── TTS App specific ──────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    TTS_SERVICE_URL: str = "http://localhost:8880"
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_ID: str = ""
    TTS_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "audio-sessions"
    SESSION_TTL_HOURS: int = 3
    MAX_GENERATION_TIMEOUT_SECONDS: int = 120
    FRONTEND_ORIGIN: str = "*"
```

- [ ] **Step 3: Update .env.example**

Replace the `TTS App` section in `backend/.env.example`. The old file has:
```
TTS_SERVICE_URL=http://localhost:8880
```

Replace the entire TTS App section with:
```
# ── TTS App ───────────────────────────────────────────────────────────
OPENAI_API_KEY=
RUNPOD_ENDPOINT_ID=2r9htace1yaroi
RUNPOD_API_KEY=<your RunPod API key>
TTS_API_KEY=<shared secret — must match TTS_API_KEY configured in the RunPod worker>
MAX_GENERATION_TIMEOUT_SECONDS=120
```

- [ ] **Step 4: Run tests to confirm nothing broke**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all 68 tests pass (config change is additive, no behavior change yet).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add TTS_API_KEY to config, remove runpod_serverless directory"
```

---

## Task 2: Update VOICE_POOLS, add LANGUAGE_CODES (TDD)

**Files:**
- Modify: `backend/tests/unit/test_tts_service.py`
- Modify: `backend/services/tts_service.py`

- [ ] **Step 1: Update the failing test for supported languages**

In `backend/tests/unit/test_tts_service.py`, replace `test_voice_pools_covers_all_supported_languages`:

```python
def test_voice_pools_covers_all_supported_languages():
    supported = {
        "English", "English (UK)", "Spanish", "Portuguese (Brazil)",
        "French", "Italian", "Japanese", "Chinese"
    }
    assert supported == set(VOICE_POOLS.keys())
```

- [ ] **Step 2: Add import and test for LANGUAGE_CODES**

At the top of the test file, update the import to include `LANGUAGE_CODES`:
```python
from services.tts_service import (
    VOICE_POOLS,
    LANGUAGE_CODES,
    RUNPOD_ENDPOINT_ID,
    generate_audio_for_phrase,
    generate_all_audio,
    generate_audio_streaming,
)
```

Add after the VOICE_POOLS tests:
```python
# ── LANGUAGE_CODES ────────────────────────────────────────────────────────────

def test_language_codes_covers_all_supported_languages():
    assert set(LANGUAGE_CODES.keys()) == set(VOICE_POOLS.keys())


def test_language_codes_correct_values():
    assert LANGUAGE_CODES["English"] == "en"
    assert LANGUAGE_CODES["English (UK)"] == "en-gb"
    assert LANGUAGE_CODES["Spanish"] == "es"
    assert LANGUAGE_CODES["Portuguese (Brazil)"] == "pt-br"
    assert LANGUAGE_CODES["French"] == "fr"
    assert LANGUAGE_CODES["Italian"] == "it"
    assert LANGUAGE_CODES["Japanese"] == "ja"
    assert LANGUAGE_CODES["Chinese"] == "zh"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v -k "language"
```

Expected: FAIL — `test_voice_pools_covers_all_supported_languages` fails (wrong keys), `LANGUAGE_CODES` import fails.

- [ ] **Step 4: Replace VOICE_POOLS and add LANGUAGE_CODES in tts_service.py**

In `backend/services/tts_service.py`, replace the `VOICE_POOLS` dict:

```python
VOICE_POOLS = {
    "English":             ["af_heart", "af_bella", "am_adam", "af_nova", "am_michael"],
    "English (UK)":        ["bf_emma", "bf_alice", "bm_george", "bm_daniel"],
    "Spanish":             ["ef_dora", "em_alex", "em_santa"],
    "Portuguese (Brazil)": ["pf_dora", "pm_alex", "pm_santa"],
    "French":              ["ff_siwis"],
    "Italian":             ["if_sara", "im_nicola"],
    "Japanese":            ["jf_alpha", "jf_gongitsune", "jm_kumo"],
    "Chinese":             ["zf_xiaobei", "zf_xiaoni", "zm_yunxi", "zm_yunyang"],
}

LANGUAGE_CODES = {
    "English":             "en",
    "English (UK)":        "en-gb",
    "Spanish":             "es",
    "Portuguese (Brazil)": "pt-br",
    "French":              "fr",
    "Italian":             "it",
    "Japanese":            "ja",
    "Chinese":             "zh",
}
```

- [ ] **Step 5: Update the English voice test to match new pool**

The test `test_voice_pools_english_contains_expected_voices` checks for `"am_adam"` which is still present. But `af_heart` and `af_bella` are also still there, so this test should still pass. Verify by running:

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py::test_voice_pools_english_contains_expected_voices -v
```

Expected: PASS (no change needed).

- [ ] **Step 6: Run all VOICE_POOLS and LANGUAGE_CODES tests**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v -k "voice_pool or language_code"
```

Expected: all related tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/services/tts_service.py backend/tests/unit/test_tts_service.py
git commit -m "feat: replace VOICE_POOLS with correct voices, add LANGUAGE_CODES dict"
```

---

## Task 3: Update generate_audio_for_phrase to new API (TDD)

**Files:**
- Modify: `backend/tests/unit/test_tts_service.py`
- Modify: `backend/services/tts_service.py`

The new API flow:
1. POST `https://api.runpod.ai/v2/{endpoint_id}/run` with `{"input": {...}}`
2. Response: `{"id": "job-123"}`
3. GET `https://api.runpod.ai/v2/{endpoint_id}/status/job-123` every 5s
4. Response when done: `{"status": "COMPLETED", "output": {"audio_base64": "..."}}`

- [ ] **Step 1: Replace helper functions in test file**

In `backend/tests/unit/test_tts_service.py`, replace `make_runpod_response` with two helpers:

```python
def make_run_response(job_id: str = "job-123") -> MagicMock:
    """Mock for POST /run — returns job id."""
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"id": job_id}
    return mock


def make_status_response(audio: bytes = b"FAKE_MP3_AUDIO_DATA") -> MagicMock:
    """Mock for GET /status/{job_id} — returns COMPLETED with audio."""
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "status": "COMPLETED",
        "output": {"audio_base64": base64.b64encode(audio).decode()},
    }
    return mock
```

- [ ] **Step 2: Write a helper that builds the standard http mock**

Add right after the two helpers above:

```python
def make_http_mock(audio: bytes = b"FAKE_MP3_AUDIO_DATA", job_id: str = "job-123") -> MagicMock:
    """AsyncClient mock wired for /run + /status polling."""
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    mock.post = AsyncMock(return_value=make_run_response(job_id))
    mock.get = AsyncMock(return_value=make_status_response(audio))
    return mock
```

- [ ] **Step 3: Rewrite generate_audio_for_phrase tests**

Replace ALL of the existing `# ── generate_audio_for_phrase` test functions with these:

```python
# ── generate_audio_for_phrase ─────────────────────────────────────────────────

async def test_generate_audio_returns_bytes():
    fake_audio = b"FAKE_MP3_AUDIO_DATA"
    with patch("services.tts_service.httpx.AsyncClient", return_value=make_http_mock(fake_audio)):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            result = await generate_audio_for_phrase("Hello world", "af_heart")
    assert result == fake_audio


async def test_generate_audio_sends_phrase_text():
    phrase = "Je voudrais un café s'il vous plaît"
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase(phrase, "af_heart")
    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"]["text"] == phrase


async def test_generate_audio_sends_voice_id():
    voice_id = "am_adam"
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase("test", voice_id)
    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"]["voice"] == voice_id


async def test_generate_audio_sends_speed_param():
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase("test", "af_heart", speed=0.7)
    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"]["speed"] == 0.7


async def test_generate_audio_sends_lang_param():
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase("test", "af_heart", lang="pt-br")
    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"]["lang"] == "pt-br"


async def test_generate_audio_sends_api_key():
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            with patch("services.tts_service.settings") as mock_settings:
                mock_settings.RUNPOD_API_KEY = "rp_key"
                mock_settings.RUNPOD_ENDPOINT_ID = "ep-test"
                mock_settings.TTS_API_KEY = "secret-key"
                await generate_audio_for_phrase("test", "af_heart")
    _, call_kwargs = mock_http.post.call_args
    assert call_kwargs["json"]["input"]["api_key"] == "secret-key"


async def test_generate_audio_calls_run_endpoint():
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase("test", "af_heart")
    url_arg = mock_http.post.call_args.args[0]
    assert url_arg.endswith("/run")


async def test_generate_audio_sends_authorization_header():
    mock_http = make_http_mock()
    with patch("services.tts_service.httpx.AsyncClient", return_value=mock_http):
        with patch("services.tts_service.asyncio.sleep", new=AsyncMock()):
            await generate_audio_for_phrase("test", "af_heart")
    _, call_kwargs = mock_http.post.call_args
    assert "Authorization" in call_kwargs["headers"]
    assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v -k "generate_audio_for_phrase or generate_audio_returns or generate_audio_sends or generate_audio_calls"
```

Expected: several FAILs (wrong payload field names, wrong endpoint path).

- [ ] **Step 5: Rewrite generate_audio_for_phrase in tts_service.py**

Replace the entire `generate_audio_for_phrase` function (including decorator) with:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_is_retryable_error),
)
async def generate_audio_for_phrase(
    phrase: str, voice_id: str, speed: float = 1.0, lang: str = "en"
) -> bytes:
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"
    headers = {"Authorization": f"Bearer {settings.RUNPOD_API_KEY}"}
    payload = {
        "input": {
            "text": phrase,
            "voice": voice_id,
            "lang": lang,
            "speed": speed,
            "format": "mp3",
            "api_key": settings.TTS_API_KEY,
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{url}/run", json=payload, headers=headers)
        r.raise_for_status()
        job_id = r.json()["id"]

        for _ in range(60):  # up to 5 min (60 × 5s)
            await asyncio.sleep(5)
            r2 = await client.get(f"{url}/status/{job_id}", headers=headers)
            r2.raise_for_status()
            data = r2.json()
            if data["status"] == "COMPLETED":
                return base64.b64decode(data["output"]["audio_base64"])
            if data["status"] == "FAILED":
                raise RuntimeError(f"TTS job failed: {data.get('error', '')[:200]}")

    raise TimeoutError(f"TTS job timed out: {job_id}")
```

Also remove the now-unused `url_status` variable reference (it was in the old implementation).

- [ ] **Step 6: Run the generate_audio_for_phrase tests**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py -v -k "generate_audio_for_phrase or generate_audio_returns or generate_audio_sends or generate_audio_calls"
```

Expected: all PASS.

- [ ] **Step 7: Run full test suite**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests pass. If any test mentions `make_runpod_response` or `runsync`, it means it wasn't updated — fix it before proceeding.

- [ ] **Step 8: Commit**

```bash
git add backend/services/tts_service.py backend/tests/unit/test_tts_service.py
git commit -m "feat: update generate_audio_for_phrase to new RunPod /run + polling API"
```

---

## Task 4: Pass lang through generate_all_audio and generate_audio_streaming

**Files:**
- Modify: `backend/services/tts_service.py`
- Modify: `backend/tests/unit/test_tts_service.py`

- [ ] **Step 1: Add a failing test for lang propagation in generate_all_audio**

In `backend/tests/unit/test_tts_service.py`, add after `test_generate_all_audio_uses_correct_pool_for_language`:

```python
async def test_generate_all_audio_passes_correct_lang_code():
    """generate_all_audio resolves language name to lang code and passes it through."""
    phrases = ["une phrase"]
    received_langs = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en"):
        received_langs.append(lang)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="French")

    assert all(lang == "fr" for lang in received_langs)


async def test_generate_all_audio_unknown_language_passes_en_lang_code():
    phrases = ["hello"]
    received_langs = []

    async def mock_gen(phrase, voice_id, speed=1.0, lang="en"):
        received_langs.append(lang)
        return b"audio"

    with patch("services.tts_service.generate_audio_for_phrase", new=mock_gen):
        await generate_all_audio(phrases, language="Klingon")

    assert all(lang == "en" for lang in received_langs)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/unit/test_tts_service.py::test_generate_all_audio_passes_correct_lang_code tests/unit/test_tts_service.py::test_generate_all_audio_unknown_language_passes_en_lang_code -v
```

Expected: FAIL — `generate_audio_for_phrase` is called without `lang` kwarg.

- [ ] **Step 3: Update generate_all_audio to resolve and pass lang**

In `backend/services/tts_service.py`, update `generate_all_audio`:

```python
async def generate_all_audio(phrases: list[str], language: str = "English") -> list[tuple[bytes, bytes]]:
    """Generate normal and slow audio for each phrase using the same voice.

    Returns a list of (normal_bytes, slow_bytes) tuples, one per phrase.
    """
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    lang = LANGUAGE_CODES.get(language, "en")
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

- [ ] **Step 4: Update generate_audio_streaming to resolve and pass lang**

In `backend/services/tts_service.py`, update `generate_audio_streaming`:

```python
async def generate_audio_streaming(
    phrases: list[str],
    language: str = "English",
) -> AsyncGenerator[tuple[int, int, tuple[bytes, bytes]], None]:
    """Yields (index, total, (normal_bytes, slow_bytes)) as each phrase completes."""
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    lang = LANGUAGE_CODES.get(language, "en")
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
```

- [ ] **Step 5: Run full test suite**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/services/tts_service.py backend/tests/unit/test_tts_service.py
git commit -m "feat: pass lang code through generate_all_audio and generate_audio_streaming"
```

---

## Task 5: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Environment variables section**

In `CLAUDE.md`, replace the Environment variables section:

```markdown
## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in:
```
OPENAI_API_KEY=
RUNPOD_ENDPOINT_ID=
RUNPOD_API_KEY=
TTS_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
```
```

- [ ] **Step 2: Update the Key implementation notes about tts_service.py**

Replace the last bullet in the "Key implementation notes" section:

Old:
```
- `tts_service.py`: voices are stored in a `VOICE_POOLS` dict keyed by language name (e.g. `"English"`, `"Spanish"`); `generate_all_audio(phrases, language="English")` selects randomly from the language-specific pool; unknown languages fall back to the English pool
```

New:
```
- `tts_service.py`: voices are stored in a `VOICE_POOLS` dict keyed by language name (e.g. `"English"`, `"Chinese"`); `generate_all_audio(phrases, language="English")` selects randomly from the language-specific pool; unknown languages fall back to English pool and `"en"` lang code. A `LANGUAGE_CODES` dict maps language name → RunPod `lang` param (e.g. `"Portuguese (Brazil)"` → `"pt-br"`).
```

- [ ] **Step 3: Add Kokoro TTS Service section to CLAUDE.md**

Append to `CLAUDE.md`:

```markdown
## Kokoro TTS Service

Audio is generated via a RunPod serverless endpoint running the Kokoro-82M model.

**Required env vars:**
```
RUNPOD_ENDPOINT_ID=2r9htace1yaroi
RUNPOD_API_KEY=<your RunPod key>
TTS_API_KEY=<shared secret — must match what the worker expects>
```

**Request format** (sent to `POST https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run`):
```json
{
  "input": {
    "text": "Hello world",
    "voice": "af_heart",
    "lang": "en",
    "speed": 1.0,
    "format": "mp3",
    "api_key": "<TTS_API_KEY>"
  }
}
```

**Response** (polled via `GET /status/{job_id}` until `status == "COMPLETED"`):
```json
{
  "output": {
    "audio_base64": "<base64-encoded MP3>",
    "format": "mp3",
    "voice": "af_heart"
  }
}
```

**Supported languages and voices:**

| Language | `lang` | Sample voices |
|---|---|---|
| English | `en` | af_heart, af_bella, am_adam, af_nova, am_michael |
| English (UK) | `en-gb` | bf_emma, bf_alice, bm_george, bm_daniel |
| Spanish | `es` | ef_dora, em_alex, em_santa |
| Portuguese (Brazil) | `pt-br` | pf_dora, pm_alex, pm_santa |
| French | `fr` | ff_siwis |
| Italian | `it` | if_sara, im_nicola |
| Japanese | `ja` | jf_alpha, jf_gongitsune, jm_kumo |
| Chinese | `zh` | zf_xiaobei, zf_xiaoni, zm_yunxi, zm_yunyang |

**Cold start:** The endpoint scales to zero. First call after idle may take 5–15s; subsequent calls are fast.
```

- [ ] **Step 4: Run full test suite one final time**

```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Kokoro TTS service documentation and new env vars"
```

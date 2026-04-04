# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This project has two parts:
- **Backend**: Python + FastAPI (`backend/`), deployed on Railway via Docker
- **Frontend**: Single HTML file (`frontend/index.html`), served as static file by FastAPI

## Running the backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

## Running the frontend

Open directly in browser (points to `http://localhost:8000` by default):
```
cmd /c start "" "<absolute-path-to-file>.html"
```
Or via PowerShell:
```
powershell -Command "Start-Process '<absolute-path-to-file>.html'"
```

## Testing and commit policy — MANDATORY

**After every code change:**
1. Run the full test suite and confirm all tests pass
2. Once all tests are green, immediately create a git commit

Run tests with:
```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

- All 103 tests must pass (unit + integration)
- Do NOT move on if any test is red — fix it first, then commit
- Once tests pass: `git add -A && git commit -m "<descriptive message>"`
- Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- Never commit broken code — each commit must be a verified working state
- Smoke tests (`tests/smoke/`) are excluded from the mandatory run (they require a live server + real API keys); run them manually when needed:
  ```bash
  python -m pytest tests/smoke -v -m smoke
  ```

## Test structure

```
backend/tests/
├── conftest.py              ← shared mock factories
├── unit/
│   ├── test_deduplicator.py
│   ├── test_audio_assembler.py
│   ├── test_phrase_generator.py
│   ├── test_moderator.py
│   └── test_tts_service.py
├── integration/
│   └── test_session_flow.py
└── smoke/
    └── test_smoke.py
```

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in:
```
OPENAI_API_KEY=
GOOGLE_TTS_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
```

## Bug reporting workflow

When the user reports a bug or UI error, before investigating the code Claude must:
1. Use the Playwright MCP to navigate to `http://localhost:8000`
2. Take a screenshot to capture the current visual state
3. Read the browser console for JavaScript errors
4. Only then investigate and fix the code

## Key implementation notes

- `moderator.py`: any `result.flagged=True` from OpenAI is treated as unsafe (regardless of specific category)
- `upload_session` is imported directly in `main.py` — always patch as `main.upload_session` in tests, not `services.storage_service.upload_session`
- pydub's `AudioSegment.from_mp3` and `AudioSegment.export` require ffmpeg (not available locally on Windows); both are mocked in tests
- ffmpeg is installed in the Docker image for Railway deployment
- `tts_service.py`: voices are stored in a `VOICE_POOLS` dict keyed by language name (e.g. `"English"`, `"Chinese"`); `generate_all_audio(phrases, language="English")` selects randomly from the language-specific pool; unknown languages fall back to English pool and `"en-US"` lang code. A `LANGUAGE_CODES` dict maps language name → BCP-47 code (e.g. `"Portuguese (Brazil)"` → `"pt-BR"`)

## Google Cloud TTS Service

Audio is generated via the Google Cloud Text-to-Speech REST API (Neural2/WaveNet voices).

**Required env var:**
```
GOOGLE_TTS_API_KEY=<your Google Cloud API key with TTS enabled>
```

**How it works:**
- Direct REST calls to `https://texttospeech.googleapis.com/v1/text:synthesize?key={API_KEY}`
- Uses `httpx.AsyncClient` with connection reuse (shared `_client` instance) for performance
- Normal speed: plain text input
- Slow speed (0.7×): SSML with `<prosody rate="75%">` wrapping
- Concurrency: `asyncio.Semaphore(4)` limits parallel calls
- Retry: tenacity with 3 attempts, exponential backoff

**Supported languages and voices (VOICE_POOLS):**

| Language | BCP-47 | Voice type |
|---|---|---|
| English | en-US | Neural2 |
| English (UK) | en-GB | Neural2 |
| Spanish | es-ES | Neural2 |
| Portuguese (Brazil) | pt-BR | Neural2 |
| French | fr-FR | Neural2 |
| Italian | it-IT | Neural2 |
| Japanese | ja-JP | Neural2 |
| Chinese | cmn-CN | WaveNet |
| German | de-DE | Neural2 |
| Korean | ko-KR | Neural2 |
| Hindi | hi-IN | Neural2 |
| Arabic | ar-XA | WaveNet |
| Russian | ru-RU | WaveNet |
| Dutch | nl-NL | Neural2 |
| Polish | pl-PL | WaveNet |
| Swedish | sv-SE | WaveNet |
| Turkish | tr-TR | WaveNet |
| Vietnamese | vi-VN | WaveNet |

**Performance:** ~2.5 minutes to generate a 5-minute session (42 phrases × normal + slow).

**Cost:** Neural2 = $16/1M chars, WaveNet = $4/1M chars. A 5-min session ≈ $0.13.

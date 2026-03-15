# PRD: Language Learning Audio App (Comprehensible Input)

## Overview

A web application that generates personalized audio sessions for language learners using the comprehensible input method with spaced repetition and shadowing. Users specify a target language, topic, and session duration; the app uses GPT to generate natural phrases and kokoro TTS to produce a structured audio file ready for listening practice.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (frontend)                 │
│              frontend/index.html (SPA)               │
│   View 1: Form → View 2: Confirm → View 3: Loading  │
│                    → View 4: Player                  │
└────────────────────────┬────────────────────────────┘
                         │ HTTP (REST)
                         ▼
┌─────────────────────────────────────────────────────┐
│               FastAPI Backend (Railway)              │
│                  backend/main.py                     │
│                                                      │
│  POST /interpret-topic                               │
│  POST /generate-session  ──► Background Task         │
│  GET  /session/{id}/status                           │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │phrase_gen   │  │ tts_service  │  │audio_asm   │  │
│  │(GPT-4o-mini)│  │(kokoro)      │  │(pydub)     │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │moderator    │  │deduplicator  │  │storage_svc │  │
│  │(OAI Modera- │  │(SequenceMat- │  │(Supabase)  │  │
│  │tion API)    │  │cher fuzzy)   │  │            │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│  ┌─────────────┐                                     │
│  │cleanup_svc  │ (APScheduler, every 30min)           │
│  └─────────────┘                                     │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Supabase Storage   │
              │  bucket: audio-sess. │
              │  sessions/{id}.mp3   │
              └──────────────────────┘
```

---

## Features

### Core Generation Features

**Feature 1 – Language selector**
Support for: English, Spanish, Portuguese (Brazil), French, German, Italian, Japanese, Russian.
Default language: **English**.

**Feature 2 – Duration → phrase count calculation**
Formula:
```python
base = max(1, round(duration_minutes * 60 / 9))
return round(base * 1.2)
```
The constant `9` reflects measured average phrase-block duration (~8.6 s); the 20% buffer ensures the assembler always has enough material to fill the target.
Example values: 5 min → 40, 10 min → 80, 15 min → 120, 20 min → 160, 30 min → 240.
Duration options: 5, 10, 15, 20, 30 minutes.

**Feature 3 – GPT phrase generation**
- Model: `gpt-4o-mini` (cost-efficient)
- System prompt instructs: natural spoken language, 6–12 words per phrase, topic-appropriate vocabulary
- Returns JSON array of phrases
- Tenacity retry with exponential backoff (up to 3 attempts)

**Feature 4 – Deduplication**
- Step 1: Exact deduplication (lowercase + strip)
- Step 2: Fuzzy deduplication using `difflib.SequenceMatcher` — ratio > 0.85 removes near-duplicates
- First occurrence is kept

**Feature 5 – Content moderation**
- Uses OpenAI Moderation API to filter phrases
- Flags: violence, sexual, hate, harassment
- If too many phrases removed (> 20%), triggers regeneration (up to 2 retries)

**New Feature – Top-up loop (phrase pool refill)**
After dedup + moderation, if the phrase pool is below `base_count` (`max(1, round(duration_minutes * 60 / 9))`), the pipeline loops up to 30 times:
- Requests `(needed × 2)` more phrases from GPT
- Deduplicates the combined pool (`deduplicate(existing + new)`)
- Moderates only the additions
- Appends safe additions and repeats
- Exits early when pool is full or no new unique phrases can be found (topic exhaustion)

**Feature 6 – kokoro TTS**
- Service: kokoro TTS, accessed via HTTP at `TTS_SERVICE_URL` (default `http://localhost:8880`)
- Model: `kokoro`
- API endpoint: `POST /v1/audio/speech` with `{ model, input, voice, speed, response_format: "mp3" }`
- Voice pools per language (voice selected randomly; unknown languages fall back to English pool):
  - English: `af_heart`, `af_bella`, `am_adam`
  - Spanish: `sf_lucia`, `sf_isabella`, `sm_javier`
  - Portuguese (Brazil): `pf_dora`, `pm_alex`, `pm_santa`
  - French: `ff_camille`, `ff_bernadette`, `fm_louis`
  - German: `df_marlene`, `df_lina`, `dm_hans`
  - Italian: `if_bianca`, `im_giorgio`
  - Japanese: `jf_haruka`, `jf_yuki`, `jm_takumi`
  - Russian: `rf_irina`, `rm_ilya`
- `generate_all_audio(phrases, language="English")` signature
- Tenacity retry on API failures (3 attempts, exponential backoff)

**Feature 7 – Slow audio version**
- Speed is `0.7×` — produced by calling kokoro with `speed=0.7`
- No pydub frame-rate manipulation; speed is handled server-side by kokoro
- Allows learners to hear clear pronunciation

**Feature 8 – Phrase block structure**
Each phrase plays as: `[normal] → 1s pause → [slow @0.7×] → 1s pause → [normal] → 1.5s pause`
This structure enables: hear → analyze → shadow along

**Feature 9 – Audio session assembly**
All phrase blocks concatenated into a single MP3 file using pydub. Final export at 128kbps MP3.
`assemble_session(audio_pairs, target_ms=None)` — when `target_ms` is set, accumulation stops after combined length ≥ target_ms (last complete block included; no mid-phrase cuts). `main.py` passes `target_ms = duration_minutes * 60 * 1000`.

**Feature 10 – Supabase Storage upload**
Audio file uploaded to Supabase Storage bucket. Signed URL returned for streaming and download.

**Feature 11 – UUID session ID**
Each session gets a UUID v4 as its ID. Used as filename: `sessions/{session_id}.mp3`.

**Feature 12 – Signed URL generation**
URL valid for `SESSION_TTL_HOURS` (default: 3 hours). Both streaming and download URLs provided.

**Feature 13 – Background cleanup**
APScheduler job runs every 30 minutes. Deletes Supabase Storage files older than TTL. Also purges in-memory session records.

### Frontend Features

**Feature 14 – Form view**
- Language dropdown (default: **English**)
- Topic free-text input
- Duration buttons displaying `~5 min`, `~10 min`, etc. (tilde prefix)
- "Generate" button → calls `/interpret-topic` → transitions to Confirm view

**Feature 15 – Topic interpretation / Confirm view**
- Calls `POST /interpret-topic` before starting generation
- Shows AI-generated 1–2 sentence description of what phrases will be generated
- Duration shown as `~X min` (e.g. `English · "have on" · ~5 min`)
- User can confirm or go back

**Feature 16 – Loading view with progress**
- Animated progress bar
- Polls `GET /session/{id}/status` every 2 seconds
- Displays progress percentage and step label:
  - 10%: "Generating phrases..."
  - 25%: "Moderating content..."
  - 40%: "Generating audio..."
  - 75%: "Assembling audio..."
  - 90%: "Uploading..."
  - 100%: "Done!"

**Feature 17 – Custom audio player**
- HTML5 `<audio>` element with custom controls
- Play/pause button, seek bar, current time / total time display

**Feature 18 – Background playback support**
- Uses HTML5 `<audio>` element (not Web Audio API) so device media controls work
- Users can lock screen and keep listening

**Feature 19 – Download button**
- `<a download href="...">` anchor pointing to signed download URL
- Filename: `session-{id}.mp3`

**Feature 20 – Voice diversity**
Language-specific voice pools (see Feature 6) randomly assigned per phrase. Keeps listening engaging.

**Feature 21 – Multilingual TTS**
kokoro model handles all 8 supported languages via language-specific voice pools.

**Feature 22 – Parallel TTS generation**
All phrases generated concurrently via `asyncio.gather`. Reduces total generation time significantly.

**Feature 23 – Async background task**
Session generation runs as a FastAPI `BackgroundTask`. Main thread is never blocked.

**Feature 24 – Timeout protection**
120-second hard timeout per session via `asyncio.timeout`. Returns structured error if exceeded.

**Feature 25 – Progress tracking**
In-memory session store (dict + asyncio.Lock) tracks: status string, progress int, audio_url, error. Polled by frontend.

---

## API Contract

### `POST /interpret-topic`
**Request:**
```json
{
  "language": "Spanish",
  "topic": "ordering food at a restaurant"
}
```
**Response:**
```json
{
  "interpretation": "I'll generate 18 simple Spanish phrases about ordering food..."
}
```

### `POST /generate-session`
**Request:**
```json
{
  "language": "Spanish",
  "topic": "ordering food at a restaurant",
  "duration_minutes": 5
}
```
**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### `GET /session/{session_id}/status`
**Response (in progress):**
```json
{
  "status": "generating_audio",
  "progress": 40,
  "audio_url": null,
  "error": null
}
```
**Response (done):**
```json
{
  "status": "done",
  "progress": 100,
  "audio_url": "https://supabase.../sessions/550e....mp3?token=...",
  "error": null
}
```
**Response (error):**
```json
{
  "status": "error",
  "progress": 0,
  "audio_url": null,
  "error": "Generation timed out"
}
```

---

## Audio Format Spec

- Format: MP3
- Bitrate: 128 kbps
- Sample rate: 44100 Hz (inherits from kokoro output)
- Phrase block structure: `normal (Xs) + 1s silence + slow_0.7x + 1s silence + normal (Xs) + 1.5s silence`
- Estimated block duration: ~8.6 seconds average per block

---

## Voice Pool

`VOICE_POOLS` dict keyed by language name:

| Language | Voices |
|---|---|
| English | `af_heart`, `af_bella`, `am_adam` |
| Spanish | `sf_lucia`, `sf_isabella`, `sm_javier` |
| Portuguese (Brazil) | `pf_dora`, `pm_alex`, `pm_santa` |
| French | `ff_camille`, `ff_bernadette`, `fm_louis` |
| German | `df_marlene`, `df_lina`, `dm_hans` |
| Italian | `if_bianca`, `im_giorgio` |
| Japanese | `jf_haruka`, `jf_yuki`, `jm_takumi` |
| Russian | `rf_irina`, `rm_ilya` |

Unknown languages fall back to the English pool.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | GPT phrase generation + moderation |
| `TTS_SERVICE_URL` | No | `http://localhost:8880` | URL of kokoro TTS service |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_KEY` | Yes | — | Supabase service role key |
| `SUPABASE_BUCKET` | No | `audio-sessions` | Storage bucket name |
| `SESSION_TTL_HOURS` | No | `3` | Hours before audio files expire |
| `MAX_GENERATION_TIMEOUT_SECONDS` | No | `120` | Hard timeout per session |
| `FRONTEND_ORIGIN` | No | `*` | CORS allowed origin |

---

## Deployment Instructions

### Local Development
```bash
cd backend
cp .env.example .env
# Fill in .env with your API keys
pip install -r requirements.txt
uvicorn main:app --reload
# Open frontend/index.html in browser
# Set API_URL in index.html to http://localhost:8000
```

### Railway Deployment
1. Push repo to GitHub
2. Create new Railway project → connect GitHub repo
3. Railway detects `backend/Dockerfile` via `railway.toml`
4. Set environment variables in Railway dashboard
5. Deploy — Railway provides a public URL
6. Update `API_URL` in `frontend/index.html` to Railway URL
7. Frontend can be served by FastAPI static mount or deployed separately

### Supabase Setup
1. Create a Supabase project
2. Create a Storage bucket named `audio-sessions`
3. Set bucket to private (signed URLs used for access)
4. Copy project URL and service role key to `.env`

### kokoro TTS Setup
- `TTS_SERVICE_URL` must point to a running kokoro instance (e.g. `http://localhost:8880` for local dev)
- kokoro is not bundled with this repo; run it separately before starting the backend

---

## Testing Strategy

### Policy
**The full test suite must pass after every code change before the task is considered done.**

Run command:
```bash
cd backend
python -m pytest tests/unit tests/integration -v
```

Expected: **68 tests passing**, 0 failures.

---

### Layer 1 — Unit Tests (`tests/unit/`)

No network, no credentials. All external dependencies mocked.

| File | What it tests | Mocks |
|---|---|---|
| `test_deduplicator.py` | Exact dedup, fuzzy dedup (SequenceMatcher), edge cases | None (pure Python) |
| `test_audio_assembler.py` | Phrase block timing/structure, session assembly, MP3 export | `AudioSegment.from_mp3`, `AudioSegment.export` |
| `test_phrase_generator.py` | `calc_num_phrases` formula, GPT response parsing, model selection | OpenAI `client.chat.completions.create` |
| `test_moderator.py` | Safe/flagged filtering, order preservation, regeneration trigger | OpenAI `client.moderations.create` |
| `test_tts_service.py` | Voice pool integrity per language, audio bytes return, URL construction, parallel gather, language fallback | `httpx.AsyncClient.post` |

**Key implementation facts confirmed by unit tests:**
- `calc_num_phrases(5) == 40`, `(10) == 80`, `(15) == 120`, `(20) == 160`, `(30) == 240`
- Any `result.flagged=True` from OpenAI Moderation → phrase rejected (regardless of specific category)
- Phrase block timing: `[normal] → 1s → [slow @0.7×] → 1s → [normal] → 1.5s`
- `VOICE_POOLS` contains entries for all 8 supported languages; each pool is non-empty with no duplicate voices
- `target_ms` parameter in `assemble_session` stops accumulation once combined length ≥ target
- Per-language voice pool selection in TTS service; unknown language falls back to English
- Top-up loop covered by integration test (session flow with pool below `base_count`)

---

### Layer 2 — Integration Tests (`tests/integration/test_session_flow.py`)

Tests the full HTTP request/response cycle using `httpx.AsyncClient` + `ASGITransport` (no real server needed). All external APIs mocked at the service boundary.

| Test | What it validates |
|---|---|
| `test_interpret_topic_returns_interpretation` | `POST /interpret-topic` → 200, `interpretation` field present |
| `test_invalid_duration_returns_400` | `duration_minutes=7` → 400 with descriptive error |
| `test_unknown_session_id_returns_404` | `GET /session/unknown/status` → 404 |
| `test_full_generate_session_happy_path` | Full pipeline: POST → background task → status `done` with `audio_url` |
| `test_generate_session_queued_status_immediately` | Session exists in store synchronously before background task completes |
| `test_valid_durations_accepted` | All 5 valid durations (5/10/15/20/30 min) → 200 |

**Mocking strategy:**
- `services.phrase_generator.client.chat.completions.create` → fake phrases response
- `services.moderator.client.moderations.create` → all-safe response
- `services.tts_service.generate_audio_for_phrase` → `b"FAKE_AUDIO_BYTES"`
- `services.audio_assembler.AudioSegment.from_mp3` → `AudioSegment.silent(500)`
- `services.audio_assembler.AudioSegment.export` → no-op
- `main.upload_session` → fake signed URL (**must patch in `main` namespace**, not service module)

---

### Layer 3 — Smoke Tests (`tests/smoke/test_smoke.py`)

Run against a live server. Require real API keys for full pipeline test.

```bash
# Start server first
cd backend && python -m uvicorn main:app --reload

# Run smoke tests
python -m pytest tests/smoke -v -m smoke
```

| Test | Requires |
|---|---|
| Root serves HTML with "LinguaFlow" | Running server |
| `/interpret-topic` returns non-empty interpretation | `OPENAI_API_KEY` |
| `/generate-session` returns valid UUID | Running server |
| Invalid duration returns 400 | Running server |
| Unknown session ID returns 404 | Running server |
| Session status schema valid | Running server |
| Full poll-until-done pipeline | All API keys |

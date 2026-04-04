# Google TTS Migration & Monthly Minute Cap — Design Spec

**Date:** 2026-04-02
**Status:** Approved
**Goal:** Replace RunPod/Kokoro serverless TTS with Google Cloud TTS to reduce per-session cost ~6-7x, add monthly minute caps per plan, and implement a paywall upgrade flow — making the product economically viable at a $5–9/month subscription price point.

---

## Problem

RunPod serverless costs ~$0.30–0.40 per 5-minute session due to cold starts and per-compute-second billing. A heavy user generating 4 hours/month (~48 sessions) costs ~$16.80 in TTS alone — more than the entire subscription revenue at $5–9/month pricing.

---

## Solution Overview

1. Replace `tts_service.py` RunPod calls with **Google Cloud TTS** (Neural2/WaveNet)
2. Add **`minutes_per_month`** limit to each plan in `plans.py`
3. Update `limit_checker.py` to enforce monthly minute budget (sum of `duration_minutes` from DB)
4. Update Pro plan price to **$9/month** and wire real Stripe price ID
5. Add **paywall** touchpoints in the frontend at 3 key moments

**Files changed:** `tts_service.py`, `plans.py`, `limit_checker.py`, `config.py`, `.env.example`, `frontend/index.html` (and dashboard pages).
**Files unchanged:** `main.py`, `audio_assembler.py`, `moderator.py`, `deduplicator.py`, all routers.

---

## Cost Analysis

| Plan | Minutes/month | Max TTS cost/user | Subscription price | Margin |
|---|---|---|---|---|
| Guest | 5 | ~$0.003 | $0 | — |
| Free | 30 | ~$0.032 | $0 | — |
| Pro | 120 | ~$0.13 | $9 | ~98.5% gross |

Even if 10% of Pro users hit the full 120-min cap every month, average TTS cost per Pro user is ~$0.013 — negligible.

---

## Section 1 — TTS Service (`tts_service.py`)

### Provider

**Google Cloud TTS** via the `google-cloud-texttospeech` Python package (sync or async client).
Auth: API key via `GOOGLE_TTS_API_KEY` env var (or service account JSON path `GOOGLE_APPLICATION_CREDENTIALS`).

### Slow audio

Replace `speed=0.7` RunPod param with SSML `<prosody rate="75%">`:

```xml
<speak><prosody rate="75%">Hello, how are you?</prosody></speak>
```

Normal speed uses plain text input (no SSML needed).

### Voice pools

```python
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
```

`LANGUAGE_CODES` maps language name → BCP-47 code used as `language_code` in the Google request (e.g. `"Chinese" → "cmn-CN"`, `"Arabic" → "ar-XA"`).

### API call shape

Each phrase generates **2 API calls** (normal + slow), same as before. Google responds synchronously (~300ms) — no polling loop.

```python
from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

def synthesize(text: str, voice_name: str, lang_code: str, slow: bool) -> bytes:
    if slow:
        input_ = texttospeech.SynthesisInput(
            ssml=f'<speak><prosody rate="75%">{text}</prosody></speak>'
        )
    else:
        input_ = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=lang_code,
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=input_, voice=voice, audio_config=audio_config
    )
    return response.audio_content
```

The async wrapper (`generate_audio_for_phrase`) runs this in a thread pool via `asyncio.to_thread`. The semaphore(4) concurrency and `generate_audio_streaming` / `generate_all_audio` interfaces remain **unchanged** — `main.py` does not change.

### Retry

Keep `tenacity` retry decorator (3 attempts, exponential backoff). Retryable: HTTP 429, 5xx from Google.

---

## Section 2 — Plan Limits (`plans.py`)

Add `minutes_per_month` to `PlanLimits` TypedDict and each plan:

```python
"guest": { ..., "limits": { ..., "minutes_per_month": 5   } }
"free":  { ..., "limits": { ..., "minutes_per_month": 30  } }
"pro":   { ..., "limits": { ..., "minutes_per_month": 120 }, "price": 9.0, "stripe_price_id": "<real_id>" }
```

`sessions_per_month` on the free plan is set to `0` (unlimited) — enforcement switches to `minutes_per_month`. The field stays in the TypedDict to avoid breaking existing references.

---

## Section 3 — Limit Checker (`limit_checker.py`)

Replace the session-count check for free plan with a **minutes-used-this-month** check that applies to all authenticated plans:

```python
# Replace free plan sessions_per_month block with:
if plan_key in ("free", "pro"):
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
                    detail=f"Free plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                           f"{remaining} min remaining. Upgrade to Pro for 120 min/month.",
                )
            else:
                raise HTTPException(
                    status_code=429,
                    detail=f"Pro plan limit reached: {minutes_used}/{minutes_limit} min used this month. "
                           f"{remaining} min remaining.",
                )
```

Guest plan keeps its existing 1-session/day + 5-min-max logic (unchanged).

---

## Section 4 — Config & Environment

`config.py` — add:
```python
GOOGLE_TTS_API_KEY: str = ""          # OR use GOOGLE_APPLICATION_CREDENTIALS
```

`.env.example` — add:
```
GOOGLE_TTS_API_KEY=your_api_key_here
# Alternative: use a service account JSON
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Remove from `.env.example` (no longer needed):
```
RUNPOD_ENDPOINT_ID=
RUNPOD_API_KEY=
TTS_API_KEY=
```

`requirements.txt` — add `google-cloud-texttospeech`, remove `httpx` only if not used elsewhere (keep it — used in other places potentially).

---

## Section 5 — Paywall (Frontend)

All text in English.

### 5a — Session generation block (3 trigger points)

**1. Duration selector — pre-submission guard**
Before the user submits, the frontend checks remaining minutes (fetched from `GET /api/user/me` which includes `minutes_used_this_month` and `plan`). If the selected duration would exceed the remaining budget, the Generate button is disabled with an inline message:

> "You've used X of 120 min this month. Select a shorter duration or upgrade your plan."

**2. Generate button — 429 handler**
If the API returns HTTP 429 on `POST /generate-session`, show an upgrade modal instead of an error toast:

> **Monthly limit reached**
> You've used all 120 minutes included in your Pro plan this month.
> [Upgrade plan] [Dismiss]

For Free users:
> **Monthly limit reached**
> You've used all 30 minutes included in your Free plan.
> Upgrade to Pro for 120 min/month.
> [Upgrade to Pro — $9/month] [Dismiss]

**3. Dashboard usage bar**
A progress bar on the dashboard showing `X / 120 min used this month`. When usage exceeds 80%, show a soft CTA:

> "You've used 96 of 120 min. [Upgrade for more]"

### 5b — Upgrade flow

- CTA buttons call `POST /api/billing/checkout/pro` → returns Stripe Checkout URL → redirect
- On return from Stripe (`?success=1`), refresh user plan and update UI
- Stripe webhook (`checkout.session.completed`) sets `user.plan = "pro"` — already implemented in `core/billing.py`

### 5c — Minutes used endpoint

`GET /api/user/me` response extended to include:
```json
{
  "plan": "free",
  "minutes_used_this_month": 18,
  "minutes_limit": 30
}
```

This is computed on-the-fly from `TtsSession` records (same query as limit_checker). No new DB column needed.

---

## Section 6 — Tests

Existing unit and integration tests must all pass after the migration.

**New/updated tests:**

- `test_tts_service.py` — mock `google.cloud.texttospeech.TextToSpeechClient`; assert SSML wrapping for slow audio; assert plain text for normal audio
- `test_limit_checker.py` — add cases for `minutes_per_month` enforcement: under limit, at limit, over limit for free and pro plans
- `test_session_flow.py` — update fixture mocks to use Google TTS mock instead of RunPod mock

**Smoke tests** — manually run after deployment with real Google credentials to verify voice quality on all new languages.

---

## Out of Scope

- Audio caching (can be added later as a cost optimization if volume grows)
- Multiple Pro tiers (e.g., Pro 240 min)
- Usage analytics dashboard for admin

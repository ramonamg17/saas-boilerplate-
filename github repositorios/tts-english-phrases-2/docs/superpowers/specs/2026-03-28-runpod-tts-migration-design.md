# Design: Migrate to RunPod Kokoro TTS Endpoint

**Date:** 2026-03-28
**Status:** Approved

## Context

The app generates TTS audio via a RunPod serverless endpoint. An earlier attempt to host the RunPod worker from within this repo (`runpod_serverless/`) was abandoned; the working endpoint (ID `2r9htace1yaroi`) now lives in the separate `tts` project. This spec covers:

1. Deleting the dead `runpod_serverless/` directory
2. Updating `tts_service.py` to match the new endpoint's API contract
3. Correcting VOICE_POOLS (wrong voice names, unsupported languages)
4. Adding `TTS_API_KEY` to config and env
5. Updating tests and CLAUDE.md

---

## 1. Cleanup

Delete the entire `runpod_serverless/` directory (contains `handler.py` and `Dockerfile` for the abandoned in-repo worker).

---

## 2. Configuration

### `backend/config.py`
Add one field:
```python
TTS_API_KEY: str = ""
```

### `backend/.env.example`
- Remove `TTS_SERVICE_URL` (was the old localhost:8880)
- Add:
```
RUNPOD_ENDPOINT_ID=2r9htace1yaroi
RUNPOD_API_KEY=<your RunPod API key>
TTS_API_KEY=<shared secret — must match TTS_API_KEY in the worker>
```

---

## 3. `tts_service.py` changes

### VOICE_POOLS (replace entirely)
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
```

German and Russian removed (not supported by new endpoint). English (UK) and Chinese added.

### LANGUAGE_CODES (new dict)
```python
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

### `generate_audio_for_phrase` — new signature + payload
```python
async def generate_audio_for_phrase(phrase, voice_id, speed=1.0, lang="en") -> bytes:
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
    # POST /run → get job_id
    # Poll /status/{job_id} every 5s, up to 60 attempts (5 min max)
    # Raise RuntimeError on FAILED; raise TimeoutError if 5 min exceeded
```

Key changes from old implementation:
- Endpoint: `/run` (async) instead of `/runsync`
- Field: `text` instead of `input`
- New fields: `lang`, `format`, `api_key`
- Removed field: `model`
- Polling: always polls `/status/{job_id}` (no fast-path runsync)

### `generate_all_audio` and `generate_audio_streaming`
Both resolve `lang` via `LANGUAGE_CODES.get(language, "en")` and pass it to `generate_audio_for_phrase`.

---

## 4. Tests (`test_tts_service.py`)

| Test | Change |
|---|---|
| `test_voice_pools_covers_all_supported_languages` | New set: English, English (UK), Spanish, Portuguese (Brazil), French, Italian, Japanese, Chinese |
| `test_generate_audio_sends_phrase_text` | Check `json["input"]["text"]` (was `input["input"]`) |
| `test_generate_audio_calls_runsync_endpoint` | Check URL ends with `/run` (was `/runsync`) |
| `test_generate_audio_sends_correct_model` | **Delete** (no `model` field in new API) |
| `test_generate_audio_sends_lang_param` | **Add** — verify `json["input"]["lang"]` is passed |
| `test_generate_audio_sends_api_key` | **Add** — verify `json["input"]["api_key"]` is set |

Mock shape (`make_runpod_response`) stays the same — new endpoint returns same COMPLETED/audio_base64 structure.

---

## 5. CLAUDE.md

Add a "Kokoro TTS Service" section documenting:
- Required env vars (`RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, `TTS_API_KEY`)
- Request format and response shape
- Available languages and voices table
- Cold start note (~5–15s, subsequent calls fast)

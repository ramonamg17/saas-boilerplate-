import asyncio
import base64
import logging
import random
from typing import AsyncGenerator

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

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

RUNPOD_ENDPOINT_ID = settings.RUNPOD_ENDPOINT_ID
SLOW_SPEED = 0.7


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return True


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


async def generate_audio_streaming(
    phrases: list[str],
    language: str = "English",
) -> AsyncGenerator[tuple[int, int, tuple[bytes, bytes]], None]:
    """Yields (index, total, (normal_bytes, slow_bytes)) as each phrase completes.

    Completion order may differ from input order (as_completed semantics).
    Keeps the same semaphore(4) concurrency as generate_all_audio.
    Existing generate_all_audio is unchanged.
    """
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    total = len(phrases)
    sem = asyncio.Semaphore(4)

    async def _bounded(i: int, phrase: str) -> tuple[int, tuple[bytes, bytes]]:
        voice = random.choice(voice_pool)
        async with sem:
            normal = await generate_audio_for_phrase(phrase, voice, speed=1.0)
            slow = await generate_audio_for_phrase(phrase, voice, speed=SLOW_SPEED)
        return i, (normal, slow)

    tasks = [asyncio.create_task(_bounded(i, p)) for i, p in enumerate(phrases)]
    for fut in asyncio.as_completed(tasks):
        i, chunk = await fut
        yield i, total, chunk


async def generate_all_audio(phrases: list[str], language: str = "English") -> list[tuple[bytes, bytes]]:
    """Generate normal and slow audio for each phrase using the same voice.

    Returns a list of (normal_bytes, slow_bytes) tuples, one per phrase.
    """
    voice_pool = VOICE_POOLS.get(language, VOICE_POOLS["English"])
    sem = asyncio.Semaphore(4)

    async def _bounded(phrase: str) -> tuple[bytes, bytes]:
        voice = random.choice(voice_pool)
        async with sem:
            normal = await generate_audio_for_phrase(phrase, voice, speed=1.0)
        async with sem:
            slow = await generate_audio_for_phrase(phrase, voice, speed=SLOW_SPEED)
        return normal, slow

    return await asyncio.gather(*[_bounded(p) for p in phrases])

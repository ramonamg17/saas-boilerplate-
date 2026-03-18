import asyncio
import logging
import os
import random
from typing import AsyncGenerator

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

VOICE_POOLS = {
    "English":             ["af_heart", "af_bella", "am_adam"],
    "Spanish":             ["sf_lucia", "sf_isabella", "sm_javier"],
    "Portuguese (Brazil)": ["pf_dora", "pm_alex", "pm_santa"],
    "French":              ["ff_camille", "ff_bernadette", "fm_louis"],
    "German":              ["df_marlene", "df_lina", "dm_hans"],
    "Italian":             ["if_bianca", "im_giorgio"],
    "Japanese":            ["jf_haruka", "jf_yuki", "jm_takumi"],
    "Russian":             ["rf_irina", "rm_ilya"],
}

TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8880")
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
async def generate_audio_for_phrase(phrase: str, voice_id: str, speed: float = 1.0) -> bytes:
    url = f"{TTS_SERVICE_URL}/v1/audio/speech"

    payload = {
        "model": "kokoro",
        "input": phrase,
        "voice": voice_id,
        "speed": speed,
        "response_format": "mp3",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error("TTS service error: status=%s body=%s", response.status_code, response.text[:300])
        response.raise_for_status()
        return response.content


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
        async with sem:
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

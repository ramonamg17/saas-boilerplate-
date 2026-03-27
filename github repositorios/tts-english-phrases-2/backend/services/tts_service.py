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
    "English":             ["af_heart", "af_bella", "am_adam"],
    "Spanish":             ["sf_lucia", "sf_isabella", "sm_javier"],
    "Portuguese (Brazil)": ["pf_dora", "pm_alex", "pm_santa"],
    "French":              ["ff_camille", "ff_bernadette", "fm_louis"],
    "German":              ["df_marlene", "df_lina", "dm_hans"],
    "Italian":             ["if_bianca", "im_giorgio"],
    "Japanese":            ["jf_haruka", "jf_yuki", "jm_takumi"],
    "Russian":             ["rf_irina", "rm_ilya"],
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
async def generate_audio_for_phrase(phrase: str, voice_id: str, speed: float = 1.0) -> bytes:
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/runsync"

    payload = {
        "input": {
            "model": "kokoro",
            "input": phrase,
            "voice": voice_id,
            "speed": speed,
        }
    }

    url_status = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status"
    headers = {"Authorization": f"Bearer {settings.RUNPOD_API_KEY}"}

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error("RunPod TTS error: status=%s body=%s", response.status_code, response.text[:300])
        response.raise_for_status()
        data = response.json()

        # Fast path: runsync returned the completed result directly
        if data.get("status") == "COMPLETED":
            return base64.b64decode(data["output"]["audio_base64"])

        # Slow path: job is still running (cold start > ~90s) — poll until done
        if data.get("status") == "IN_PROGRESS":
            job_id = data["id"]
            for _ in range(60):  # up to 5 min (60 × 5s)
                await asyncio.sleep(5)
                r = await client.get(f"{url_status}/{job_id}", headers=headers)
                r.raise_for_status()
                s = r.json()
                if s.get("status") == "COMPLETED":
                    return base64.b64decode(s["output"]["audio_base64"])
                if s.get("status") == "FAILED":
                    raise RuntimeError(f"RunPod job failed: {s.get('error', '')[:200]}")
            raise RuntimeError(f"RunPod job did not complete within 5 minutes: {job_id}")

        raise RuntimeError(f"Unexpected RunPod response: {data}")


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

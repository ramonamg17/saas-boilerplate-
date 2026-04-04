import asyncio
import base64
import logging
import random
from typing import AsyncGenerator

import httpx
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
_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def _synthesize_sync(text: str, voice_name: str, lang_code: str, slow: bool) -> bytes:
    """Synchronous Google TTS REST call. Runs in a thread pool via asyncio.to_thread."""
    if slow:
        input_ = {"ssml": f'<speak><prosody rate="{SLOW_RATE}">{text}</prosody></speak>'}
    else:
        input_ = {"text": text}
    payload = {
        "input": input_,
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    resp = httpx.post(
        _TTS_URL,
        params={"key": settings.GOOGLE_TTS_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return base64.b64decode(resp.json()["audioContent"])


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

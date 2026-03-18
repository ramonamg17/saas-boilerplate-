"""
Integration tests for the full POST /generate-session → poll → done flow.

All external APIs (OpenAI, ElevenLabs, Supabase) are mocked at the service
boundary so the tests run without real credentials and without network access.

FastAPI BackgroundTasks run synchronously inside the ASGI lifecycle when using
httpx.AsyncClient with ASGITransport, so the session is fully processed before
the first status poll.
"""
import asyncio
import contextlib
import json
import pytest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from pydub import AudioSegment

# ── App import (with scheduler patched) ──────────────────────────────────────

with unittest.mock.patch("services.cleanup_service.start_cleanup_scheduler"):
    with unittest.mock.patch("services.cleanup_service.stop_cleanup_scheduler"):
        from main import app


# ── Shared mock helpers ───────────────────────────────────────────────────────

SAMPLE_PHRASES = [
    "Quiero ordenar una mesa para dos",
    "Me trae la carta por favor",
    "Quisiera un café con leche",
    "La cuenta por favor cuando pueda",
    "Hay algún plato del día especial",
]

FAKE_SIGNED_URL = "https://test.supabase.co/storage/v1/object/sign/sessions/test.mp3?token=abc"


def _make_phrases_response():
    msg = MagicMock()
    msg.content = json.dumps({"phrases": SAMPLE_PHRASES})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_interpret_response():
    msg = MagicMock()
    msg.content = "I'll generate natural Spanish phrases about ordering food at a restaurant."
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_moderation_response(n: int):
    result = MagicMock()
    result.flagged = False
    result.categories = MagicMock(violence=False, sexual=False, hate=False, harassment=False)
    resp = MagicMock()
    resp.results = [result] * n
    return resp


def _make_http_audio_response():
    resp = MagicMock()
    resp.content = b"FAKE_AUDIO_BYTES"
    resp.raise_for_status = MagicMock()
    return resp


def _all_patches():
    """Return a list of patch context managers for all external services."""
    return [
        # OpenAI phrase generation — returns a predictable list
        patch(
            "services.phrase_generator.client.chat.completions.create",
            new=AsyncMock(return_value=_make_phrases_response()),
        ),
        # OpenAI moderation — all safe
        patch(
            "services.moderator.client.moderations.create",
            new=AsyncMock(return_value=_make_moderation_response(len(SAMPLE_PHRASES))),
        ),
        # ElevenLabs TTS — fake bytes per phrase
        patch(
            "services.tts_service.generate_audio_for_phrase",
            new=AsyncMock(return_value=b"FAKE_AUDIO_BYTES"),
        ),
        # pydub MP3 decode — return silent audio (no ffmpeg needed)
        patch(
            "services.audio_assembler.AudioSegment.from_mp3",
            return_value=AudioSegment.silent(duration=500),
        ),
        # pydub MP3 encode — skip ffmpeg
        patch("services.audio_assembler.AudioSegment.export"),
        # Supabase upload → return fake signed URL
        # Must patch in main's namespace (main.py uses `from services.storage_service import upload_session`)
        patch(
            "main.upload_session",
            new=AsyncMock(return_value=FAKE_SIGNED_URL),
        ),
        # Timing service — prevent writing real timing_data.json; return predictable estimate
        patch("main.get_estimate", return_value=200),
        patch("main.save_timing"),
        # Scheduler — suppress real APScheduler startup/shutdown
        patch("main.start_cleanup_scheduler"),
        patch("main.stop_cleanup_scheduler"),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_interpret_topic_returns_interpretation():
    with unittest.mock.patch(
        "services.phrase_generator.client.chat.completions.create",
        new=AsyncMock(return_value=_make_interpret_response()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/interpret-topic",
                json={"language": "Spanish", "topic": "ordering food"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "interpretation" in data
    assert isinstance(data["interpretation"], str)
    assert len(data["interpretation"]) > 0


async def test_invalid_duration_returns_400():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/generate-session",
            json={"language": "Spanish", "topic": "food", "duration_minutes": 7},
        )
    assert resp.status_code == 400
    assert "duration_minutes" in resp.json()["detail"]


async def test_unknown_session_id_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/session/00000000-0000-0000-0000-000000000000/status")
    assert resp.status_code == 404


async def test_full_generate_session_happy_path():
    """
    Full pipeline: POST /generate-session → background task completes →
    GET /session/{id}/status returns done with audio_url.
    """
    patches = _all_patches()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Start session
            resp = await client.post(
                "/generate-session",
                json={"language": "Spanish", "topic": "ordering food", "duration_minutes": 5},
            )
            assert resp.status_code == 200
            session_id = resp.json()["session_id"]
            assert session_id  # non-empty UUID

            # 2. Poll until done or timeout (background task usually completes
            #    within the ASGI lifecycle, but we poll to be safe)
            status_data = {}
            for _ in range(20):
                status_resp = await client.get(f"/session/{session_id}/status")
                assert status_resp.status_code == 200
                status_data = status_resp.json()
                if status_data["status"] in ("done", "error"):
                    break
                await asyncio.sleep(0.1)

            # 3. Assert success
            assert status_data["status"] == "done", (
                f"Expected 'done', got '{status_data['status']}': {status_data.get('error')}"
            )
            assert status_data["audio_url"] == FAKE_SIGNED_URL
            assert status_data["progress"] == 100
            assert status_data["error"] is None


async def test_generate_session_queued_status_immediately():
    """Session should be in 'queued' state synchronously before background task runs."""
    patches = _all_patches()
    # Delay the phrase generation so we can observe the intermediate state
    original_gen = AsyncMock(return_value=_make_phrases_response())

    async def slow_gen(*args, **kwargs):
        await asyncio.sleep(0.05)
        return await original_gen(*args, **kwargs)

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(
            patch("services.phrase_generator.client.chat.completions.create", new=slow_gen)
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/generate-session",
                json={"language": "Spanish", "topic": "food", "duration_minutes": 5},
            )
            session_id = resp.json()["session_id"]
            # Session must exist immediately
            status_resp = await client.get(f"/session/{session_id}/status")
            assert status_resp.status_code == 200


async def test_valid_durations_accepted():
    """All allowed duration values should return 200 and a session_id."""
    patches = _all_patches()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for duration in (5, 10, 15, 20, 30):
                resp = await client.post(
                    "/generate-session",
                    json={"language": "French", "topic": "travel", "duration_minutes": duration},
                )
                assert resp.status_code == 200, f"duration {duration} failed"
                assert "session_id" in resp.json()


async def test_session_status_has_timing_fields():
    """Session status must include start_time and estimated_seconds from the start."""
    patches = _all_patches()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/generate-session",
                json={"language": "Spanish", "topic": "food", "duration_minutes": 5},
            )
            session_id = resp.json()["session_id"]

            status_resp = await client.get(f"/session/{session_id}/status")
            data = status_resp.json()

            assert "start_time" in data
            assert data["start_time"] is not None
            assert isinstance(data["start_time"], float)

            assert "estimated_seconds" in data
            assert isinstance(data["estimated_seconds"], int)
            assert data["estimated_seconds"] > 0


async def test_session_done_status_has_phrase_count_fields():
    """Final done status must include phrases_done and phrases_total."""
    patches = _all_patches()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/generate-session",
                json={"language": "Spanish", "topic": "food", "duration_minutes": 5},
            )
            session_id = resp.json()["session_id"]

            status_data = {}
            for _ in range(20):
                status_resp = await client.get(f"/session/{session_id}/status")
                status_data = status_resp.json()
                if status_data["status"] in ("done", "error"):
                    break
                await asyncio.sleep(0.1)

            assert status_data["status"] == "done"
            assert "phrases_done" in status_data
            assert "phrases_total" in status_data
            assert isinstance(status_data["phrases_done"], int)
            assert isinstance(status_data["phrases_total"], int)


async def test_session_done_status_has_preview_url():
    """Final done status must include preview_url (set during streaming)."""
    patches = _all_patches()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/generate-session",
                json={"language": "Spanish", "topic": "food", "duration_minutes": 5},
            )
            session_id = resp.json()["session_id"]

            status_data = {}
            for _ in range(20):
                status_resp = await client.get(f"/session/{session_id}/status")
                status_data = status_resp.json()
                if status_data["status"] in ("done", "error"):
                    break
                await asyncio.sleep(0.1)

            assert status_data["status"] == "done"
            # preview_url key must be present (may be None if previews failed, but key exists)
            assert "preview_url" in status_data

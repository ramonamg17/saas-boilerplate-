"""
Smoke tests — run against a LIVE server (localhost:8000 by default).

Usage:
    # Start the server first:
    cd backend && python -m uvicorn main:app --reload

    # Then run smoke tests (excluded from normal pytest run):
    pytest tests/smoke/ -v -m smoke

These tests are intentionally NOT mocked. They require:
  - A running backend at BASE_URL
  - Valid API keys in backend/.env (OPENAI_API_KEY is sufficient for /interpret-topic)
"""
import asyncio
import os
import pytest
import httpx

BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")
pytestmark = pytest.mark.smoke


# ── Connectivity ──────────────────────────────────────────────────────────────

def test_root_serves_html():
    resp = httpx.get(f"{BASE_URL}/")
    assert resp.status_code == 200
    assert "LinguaFlow" in resp.text
    assert "text/html" in resp.headers["content-type"]


def test_unknown_route_returns_404():
    resp = httpx.get(f"{BASE_URL}/nonexistent-route")
    assert resp.status_code == 404


# ── /interpret-topic ──────────────────────────────────────────────────────────

def test_interpret_topic_live():
    resp = httpx.post(
        f"{BASE_URL}/interpret-topic",
        json={"language": "Spanish", "topic": "ordering food"},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "interpretation" in data
    assert len(data["interpretation"]) > 20


def test_interpret_topic_missing_fields_returns_error():
    resp = httpx.post(f"{BASE_URL}/interpret-topic", json={})
    assert resp.status_code == 422  # FastAPI validation error


# ── /generate-session ─────────────────────────────────────────────────────────

def test_generate_session_returns_session_id():
    resp = httpx.post(
        f"{BASE_URL}/generate-session",
        json={"language": "Spanish", "topic": "daily routines", "duration_minutes": 5},
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    # Validate UUID format (8-4-4-4-12)
    session_id = data["session_id"]
    parts = session_id.split("-")
    assert len(parts) == 5
    assert [len(p) for p in parts] == [8, 4, 4, 4, 12]


def test_generate_session_invalid_duration():
    resp = httpx.post(
        f"{BASE_URL}/generate-session",
        json={"language": "Spanish", "topic": "food", "duration_minutes": 7},
        timeout=10,
    )
    assert resp.status_code == 400


def test_generate_session_missing_fields():
    resp = httpx.post(f"{BASE_URL}/generate-session", json={"language": "Spanish"})
    assert resp.status_code == 422


# ── /session/{id}/status ──────────────────────────────────────────────────────

def test_session_status_unknown_id_returns_404():
    resp = httpx.get(f"{BASE_URL}/session/00000000-0000-0000-0000-000000000000/status")
    assert resp.status_code == 404


def test_session_status_schema_valid():
    # Start a session, then immediately check its status
    start = httpx.post(
        f"{BASE_URL}/generate-session",
        json={"language": "French", "topic": "travel", "duration_minutes": 5},
        timeout=10,
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    status = httpx.get(f"{BASE_URL}/session/{session_id}/status", timeout=10)
    assert status.status_code == 200
    data = status.json()

    assert "status" in data
    assert "progress" in data
    assert "audio_url" in data
    assert "error" in data
    assert data["status"] in ("queued", "generating_phrases", "moderating",
                               "generating_audio", "assembling", "uploading",
                               "done", "error")
    assert isinstance(data["progress"], int)
    assert 0 <= data["progress"] <= 100


def test_session_poll_until_terminal_state():
    """
    Starts a real 5-minute session and polls until it reaches 'done' or 'error'.
    Requires all API keys to be set. Skip if OPENAI_API_KEY not set.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping full pipeline smoke test")
    if not os.getenv("ELEVENLABS_API_KEY"):
        pytest.skip("ELEVENLABS_API_KEY not set — skipping full pipeline smoke test")

    start = httpx.post(
        f"{BASE_URL}/generate-session",
        json={"language": "Spanish", "topic": "greetings", "duration_minutes": 5},
        timeout=10,
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    # Poll up to 3 minutes
    for attempt in range(90):
        status = httpx.get(f"{BASE_URL}/session/{session_id}/status", timeout=10)
        data = status.json()
        if data["status"] == "done":
            assert data["audio_url"] is not None
            assert data["audio_url"].startswith("https://")
            return
        if data["status"] == "error":
            pytest.fail(f"Session failed: {data['error']}")
        import time
        time.sleep(2)

    pytest.fail("Session did not reach terminal state within 3 minutes")

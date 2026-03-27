"""
RunPod Serverless handler for Kokoro TTS.

Starts the Kokoro FastAPI server as a subprocess, waits for it to be ready,
then proxies /v1/audio/speech requests and returns base64-encoded MP3 audio.
"""

import base64
import os
import subprocess
import threading
import time

import requests
import runpod

_server_ready = False
_server_proc = None
_server_lock = threading.Lock()


def _start_server() -> None:
    global _server_ready, _server_proc

    env = {
        **os.environ,
        "USE_GPU": "true",
        "USE_ONNX": "false",
        # Single PYTHONPATH entry — avoids import conflicts with dual-path setup
        "PYTHONPATH": "/root/kokoro-fastapi",
        # Absolute MODEL_DIR: os.path.join(api_dir, absolute_path) == absolute_path in Python,
        # so this bypasses the api_dir prefix computed in paths.py.
        # Models were downloaded to /root/kokoro-fastapi/src/models/v1_0/ during Docker build.
        "MODEL_DIR": "/root/kokoro-fastapi/src/models",
        # VOICES_DIR: relative to api_dir (/root/kokoro-fastapi/api), so resolves to
        # /root/kokoro-fastapi/api/src/voices/v1_0 — exactly where git clone puts them.
        "VOICES_DIR": "src/voices/v1_0",
    }

    _server_proc = subprocess.Popen(
        ["python3.11", "-m", "uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8880"],
        cwd="/root/kokoro-fastapi",
        env=env,
    )

    # Wait up to 5 minutes for model load + warmup inference
    for _ in range(150):
        try:
            if requests.get("http://localhost:8880/health", timeout=3).status_code == 200:
                _server_ready = True
                return
        except Exception:
            pass
        time.sleep(2)

    raise RuntimeError("Kokoro server failed to become healthy within 5 minutes")


def _ensure_server() -> None:
    global _server_ready
    if _server_ready:
        return
    with _server_lock:
        if not _server_ready:
            _start_server()


def handler(job: dict) -> dict:
    _ensure_server()

    inp = job["input"]
    response = requests.post(
        "http://localhost:8880/v1/audio/speech",
        json={
            "model": inp.get("model", "kokoro"),
            "input": inp["input"],
            "voice": inp.get("voice", "af_heart"),
            "speed": inp.get("speed", 1.0),
            "response_format": "mp3",
        },
        timeout=120,
    )
    response.raise_for_status()
    return {"audio_base64": base64.b64encode(response.content).decode()}


# Pre-warm: start Kokoro server in background immediately on worker startup.
# This way the model is already loaded when the first job arrives.
threading.Thread(target=_ensure_server, daemon=True).start()

runpod.serverless.start({"handler": handler})

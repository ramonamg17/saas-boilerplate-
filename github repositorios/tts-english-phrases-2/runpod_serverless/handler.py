"""
RunPod Serverless handler for Kokoro TTS.

Starts the Kokoro FastAPI server as a subprocess, waits for it to be ready,
then proxies /v1/audio/speech requests and returns base64-encoded MP3 audio.
"""

import base64
import os
import subprocess
import time

import requests
import runpod

_server_ready = False
_server_proc = None


def _ensure_server() -> None:
    global _server_ready, _server_proc

    if _server_ready:
        return

    env = {
        **os.environ,
        "USE_GPU": "true",
        "USE_ONNX": "false",
        "PYTHONPATH": "/root/kokoro-fastapi:/root/kokoro-fastapi/api",
        "MODEL_DIR": "src/models",
        "VOICES_DIR": "src/voices/v1_0",
    }

    _server_proc = subprocess.Popen(
        ["python3.11", "-m", "uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8880"],
        cwd="/root/kokoro-fastapi",
        env=env,
    )

    # Wait up to 4 minutes for the model to load and server to be healthy
    for _ in range(120):
        try:
            if requests.get("http://localhost:8880/health", timeout=3).status_code == 200:
                _server_ready = True
                return
        except Exception:
            pass
        time.sleep(2)

    raise RuntimeError("Kokoro server failed to become healthy within 4 minutes")


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


runpod.serverless.start({"handler": handler})

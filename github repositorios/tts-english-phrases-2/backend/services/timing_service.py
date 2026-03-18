"""
Persists average TTS generation time per session duration.
Data file: backend/timing_data.json (git-ignored).
"""
import json
from pathlib import Path

DEFAULT_ESTIMATES = {5: 200, 10: 340, 15: 480, 20: 600, 30: 900}  # seconds

DATA_FILE = Path(__file__).parent.parent / "timing_data.json"


def _load() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data))


def get_estimate(duration_minutes: int) -> int:
    """Returns estimated seconds for this duration (uses stored average if available)."""
    data = _load()
    key = str(duration_minutes)
    if key in data:
        return int(data[key]["avg"])
    return DEFAULT_ESTIMATES.get(duration_minutes, 300)


def save_timing(duration_minutes: int, elapsed_seconds: float) -> None:
    """Updates rolling average. avg = (old_avg * n + new) / (n + 1)."""
    data = _load()
    key = str(duration_minutes)
    if key in data:
        n = data[key]["n"]
        old_avg = data[key]["avg"]
        new_avg = (old_avg * n + elapsed_seconds) / (n + 1)
        data[key] = {"avg": new_avg, "n": n + 1}
    else:
        data[key] = {"avg": elapsed_seconds, "n": 1}
    _save(data)

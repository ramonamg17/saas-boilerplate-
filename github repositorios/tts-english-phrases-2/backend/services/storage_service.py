import os
from supabase import create_client, Client

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(url, key)
    return _client


def _get_bucket() -> str:
    return os.getenv("SUPABASE_BUCKET", "audio-sessions")


def _get_ttl_seconds() -> int:
    hours = int(os.getenv("SESSION_TTL_HOURS", "3"))
    return hours * 3600


async def upload_session(session_id: str, audio_bytes: bytes) -> str:
    client = _get_client()
    bucket = _get_bucket()
    path = f"sessions/{session_id}.mp3"

    client.storage.from_(bucket).upload(
        path=path,
        file=audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )

    ttl = _get_ttl_seconds()
    signed = client.storage.from_(bucket).create_signed_url(path, ttl)
    return signed["signedURL"]


def list_session_files() -> list[dict]:
    client = _get_client()
    bucket = _get_bucket()
    try:
        files = client.storage.from_(bucket).list("sessions")
        return files or []
    except Exception:
        return []


def delete_session_file(session_id: str) -> None:
    client = _get_client()
    bucket = _get_bucket()
    path = f"sessions/{session_id}.mp3"
    client.storage.from_(bucket).remove([path])

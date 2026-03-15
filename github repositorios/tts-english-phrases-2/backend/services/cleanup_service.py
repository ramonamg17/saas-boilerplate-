import os
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.storage_service import list_session_files, delete_session_file

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _get_ttl_hours() -> int:
    return int(os.getenv("SESSION_TTL_HOURS", "3"))


def _parse_created_at(file_info: dict) -> datetime | None:
    created_at = file_info.get("created_at")
    if not created_at:
        return None
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def cleanup_expired_sessions(sessions: dict) -> None:
    logger.info("Running session cleanup job")
    ttl_hours = _get_ttl_hours()
    now = datetime.now(timezone.utc)

    try:
        files = list_session_files()
    except Exception as e:
        logger.error(f"Failed to list session files: {e}")
        return

    deleted = 0
    for file_info in files:
        created_at = _parse_created_at(file_info)
        if created_at is None:
            continue

        age_hours = (now - created_at).total_seconds() / 3600
        if age_hours >= ttl_hours:
            name = file_info.get("name", "")
            session_id = name.replace(".mp3", "")
            try:
                delete_session_file(session_id)
                sessions.pop(session_id, None)
                deleted += 1
            except Exception as e:
                logger.error(f"Failed to delete {session_id}: {e}")

    logger.info(f"Cleanup complete: deleted {deleted} expired sessions")


def start_cleanup_scheduler(sessions: dict) -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        cleanup_expired_sessions,
        "interval",
        minutes=30,
        args=[sessions],
        id="session_cleanup",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Cleanup scheduler started (every 30 minutes)")
    return _scheduler


def stop_cleanup_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None

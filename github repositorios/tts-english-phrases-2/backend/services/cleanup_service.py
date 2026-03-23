import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def cleanup_expired_sessions(sessions: dict) -> None:
    """Delete sessions (storage + DB) whose expires_at has passed."""
    logger.info("Running session cleanup job")
    now = datetime.now(timezone.utc)

    try:
        from database import AsyncSessionLocal
        from models.session_model import TtsSession
        from services.storage_service import delete_session_file
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TtsSession).where(TtsSession.expires_at < now)
            )
            expired = result.scalars().all()

            deleted = 0
            for s in expired:
                try:
                    delete_session_file(s.id)
                    sessions.pop(s.id, None)
                except Exception as e:
                    logger.error(f"Failed to delete storage file for {s.id}: {e}")

                await db.delete(s)
                deleted += 1

            await db.commit()
            logger.info(f"Cleanup complete: deleted {deleted} expired sessions")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


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

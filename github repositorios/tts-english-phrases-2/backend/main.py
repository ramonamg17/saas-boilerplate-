import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import RetryError

load_dotenv()

from config import settings
from database import AsyncSessionLocal, create_tables, get_db
from middleware.auth_guard import optional_user
from models.session_model import TtsSession
from models.user import User
from plans import get_plan
from services.audio_assembler import assemble_session
from services.cleanup_service import start_cleanup_scheduler, stop_cleanup_scheduler
from services.deduplicator import deduplicate
from services.limit_checker import check_generation_limits
from services.moderator import filter_phrases
from services.phrase_generator import calc_num_phrases, generate_phrases, interpret_topic
from services.storage_service import upload_session
from services.timing_service import get_estimate, save_timing
from services.tts_service import generate_audio_streaming
from routers import auth as auth_router
from routers import billing as billing_router
from routers import user as user_router
from routers import admin as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sessions: dict = {}
sessions_lock = asyncio.Lock()

MAX_TIMEOUT = settings.MAX_GENERATION_TIMEOUT_SECONDS
logger.info(f"MAX_TIMEOUT = {MAX_TIMEOUT}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    start_cleanup_scheduler(sessions)
    yield
    stop_cleanup_scheduler()


app = FastAPI(title="Language Learning Audio API", lifespan=lifespan)

frontend_origin = settings.FRONTEND_ORIGIN
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(billing_router.router, prefix="/api/billing", tags=["billing"])
app.include_router(user_router.router, prefix="/api/user", tags=["user"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["admin"])

# ── Static files / frontend ───────────────────────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def serve_frontend():
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Language Learning Audio API"}


# ── Request/response models ───────────────────────────────────────────

class InterpretTopicRequest(BaseModel):
    language: str
    topic: str
    refinement: str | None = None


class GenerateSessionRequest(BaseModel):
    language: str
    topic: str
    duration_minutes: int


# ── Session state helpers ─────────────────────────────────────────────

async def update_status(
    session_id: str,
    status: str,
    progress: int,
    audio_url: str | None = None,
    preview_url: str | None = None,
    phrases_done: int | None = None,
    phrases_total: int | None = None,
    error: str | None = None,
) -> None:
    async with sessions_lock:
        existing = sessions.get(session_id, {})
        sessions[session_id] = {
            "status": status,
            "progress": progress,
            "audio_url": audio_url,
            "preview_url": preview_url if preview_url is not None else existing.get("preview_url"),
            "phrases_done": phrases_done if phrases_done is not None else existing.get("phrases_done", 0),
            "phrases_total": phrases_total if phrases_total is not None else existing.get("phrases_total", 0),
            "error": error,
            "start_time": existing.get("start_time"),
            "estimated_seconds": existing.get("estimated_seconds"),
        }

    # Persist terminal states to DB (open a new short-lived session)
    if status in ("done", "error"):
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select as sa_select
                result = await db.execute(
                    sa_select(TtsSession).where(TtsSession.id == session_id)
                )
                db_session = result.scalar_one_or_none()
                if db_session:
                    db_session.status = status
                    db_session.progress = progress
                    db_session.audio_url = audio_url
                    db_session.error = error
                    if status == "done":
                        db_session.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to persist terminal state to DB: {e}")


# ── Background generation task ────────────────────────────────────────

async def run_session_generation(
    session_id: str,
    language: str,
    topic: str,
    duration_minutes: int,
) -> None:
    try:
        async with asyncio.timeout(MAX_TIMEOUT):
            num_phrases = calc_num_phrases(duration_minutes)
            logger.info(f"[{session_id}] Generating {num_phrases} phrases")
            await update_status(session_id, "generating_phrases", 10)

            phrases = await generate_phrases(language, topic, num_phrases)
            logger.info(f"[{session_id}] Got {len(phrases)} phrases from GPT")

            phrases = deduplicate(phrases)
            logger.info(f"[{session_id}] After dedup: {len(phrases)} phrases")
            await update_status(session_id, "moderating", 25)

            async def regen(lang, top, count):
                return await generate_phrases(lang, top, count)

            phrases = await filter_phrases(
                phrases,
                regenerate_fn=regen,
                language=language,
                topic=topic,
            )
            logger.info(f"[{session_id}] After moderation: {len(phrases)} phrases")

            if not phrases:
                raise ValueError("No phrases remained after moderation")

            base_count = max(1, round(duration_minutes * 60 / 9))
            for attempt in range(30):
                if len(phrases) >= base_count:
                    break
                needed = base_count - len(phrases)
                extra = await generate_phrases(language, topic, round(needed * 2))
                combined = deduplicate(phrases + extra)
                new_additions = combined[len(phrases):]
                if not new_additions:
                    logger.info(f"[{session_id}] Top-up {attempt + 1}: no new unique phrases, stopping")
                    break
                safe_additions = await filter_phrases(new_additions)
                phrases = phrases + safe_additions
                logger.info(f"[{session_id}] Top-up {attempt + 1}: +{len(safe_additions)} phrases → {len(phrases)} total")

            # ── Streaming audio generation ──────────────────────────────────────
            await update_status(session_id, "generating_audio", 40)
            chunks_by_index: dict[int, tuple[bytes, bytes]] = {}
            preview_checkpoints = [0.25, 0.50, 0.75]
            next_cp = 0
            current_preview_url: str | None = None
            gen_start = time.time()

            async for idx, total, chunk in generate_audio_streaming(phrases, language=language):
                chunks_by_index[idx] = chunk
                done = len(chunks_by_index)
                progress = 40 + int(done / total * 34)  # 40% → 74%
                await update_status(
                    session_id, "generating_audio", progress,
                    phrases_done=done, phrases_total=total,
                    preview_url=current_preview_url,
                )

                ratio = done / total
                if next_cp < len(preview_checkpoints) and ratio >= preview_checkpoints[next_cp]:
                    try:
                        ordered = [chunks_by_index[j] for j in sorted(chunks_by_index)]
                        preview_bytes = assemble_session(ordered, target_ms=duration_minutes * 60 * 1000)
                        preview_id = f"{session_id}_v{next_cp + 1}"
                        current_preview_url = await upload_session(preview_id, preview_bytes)
                        next_cp += 1
                        await update_status(
                            session_id, "generating_audio", progress,
                            phrases_done=done, phrases_total=total,
                            preview_url=current_preview_url,
                        )
                        logger.info(f"[{session_id}] Preview v{next_cp} uploaded")
                    except Exception as preview_err:
                        logger.warning(f"[{session_id}] Preview upload failed (non-fatal): {preview_err}")
                        next_cp += 1

            logger.info(f"[{session_id}] TTS complete for {len(chunks_by_index)} phrases")
            save_timing(duration_minutes, time.time() - gen_start)

            # ── Assemble final audio ────────────────────────────────────────────
            await update_status(session_id, "assembling", 75, preview_url=current_preview_url)
            ordered_chunks = [chunks_by_index[j] for j in sorted(chunks_by_index)]
            final_audio = assemble_session(ordered_chunks, target_ms=duration_minutes * 60 * 1000)
            logger.info(f"[{session_id}] Audio assembled: {len(final_audio)} bytes")

            await update_status(session_id, "uploading", 90, preview_url=current_preview_url)
            audio_url = await upload_session(session_id, final_audio)
            logger.info(f"[{session_id}] Uploaded. URL: {audio_url[:60]}...")

            await update_status(session_id, "done", 100, audio_url=audio_url, preview_url=current_preview_url)

    except TimeoutError:
        logger.error(f"[{session_id}] Timed out after {MAX_TIMEOUT}s")
        await update_status(session_id, "error", 0, error="Generation timed out")
    except Exception as e:
        cause = e.last_attempt.exception() if isinstance(e, RetryError) else e
        logger.error(f"[{session_id}] Error: {cause}", exc_info=True)
        await update_status(session_id, "error", 0, error=str(cause))


# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/interpret-topic")
async def interpret_topic_route(req: InterpretTopicRequest):
    try:
        interpretation = await interpret_topic(req.topic, req.language, req.refinement)
        return {"interpretation": interpretation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-session")
async def generate_session(
    req: GenerateSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(optional_user),
    x_guest_id: Optional[str] = Header(None),
):
    if req.duration_minutes not in (5, 10, 15, 20, 30):
        raise HTTPException(status_code=400, detail="duration_minutes must be 5, 10, 15, 20, or 30")

    # Enforce plan limits before creating anything
    await check_generation_limits(db, req.duration_minutes, user, x_guest_id)

    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    # Persist session record immediately (status=queued)
    db_session = TtsSession(
        id=session_id,
        user_id=user.id if user else None,
        guest_id=x_guest_id if not user else None,
        status="queued",
        progress=0,
        duration_minutes=req.duration_minutes,
        language=req.language,
        topic=req.topic,
        estimated_seconds=get_estimate(req.duration_minutes),
        expires_at=expires_at,
    )
    db.add(db_session)
    await db.flush()

    # Keep in-memory dict for real-time polling during generation
    async with sessions_lock:
        sessions[session_id] = {
            "status": "queued",
            "progress": 0,
            "audio_url": None,
            "error": None,
            "preview_url": None,
            "phrases_done": 0,
            "phrases_total": 0,
            "start_time": time.time(),
            "estimated_seconds": get_estimate(req.duration_minutes),
        }

    background_tasks.add_task(
        run_session_generation,
        session_id,
        req.language,
        req.topic,
        req.duration_minutes,
    )

    return {"session_id": session_id}


@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    async with sessions_lock:
        session = sessions.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session

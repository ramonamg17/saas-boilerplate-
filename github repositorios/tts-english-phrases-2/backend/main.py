import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from tenacity import RetryError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from services.audio_assembler import assemble_session
from services.cleanup_service import start_cleanup_scheduler, stop_cleanup_scheduler
from services.deduplicator import deduplicate
from services.moderator import filter_phrases
from services.phrase_generator import calc_num_phrases, generate_phrases, interpret_topic
from services.storage_service import upload_session
from services.tts_service import generate_all_audio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sessions: dict = {}
sessions_lock = asyncio.Lock()

MAX_TIMEOUT = int(os.getenv("MAX_GENERATION_TIMEOUT_SECONDS", "120"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_cleanup_scheduler(sessions)
    yield
    stop_cleanup_scheduler()


app = FastAPI(title="Language Learning Audio API", lifespan=lifespan)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def serve_frontend():
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Language Learning Audio API"}


class InterpretTopicRequest(BaseModel):
    language: str
    topic: str
    refinement: str | None = None


class GenerateSessionRequest(BaseModel):
    language: str
    topic: str
    duration_minutes: int


async def update_status(
    session_id: str,
    status: str,
    progress: int,
    audio_url: str | None = None,
    error: str | None = None,
) -> None:
    async with sessions_lock:
        sessions[session_id] = {
            "status": status,
            "progress": progress,
            "audio_url": audio_url,
            "error": error,
        }


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

            await update_status(session_id, "generating_audio", 40)
            audio_chunks = await generate_all_audio(phrases, language=language)
            logger.info(f"[{session_id}] TTS complete for {len(audio_chunks)} phrases")

            await update_status(session_id, "assembling", 75)
            final_audio = assemble_session(audio_chunks, target_ms=duration_minutes * 60 * 1000)
            logger.info(f"[{session_id}] Audio assembled: {len(final_audio)} bytes")

            await update_status(session_id, "uploading", 90)
            audio_url = await upload_session(session_id, final_audio)
            logger.info(f"[{session_id}] Uploaded. URL: {audio_url[:60]}...")

            await update_status(session_id, "done", 100, audio_url=audio_url)

    except TimeoutError:
        logger.error(f"[{session_id}] Timed out after {MAX_TIMEOUT}s")
        await update_status(session_id, "error", 0, error="Generation timed out")
    except Exception as e:
        cause = e.last_attempt.exception() if isinstance(e, RetryError) else e
        logger.error(f"[{session_id}] Error: {cause}", exc_info=True)
        await update_status(session_id, "error", 0, error=str(cause))


@app.post("/interpret-topic")
async def interpret_topic_route(req: InterpretTopicRequest):
    try:
        interpretation = await interpret_topic(req.topic, req.language, req.refinement)
        return {"interpretation": interpretation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-session")
async def generate_session(req: GenerateSessionRequest, background_tasks: BackgroundTasks):
    if req.duration_minutes not in (5, 10, 15, 20, 30):
        raise HTTPException(status_code=400, detail="duration_minutes must be 5, 10, 15, 20, or 30")

    session_id = str(uuid.uuid4())
    async with sessions_lock:
        sessions[session_id] = {
            "status": "queued",
            "progress": 0,
            "audio_url": None,
            "error": None,
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

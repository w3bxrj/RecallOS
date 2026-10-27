import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import update, text
import httpx


from app.core.config import settings
from app.core.db import SessionLocal
from app.core.redact import redact
from app.models.job import Job
from app.ws.publisher import ws_publisher
from app.core.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # 1. Bind WebSocket publisher to main event loop
    try:
        loop = asyncio.get_running_loop()
        ws_publisher.set_event_loop(loop)
    except Exception:
        pass

    # 2. Recover stranded jobs on startup
    try:
        with SessionLocal() as db:
            db.execute(
                update(Job)
                .where(Job.status.in_(["queued", "processing"]))
                .values(
                    status="failed",
                    error_message="Server restarted during processing",
                )
            )
            db.commit()
    except Exception:
        pass

    # 3. Model availability sanity check in production (fail fast warning, never blocks startup)
    if settings.ENV == "production" and settings.GEMINI_API_KEY:
        try:
            model_url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}"
            headers = {"x-goog-api-key": settings.GEMINI_API_KEY}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(model_url, headers=headers)
                if res.status_code == 404:
                    logger.warning(
                        "Configured GEMINI_MODEL '%s' was not found (HTTP 404). Flashcard generation may fail. Update GEMINI_MODEL env var.",
                        settings.GEMINI_MODEL,
                    )
                elif res.status_code in (401, 403):
                    logger.warning(
                        "Gemini API returned HTTP %d for model '%s'. Check GEMINI_API_KEY.",
                        res.status_code,
                        settings.GEMINI_MODEL,
                    )
                elif res.status_code != 200:
                    logger.warning(
                        "Gemini model check returned HTTP %d for model '%s'.",
                        res.status_code,
                        settings.GEMINI_MODEL,
                    )
                else:
                    logger.info("Gemini model '%s' verified successfully.", settings.GEMINI_MODEL)
        except Exception as check_exc:
            logger.warning("Failed to verify Gemini model at startup: %s", redact(str(check_exc)))

    yield


app = FastAPI(
    title="RecallOS API",
    description="Scientific spaced repetition and collaborative study operating system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware: allow only configured origins with credentials off
origins = settings.allowed_origins_list
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

from app.routers import auth, users, reviews, uploads, decks, ws, stats

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include Routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(decks.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(ws.router)


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check() -> dict:
    """Uptime health check endpoint (no DB call, for UptimeRobot / Render ping)."""
    return {"status": "ok"}


@app.get("/health/db", tags=["Health"])
def health_check_db() -> dict:
    """Database connectivity health check (executes SELECT 1 for manual checks)."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unreachable",
        ) from exc



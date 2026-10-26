import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import update, text


from app.core.config import settings
from app.core.db import SessionLocal
from app.models.job import Job
from app.ws.publisher import ws_publisher
from app.core.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)


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



from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Handle SQLite vs PostgreSQL engine arguments
engine_kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL (Neon free tier) pool sizing to prevent connection exhaustion
    engine_kwargs["pool_size"] = 3
    engine_kwargs["max_overflow"] = 2

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

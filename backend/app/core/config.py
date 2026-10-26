from typing import List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./recallos_dev.db"
    JWT_SECRET: str = "recallos-dev-secret-key-32-characters-minimum-for-security"
    JWT_EXPIRE_MINUTES: int = 1440
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_UPLOAD_MB: int = 10
    DAILY_CARD_LIMIT: int = 50
    ENABLE_DUEL: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not v:
            return v
        v = v.strip()
        # Normalise Postgres schemes to use the installed psycopg2 driver explicitly
        if v.startswith("postgres://"):
            return "postgresql+psycopg2://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg2://" + v[len("postgresql://"):]
        return v

    @property
    def allowed_origins_list(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        # Strip whitespace and trailing slash from every origin entry
        return [origin.strip().rstrip("/") for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_constraints(self) -> "Settings":
        if self.ENV.lower() == "production":
            if not self.DATABASE_URL or self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("In production, DATABASE_URL must not be empty or point to SQLite.")
            if (
                self.JWT_SECRET == "recallos-dev-secret-key-32-characters-minimum-for-security"
                or len(self.JWT_SECRET) < 32
            ):
                raise ValueError("In production, JWT_SECRET must not be the default secret and must be at least 32 characters long.")
            if any(o == "*" for o in self.allowed_origins_list):
                raise ValueError("In production, ALLOWED_ORIGINS must not contain wildcards ('*').")
        return self


settings = Settings()


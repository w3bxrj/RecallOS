from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./recallos_dev.db"
    JWT_SECRET: str = "recallos-dev-secret-key-32-characters-minimum-for-security"
    JWT_EXPIRE_MINUTES: int = 1440
    GEMINI_API_KEY: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_UPLOAD_MB: int = 10
    DAILY_CARD_LIMIT: int = 50
    ENABLE_DUEL: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()

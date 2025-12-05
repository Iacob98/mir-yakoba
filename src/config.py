from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Мир Якоба"
    debug: bool = False
    secret_key: str
    base_url: str = "http://localhost:8000"

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str
    telegram_webhook_secret: Optional[str] = None

    # OpenAI (for Whisper transcription)
    openai_api_key: Optional[str] = None

    # File storage
    upload_dir: Path = Path("./uploads")
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    max_audio_size: int = 50 * 1024 * 1024  # 50MB
    max_video_size: int = 100 * 1024 * 1024  # 100MB

    # Session
    session_expire_days: int = 30
    auth_code_expire_minutes: int = 5

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url


settings = Settings()

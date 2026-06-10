
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


    database_url: str = "postgresql+asyncpg://postgres:1111@localhost:5432/neuroscan"


    auth_enabled: bool = False
    jwt_secret_key: str = "change-me-to-a-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60


    upload_dir: str = "uploads"

    @property
    def upload_path(self) -> Path:
        path = _ROOT_DIR / self.upload_dir
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

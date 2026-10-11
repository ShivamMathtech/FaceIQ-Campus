from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend" / ".env", extra="ignore"
    )
    database_url: str = f'sqlite:///{ROOT / "storage" / "faceiq.db"}'
    encryption_key: str = ""
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    environment: str = "development"
    token_minutes: int = 60
    model_dir: str = str(ROOT / "storage" / "models")
    inference_interval_ms: int = 800
    max_upload_mb: int = 5
    frame_max_width: int = 960
    cv_threads: int = 2

    # No network-accessible mock switch: deterministic adapters exist only in tests.
    @property
    def origins(self):
        return [s.strip() for s in self.allowed_origins.split(",")]


@lru_cache
def get_settings():
    return Settings()

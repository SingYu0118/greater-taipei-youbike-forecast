from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
    )

    app_env: str = "development"
    data_dir: Path = Path("data")
    model_dir: Path = Path("artifacts/models")
    allowed_origins: str = "http://localhost:5173"
    collection_start_at: datetime | None = None
    raw_storage_backend: Literal["local", "r2"] = "local"

    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None

    request_timeout_seconds: float = 30.0
    request_attempts: int = 4
    ntpc_page_size: int = 1000

    @field_validator("collection_start_at")
    @classmethod
    def normalize_collection_start(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("COLLECTION_START_AT must include an explicit UTC offset")
        return value.astimezone(UTC)

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def cloud_raw_dir(self) -> Path:
        return self.data_dir / "cloud_raw"

    @property
    def formal_processed_dir(self) -> Path:
        return self.data_dir / "formal_processed"

    @property
    def formal_feature_path(self) -> Path:
        return self.data_dir / "formal_features" / "station_hour_ahead.parquet"

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]


settings = Settings()


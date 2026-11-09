from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    data_dir: Path = Path("data")
    model_dir: Path = Path("artifacts/models")
    allowed_origins: str = "http://localhost:5173"

    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None

    request_timeout_seconds: float = 30.0
    request_attempts: int = 4
    ntpc_page_size: int = 1000

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]


settings = Settings()


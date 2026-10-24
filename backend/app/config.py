from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    storage_dir: Path = ROOT / "data" / "raw"
    database_url: str = "sqlite:///./data/medishield.db"
    groq_api_key: str = ""
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"


settings = Settings()

"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_log_level: str = "INFO"
    database_url: str = "mysql+pymysql://marklens:marklens@127.0.0.1:3306/marklens?charset=utf8mb4"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking: str = "disabled"
    text_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    image_embedding_model: str = "Qdrant/resnet50-onnx"
    ocr_provider: str = "rapidocr"
    model_cache_dir: Path = REPOSITORY_ROOT / ".model-cache"
    upload_dir: Path = REPOSITORY_ROOT / "data" / "uploads"
    source_data_dir: Path = REPOSITORY_ROOT / "data" / "sources"
    cors_origins: str = "http://localhost:5173"
    model_runtime_enabled: bool = True
    max_upload_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 16_000_000
    agent_eager: bool = False
    retrieval_config_version: str = "heuristic-v1"
    risk_config_version: str = "teaching-v1"
    demo_mode: bool = Field(default=False, description="Expose seed/demo labels in responses.")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

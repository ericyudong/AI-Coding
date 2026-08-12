"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "益慧科技法务Agent"
    app_version: str = "1.0.0"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8010

    database_url: str = "sqlite+aiosqlite:///./legal_agent.db"
    data_dir: str = "data"

    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 32
    qdrant_path: str = "data/qdrant"

    parser_max_pages: int = 200
    parser_ocr_enabled: bool = True
    parser_ocr_dpi: int = 200
    parser_ocr_min_page_chars: int = 20
    parser_ocr_min_score: float = 0.5
    chunk_size: int = 800
    chunk_overlap: int = 100
    semantic_search_top_k: int = 20
    rag_top_k: int = 5
    rag_max_context_chars: int = 6000

    review_max_chars: int = 80000
    review_chunk_size: int = 12000

    bootstrap_admin_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"

    contract_max_upload_bytes: int = 100 * 1024 * 1024
    contract_max_batch_files: int = 50
    performance_alert_days: int = 7
    performance_alert_channels: str = "in_app,email"
    performance_alert_interval_seconds: int = 900
    performance_evidence_max_bytes: int = 50 * 1024 * 1024

    # SMTP email alerts (disabled by default → skip with log)
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_ssl: bool = True
    smtp_use_tls: bool = False

    # ERP sync: manual_import (CSV) | api (placeholder)
    erp_sync_mode: str = "manual_import"
    erp_api_base_url: str = ""
    erp_api_key: str = ""

    static_dir: str = ""
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def data_root() -> Path:
    settings = get_settings()
    root = Path(settings.data_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root

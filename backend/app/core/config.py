"""Application configuration.

All runtime configuration is read from environment variables or the project
root ``.env`` file.  Never hard-code API keys, database passwords or secrets.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    """Typed application settings (Pydantic Settings v2)."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Intelligent Vision Analysis Platform"
    app_version: str = "0.1.0"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    secret_key: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    # --- Paths (relative values are resolved against the project root) ---
    log_dir: Path = BACKEND_DIR / "logs"
    upload_dir: Path = BACKEND_DIR / "uploads"
    vector_db_dir: Path = BACKEND_DIR / "vector_db"
    models_config: Path = BACKEND_DIR / "config" / "models.yaml"

    # --- Upload limits ---
    max_image_mb: int = Field(default=20, ge=1, le=200)
    max_document_mb: int = Field(default=50, ge=1, le=500)

    # --- Database (not used in P1) ---
    database_url: SecretStr = SecretStr("sqlite:///./backend/data/ivap.db")
    db_echo: bool = False

    # --- Vision ---
    default_model: str = "ece-yolo"
    detector_mode: Literal["real", "mock"] = "real"
    model_preload: bool = True

    # --- LLM ---
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_timeout_seconds: int = Field(default=60, ge=5, le=600)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4000, ge=256, le=16000)
    llm_mock: bool = False

    # --- Embedding ---
    embedding_provider: Literal["openai", "local", "mock"] = "openai"
    embedding_api_key: SecretStr = SecretStr("")
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, ge=1)
    embedding_batch_size: int = Field(default=32, ge=1, le=512)

    # --- RAG ---
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    rag_chunk_size: int = Field(default=500, ge=50, le=4000)
    rag_chunk_overlap: int = Field(default=80, ge=0, le=1000)

    # --- Agent ---
    agent_max_steps: int = Field(default=6, ge=1, le=20)
    agent_timeout_seconds: int = Field(default=180, ge=30, le=600)
    agent_history_limit: int = Field(default=10, ge=1, le=50)

    # --- Auth (reserved) ---
    auth_enabled: bool = False

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @field_validator("log_dir", "upload_dir", "vector_db_dir", "models_config")
    @classmethod
    def _resolve_project_path(cls, value: Path) -> Path:
        """Resolve relative paths against the project root, not the cwd."""
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url_value(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.get_secret_value()) and bool(self.llm_model)

    @property
    def embedding_api_key_value(self) -> str:
        """Embedding key falls back to the LLM key when omitted."""
        return self.embedding_api_key.get_secret_value() or self.llm_api_key.get_secret_value()

    @property
    def embedding_base_url_value(self) -> str:
        return self.embedding_base_url or self.llm_base_url

    def ensure_dirs(self) -> None:
        """Create runtime directories if they do not exist."""
        for directory in (self.log_dir, self.upload_dir, self.vector_db_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Tests can call ``get_settings.cache_clear()`` to rebuild it.
    """
    return Settings()

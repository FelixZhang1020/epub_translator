"""Application configuration."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "ePub Translator"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_port: int = 5173

    # Database
    database_url: str = "sqlite+aiosqlite:///./epub_translator.db"

    # File storage (temporary files - project files are in projects/{id}/)
    upload_dir: Path = Path(__file__).parent.parent.parent.parent / "data" / "temp" / "uploads"
    output_dir: Path = Path(__file__).parent.parent.parent.parent / "data" / "temp" / "outputs"

    # Upload limits
    max_upload_size_mb: int = 100  # Maximum upload size in MB

    # Translation settings
    default_chunk_size: int = 500  # tokens
    max_retries: int = 3
    retry_delay: float = 1.0
    translation_throttle_delay: float = 0.5  # Delay between API calls (seconds)

    # CORS - dynamically built based on frontend_port
    cors_origins: list[str] = []

    # Authentication (optional - for network-exposed deployments)
    # Set API_AUTH_TOKEN to enable authentication on sensitive endpoints
    api_auth_token: Optional[str] = None
    # If True, require auth on all endpoints; if False, only on sensitive ones
    require_auth_all: bool = False

    # Feature flags
    enable_epub_export: bool = True  # Set to False to hide ePub export option (copyright compliance)

    # LLM API Keys (loaded from environment, used by LLMConfigService)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None  # Alibaba Qwen
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Build CORS origins based on frontend port
        if not self.cors_origins:
            self.cors_origins = [
                f"http://localhost:{self.frontend_port}",
                f"http://127.0.0.1:{self.frontend_port}",
            ]


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)

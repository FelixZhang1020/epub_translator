"""Application configuration."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "EPUB Translator"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_port: int = 5173

    # Database
    database_url: str = "sqlite+aiosqlite:///./epub_translator.db"

    # File storage
    upload_dir: Path = Path("./uploads")
    output_dir: Path = Path("./outputs")

    # Translation settings
    default_chunk_size: int = 500  # tokens
    max_retries: int = 3
    retry_delay: float = 1.0

    # CORS - dynamically built based on frontend_port
    cors_origins: list[str] = []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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

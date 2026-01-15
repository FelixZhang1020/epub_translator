"""LLM Configuration database model for storing API keys and settings."""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Text, Float, Integer
from sqlalchemy.orm import relationship

from .base import Base

# Environment variable mapping for each provider
ENV_VAR_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


class LLMConfiguration(Base):
    """Store LLM configurations including API keys in the database.

    This allows the backend to manage LLM configs directly without
    requiring the frontend to pass API keys on every request.
    """
    __tablename__ = "llm_configurations"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)  # User-friendly name
    provider = Column(String(50), nullable=False)  # openai, anthropic, gemini, etc.
    model = Column(String(100), nullable=False)  # gpt-4o-mini, claude-3-5-sonnet, etc.
    api_key = Column(Text, nullable=True)  # Encrypted API key (or plain for simplicity)
    base_url = Column(String(500), nullable=True)  # Custom base URL (for Ollama, etc.)
    temperature = Column(Float, nullable=True, default=0.7)  # LLM temperature (0.0-2.0)
    max_tokens = Column(Integer, nullable=True, default=4096)  # Max output tokens
    top_p = Column(Float, nullable=True)  # Top-p sampling parameter
    frequency_penalty = Column(Float, nullable=True)  # Frequency penalty (-2.0 to 2.0)
    presence_penalty = Column(Float, nullable=True)  # Presence penalty (-2.0 to 2.0)
    is_default = Column(Boolean, default=False)  # Default configuration
    is_active = Column(Boolean, default=True)  # Currently selected configuration

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<LLMConfiguration {self.name} ({self.provider}/{self.model})>"

    def get_env_api_key(self) -> Optional[str]:
        """Get API key from environment variable for this provider."""
        env_var = ENV_VAR_MAP.get(self.provider)
        if env_var:
            return os.getenv(env_var)
        return None

    def get_effective_api_key(self) -> Optional[str]:
        """Get the effective API key (database first, then environment)."""
        if self.api_key:
            return self.api_key
        return self.get_env_api_key()

    def has_effective_api_key(self) -> bool:
        """Check if an API key is available (database or environment)."""
        return bool(self.get_effective_api_key())

    def _mask_api_key(self) -> str:
        """Return a masked version of the API key for display."""
        key = self.get_effective_api_key()
        if not key:
            return ""
        if len(key) <= 12:
            return "••••••••"
        # Show first 4 and last 4 characters
        return f"{key[:4]}••••••••{key[-4:]}"

    def _get_api_key_source(self) -> str:
        """Get the source of the API key (database, environment, or none)."""
        if self.api_key:
            return "database"
        if self.get_env_api_key():
            return "environment"
        return "none"

    def to_dict(self, include_api_key: bool = False) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "max_tokens": self.max_tokens if self.max_tokens is not None else 4096,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "has_api_key": self.has_effective_api_key(),
            "api_key_source": self._get_api_key_source(),
            "masked_api_key": self._mask_api_key(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        if include_api_key:
            result["api_key"] = self.get_effective_api_key()
        return result

    def get_litellm_model_string(self) -> str:
        """Get the model string in LiteLLM format (provider/model)."""
        # Map provider names to litellm prefixes
        provider_map = {
            "openai": "",  # No prefix needed for OpenAI
            "anthropic": "anthropic/",
            "gemini": "gemini/",
            "qwen": "qwen/",
            "deepseek": "deepseek/",
            "ollama": "ollama/",
            "openrouter": "openrouter/",
        }
        prefix = provider_map.get(self.provider, f"{self.provider}/")

        # OpenAI models don't need prefix
        if self.provider == "openai":
            return self.model
        return f"{prefix}{self.model}"


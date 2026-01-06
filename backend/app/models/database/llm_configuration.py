"""LLM Configuration database model for storing API keys and settings."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Text, Float
from sqlalchemy.orm import relationship

from .base import Base


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
    is_default = Column(Boolean, default=False)  # Default configuration
    is_active = Column(Boolean, default=True)  # Currently selected configuration

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<LLMConfiguration {self.name} ({self.provider}/{self.model})>"

    def _mask_api_key(self) -> str:
        """Return a masked version of the API key for display."""
        if not self.api_key:
            return ""
        key = self.api_key
        if len(key) <= 12:
            return "••••••••"
        # Show first 4 and last 4 characters
        return f"{key[:4]}••••••••{key[-4:]}"

    def to_dict(self, include_api_key: bool = False) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "has_api_key": bool(self.api_key),
            "masked_api_key": self._mask_api_key(),  # Always include masked version
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
        if include_api_key and self.api_key:
            result["api_key"] = self.api_key
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

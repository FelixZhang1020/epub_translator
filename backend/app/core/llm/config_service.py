"""Unified LLM Configuration Service.

This service provides a centralized way to get LLM configuration for all
LLM-related operations. It supports multiple ways to specify configuration:

1. Direct parameters (api_key + model) - for debugging/testing
2. Config ID - reference a stored configuration
3. Active config - automatically use the currently active configuration
4. Environment variables - fallback to env vars
"""

import os
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.llm_configuration import LLMConfiguration


@dataclass
class ResolvedLLMConfig:
    """Resolved LLM configuration ready for use."""
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.7  # LLM temperature (0.0-2.0)
    config_id: Optional[str] = None  # ID if loaded from database
    config_name: Optional[str] = None  # Name if loaded from database

    def get_litellm_model(self) -> str:
        """Get model string in LiteLLM format."""
        # Provider prefixes for LiteLLM
        provider_prefixes = {
            "openai": "",  # No prefix for OpenAI
            "anthropic": "anthropic/",
            "gemini": "gemini/",
            "qwen": "qwen/",
            "deepseek": "deepseek/",
            "ollama": "ollama/",
            "openrouter": "openrouter/",
        }
        prefix = provider_prefixes.get(self.provider, f"{self.provider}/")

        if self.provider == "openai":
            return self.model
        return f"{prefix}{self.model}"


class LLMConfigService:
    """Service for resolving LLM configurations."""

    # Environment variable mapping for each provider
    ENV_VAR_MAP = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }

    @classmethod
    async def resolve_config(
        cls,
        db: AsyncSession,
        *,
        # Option 1: Direct parameters (highest priority)
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        # Option 2: Config ID
        config_id: Optional[str] = None,
    ) -> ResolvedLLMConfig:
        """Resolve LLM configuration from various sources.

        Priority order:
        1. Direct api_key + model (for debugging)
        2. config_id (reference stored config)
        3. Active configuration (is_active=True)
        4. Default configuration (is_default=True)
        5. Environment variables (fallback)

        Raises:
            ValueError: If no valid configuration can be resolved
        """
        # Priority 1: Direct parameters
        if api_key and model:
            resolved_provider = provider
            if not resolved_provider:
                # Try to infer provider from model string
                if "/" in model:
                    resolved_provider, model = model.split("/", 1)
                else:
                    resolved_provider = "openai"  # Default

            return ResolvedLLMConfig(
                provider=resolved_provider,
                model=model,
                api_key=api_key,
            )

        # Priority 2: Config ID
        if config_id:
            config = await cls._get_config_by_id(db, config_id)
            if config:
                return cls._config_to_resolved(config)
            raise ValueError(f"Configuration not found: {config_id}")

        # Priority 3: Active configuration
        config = await cls._get_active_config(db)
        if config:
            return cls._config_to_resolved(config)

        # Priority 4: Default configuration
        config = await cls._get_default_config(db)
        if config:
            return cls._config_to_resolved(config)

        # Priority 5: Environment variables (try common providers)
        for prov, env_var in cls.ENV_VAR_MAP.items():
            env_key = os.getenv(env_var)
            if env_key:
                # Use a default model for the provider
                default_models = {
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-sonnet-4-5-20250929",
                    "gemini": "gemini-2.5-flash",
                    "qwen": "qwen-plus",
                    "deepseek": "deepseek-chat",
                }
                return ResolvedLLMConfig(
                    provider=prov,
                    model=default_models.get(prov, "gpt-4o-mini"),
                    api_key=env_key,
                )

        raise ValueError(
            "No LLM configuration available. Please configure an LLM provider "
            "either through the settings page, or set environment variables."
        )

    @classmethod
    async def _get_config_by_id(
        cls, db: AsyncSession, config_id: str
    ) -> Optional[LLMConfiguration]:
        """Get configuration by ID."""
        result = await db.execute(
            select(LLMConfiguration).where(LLMConfiguration.id == config_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def _get_active_config(
        cls, db: AsyncSession
    ) -> Optional[LLMConfiguration]:
        """Get the currently active configuration."""
        result = await db.execute(
            select(LLMConfiguration).where(LLMConfiguration.is_active == True)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def _get_default_config(
        cls, db: AsyncSession
    ) -> Optional[LLMConfiguration]:
        """Get the default configuration."""
        result = await db.execute(
            select(LLMConfiguration).where(LLMConfiguration.is_default == True)
        )
        return result.scalar_one_or_none()

    @classmethod
    def _config_to_resolved(cls, config: LLMConfiguration) -> ResolvedLLMConfig:
        """Convert database config to resolved config."""
        import logging
        logger = logging.getLogger(__name__)

        resolved = ResolvedLLMConfig(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature if config.temperature is not None else 0.7,
            config_id=config.id,
            config_name=config.name,
        )

        logger.info(f"[Config Service] Resolved config: provider={resolved.provider}, model={resolved.model}, base_url={resolved.base_url}, config_name={resolved.config_name}")

        return resolved

    @classmethod
    async def update_last_used(cls, db: AsyncSession, config_id: str) -> None:
        """Update the last_used_at timestamp for a configuration."""
        config = await cls._get_config_by_id(db, config_id)
        if config:
            config.last_used_at = datetime.utcnow()
            await db.commit()

    @classmethod
    async def list_configs(
        cls, db: AsyncSession, include_api_key: bool = False
    ) -> list[dict]:
        """List all configurations."""
        result = await db.execute(
            select(LLMConfiguration).order_by(LLMConfiguration.created_at.desc())
        )
        configs = result.scalars().all()
        return [c.to_dict(include_api_key=include_api_key) for c in configs]

    @classmethod
    async def create_config(
        cls,
        db: AsyncSession,
        *,
        id: str,
        name: str,
        provider: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        is_default: bool = False,
        is_active: bool = False,
    ) -> LLMConfiguration:
        """Create a new configuration."""
        # If setting as default, unset other defaults
        if is_default:
            await cls._clear_default(db)

        # If setting as active, unset other actives
        if is_active:
            await cls._clear_active(db)

        config = LLMConfiguration(
            id=id,
            name=name,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            is_default=is_default,
            is_active=is_active,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def update_config(
        cls,
        db: AsyncSession,
        config_id: str,
        **updates,
    ) -> Optional[LLMConfiguration]:
        """Update an existing configuration."""
        config = await cls._get_config_by_id(db, config_id)
        if not config:
            return None

        # Handle default/active flags
        if updates.get("is_default"):
            await cls._clear_default(db)
        if updates.get("is_active"):
            await cls._clear_active(db)

        for key, value in updates.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        await db.commit()
        await db.refresh(config)
        return config

    @classmethod
    async def delete_config(cls, db: AsyncSession, config_id: str) -> bool:
        """Delete a configuration."""
        config = await cls._get_config_by_id(db, config_id)
        if not config:
            return False
        await db.delete(config)
        await db.commit()
        return True

    @classmethod
    async def set_active(cls, db: AsyncSession, config_id: str) -> bool:
        """Set a configuration as active."""
        config = await cls._get_config_by_id(db, config_id)
        if not config:
            return False
        await cls._clear_active(db)
        config.is_active = True
        await db.commit()
        return True

    @classmethod
    async def duplicate_config(
        cls,
        db: AsyncSession,
        config_id: str,
        new_id: str,
        new_name: str,
    ) -> Optional[LLMConfiguration]:
        """Duplicate an existing configuration including the API key.

        Args:
            db: Database session
            config_id: ID of the configuration to duplicate
            new_id: ID for the new configuration
            new_name: Name for the new configuration

        Returns:
            The new configuration, or None if source not found
        """
        source = await cls._get_config_by_id(db, config_id)
        if not source:
            return None

        # Create new config with same settings but new id/name
        # Do not copy is_default or is_active flags
        new_config = LLMConfiguration(
            id=new_id,
            name=new_name,
            provider=source.provider,
            model=source.model,
            api_key=source.api_key,
            base_url=source.base_url,
            temperature=source.temperature,
            is_default=False,
            is_active=False,
        )
        db.add(new_config)
        await db.commit()
        await db.refresh(new_config)
        return new_config

    @classmethod
    async def _clear_default(cls, db: AsyncSession) -> None:
        """Clear all default flags."""
        result = await db.execute(
            select(LLMConfiguration).where(LLMConfiguration.is_default == True)
        )
        for config in result.scalars().all():
            config.is_default = False

    @classmethod
    async def _clear_active(cls, db: AsyncSession) -> None:
        """Clear all active flags."""
        result = await db.execute(
            select(LLMConfiguration).where(LLMConfiguration.is_active == True)
        )
        for config in result.scalars().all():
            config.is_active = False


# Singleton instance
llm_config_service = LLMConfigService()

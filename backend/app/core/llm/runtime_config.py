"""Unified LLM Runtime Configuration.

This module provides a single source of truth for LLM configuration that
flows through the entire pipeline from database to actual LLM call.

Key components:
- LLMRuntimeConfig: Complete configuration for a single LLM request
- LLMConfigOverride: Optional request-level parameter overrides
- LLMConfigResolver: Resolves configuration from multiple sources
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Stage type for stage-specific defaults
StageType = Literal["analysis", "translation", "optimization", "proofreading"]


@dataclass
class LLMRuntimeConfig:
    """Complete LLM configuration resolved for a single request.

    This is the ONLY place LLM parameters should come from.
    All stages use this same config structure, ensuring parameters
    like temperature and max_tokens actually reach the LLM call.
    """

    # Connection parameters
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None

    # Generation parameters (with sensible defaults)
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None

    # Response format (for structured output)
    response_format: Optional[Dict[str, Any]] = None

    # Metadata (for logging/tracking)
    config_id: Optional[str] = None
    config_name: Optional[str] = None

    def get_litellm_model(self) -> str:
        """Get model string in LiteLLM format (provider/model)."""
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

    def to_litellm_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs for litellm.acompletion().

        This ensures all configured parameters actually reach the LLM call.
        """
        kwargs: Dict[str, Any] = {
            "model": self.get_litellm_model(),
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if self.base_url:
            kwargs["api_base"] = self.base_url

        if self.top_p is not None:
            kwargs["top_p"] = self.top_p

        if self.frequency_penalty is not None:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if self.presence_penalty is not None:
            kwargs["presence_penalty"] = self.presence_penalty

        if self.response_format:
            kwargs["response_format"] = self.response_format

        return kwargs

    def with_overrides(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> "LLMRuntimeConfig":
        """Create a copy with specific overrides applied.

        Useful for temporary changes without modifying the original config.
        """
        return LLMRuntimeConfig(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty,
            response_format=response_format if response_format is not None else self.response_format,
            config_id=self.config_id,
            config_name=self.config_name,
        )


@dataclass
class LLMConfigOverride:
    """Optional overrides that can be passed from API request.

    These have the highest priority and override both DB config
    and stage-specific defaults.
    """

    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    model: Optional[str] = None  # Override model selection
    response_format: Optional[Dict[str, Any]] = None


class LLMConfigResolver:
    """Resolves LLM configuration from multiple sources.

    Resolution priority (highest to lowest):
    1. Request override (LLMConfigOverride) - for testing/debugging
    2. Stored config by ID - specific configuration reference
    3. Active config (is_active=True) - user's selected config
    4. Default config (is_default=True) - fallback stored config
    5. Environment variables - last resort fallback

    Stage-specific temperature defaults are applied when the stored
    config doesn't specify a temperature.
    """

    # Environment variable mapping for each provider
    ENV_VAR_MAP = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }

    # Default models for environment variable fallback
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet-4-5-20250929",
        "gemini": "gemini-2.5-flash",
        "qwen": "qwen-plus",
        "deepseek": "deepseek-chat",
    }

    # Default values when nothing else is configured
    DEFAULTS = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    # Stage-specific default temperatures
    # Used when config doesn't specify a temperature
    STAGE_TEMPERATURES: Dict[str, float] = {
        "analysis": 0.3,  # More deterministic for structured JSON output
        "translation": 0.5,  # Balanced creativity for natural translation
        "optimization": 0.3,  # Careful, conservative refinement
        "proofreading": 0.3,  # Conservative suggestions
    }

    # Stage-specific default max_tokens
    STAGE_MAX_TOKENS: Dict[str, int] = {
        "analysis": 8192,  # Analysis can produce longer structured output
        "translation": 4096,  # Standard translation output
        "optimization": 4096,  # Similar to translation
        "proofreading": 2048,  # Suggestions are typically shorter
    }

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        *,
        config_id: Optional[str] = None,
        override: Optional[LLMConfigOverride] = None,
        stage: Optional[StageType] = None,
    ) -> LLMRuntimeConfig:
        """Resolve complete LLM configuration.

        Args:
            db: Database session
            config_id: Specific config ID to use
            override: Request-level parameter overrides
            stage: Current stage (affects default temperature/max_tokens)

        Returns:
            Fully resolved LLMRuntimeConfig ready for use

        Raises:
            ValueError: If no valid configuration can be resolved
        """
        from app.models.database.llm_configuration import LLMConfiguration

        config_record: Optional[LLMConfiguration] = None
        temperature_from_config = False
        max_tokens_from_config = False

        # Try to load from database (by priority)
        if config_id:
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.id == config_id)
            )
            config_record = result.scalar_one_or_none()
            if not config_record:
                raise ValueError(f"Configuration not found: {config_id}")

        if not config_record:
            # Try active config
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.is_active == True)
            )
            config_record = result.scalar_one_or_none()

        if not config_record:
            # Try default config
            result = await db.execute(
                select(LLMConfiguration).where(LLMConfiguration.is_default == True)
            )
            config_record = result.scalar_one_or_none()

        # Build runtime config
        if config_record:
            # Resolve API key (DB first, then environment)
            api_key = config_record.api_key
            if not api_key:
                env_var = cls.ENV_VAR_MAP.get(config_record.provider)
                if env_var:
                    api_key = os.environ.get(env_var, "")

            if not api_key:
                raise ValueError(
                    f"No API key available for configuration '{config_record.name}' "
                    f"(provider: {config_record.provider}). Please set the API key "
                    f"in settings or configure the environment variable."
                )

            # Check if temperature/max_tokens were explicitly set in config
            temperature_from_config = config_record.temperature is not None
            max_tokens_from_config = (
                hasattr(config_record, "max_tokens")
                and config_record.max_tokens is not None
            )

            runtime_config = LLMRuntimeConfig(
                provider=config_record.provider,
                model=config_record.model,
                api_key=api_key,
                base_url=config_record.base_url,
                temperature=(
                    config_record.temperature
                    if temperature_from_config
                    else cls.DEFAULTS["temperature"]
                ),
                max_tokens=(
                    config_record.max_tokens
                    if max_tokens_from_config
                    else cls.DEFAULTS["max_tokens"]
                ),
                config_id=config_record.id,
                config_name=config_record.name,
            )

            api_key_source = "database" if config_record.api_key else "environment"
            logger.info(
                f"Resolved config from DB: provider={runtime_config.provider}, "
                f"model={runtime_config.model}, config_name={runtime_config.config_name}, "
                f"api_key_source={api_key_source}"
            )

        else:
            # Fallback to environment variables
            runtime_config = cls._resolve_from_environment()

        # Apply stage-specific defaults if not explicitly configured
        if stage:
            if not temperature_from_config:
                stage_temp = cls.STAGE_TEMPERATURES.get(stage)
                if stage_temp is not None:
                    runtime_config.temperature = stage_temp
                    logger.debug(
                        f"Applied stage-specific temperature: "
                        f"stage={stage}, temperature={stage_temp}"
                    )

            if not max_tokens_from_config:
                stage_max = cls.STAGE_MAX_TOKENS.get(stage)
                if stage_max is not None:
                    runtime_config.max_tokens = stage_max
                    logger.debug(
                        f"Applied stage-specific max_tokens: "
                        f"stage={stage}, max_tokens={stage_max}"
                    )

        # Apply request overrides (highest priority)
        if override:
            if override.temperature is not None:
                runtime_config.temperature = override.temperature
            if override.max_tokens is not None:
                runtime_config.max_tokens = override.max_tokens
            if override.top_p is not None:
                runtime_config.top_p = override.top_p
            if override.model is not None:
                runtime_config.model = override.model
            if override.response_format is not None:
                runtime_config.response_format = override.response_format

            logger.debug(f"Applied request overrides: {override}")

        logger.info(
            f"Final config: model={runtime_config.model}, "
            f"temperature={runtime_config.temperature}, "
            f"max_tokens={runtime_config.max_tokens}"
        )

        return runtime_config

    @classmethod
    def _resolve_from_environment(cls) -> LLMRuntimeConfig:
        """Resolve config from environment variables as last resort.

        Raises:
            ValueError: If no API key found in environment
        """
        for provider, env_var in cls.ENV_VAR_MAP.items():
            api_key = os.environ.get(env_var)
            if api_key:
                model = cls.DEFAULT_MODELS.get(provider, cls.DEFAULTS["model"])
                logger.info(
                    f"Resolved config from environment: "
                    f"provider={provider}, model={model}"
                )
                return LLMRuntimeConfig(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    temperature=cls.DEFAULTS["temperature"],
                    max_tokens=cls.DEFAULTS["max_tokens"],
                )

        raise ValueError(
            "No LLM configuration available. Please configure an LLM provider "
            "either through the settings page, or set environment variables "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)."
        )


# Convenience function for quick resolution
async def resolve_llm_config(
    db: AsyncSession,
    *,
    config_id: Optional[str] = None,
    override: Optional[LLMConfigOverride] = None,
    stage: Optional[StageType] = None,
) -> LLMRuntimeConfig:
    """Convenience function to resolve LLM configuration.

    This is the recommended way to get LLM configuration in service code.

    Example:
        config = await resolve_llm_config(db, stage="translation")
        response = await llm_gateway.execute(system, user, config)
    """
    return await LLMConfigResolver.resolve(
        db, config_id=config_id, override=override, stage=stage
    )


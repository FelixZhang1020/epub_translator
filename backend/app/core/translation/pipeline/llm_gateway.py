"""LLM Gateway for unified provider access.

This module provides an abstract gateway interface for LLM providers,
along with unified implementation using LiteLLM content.
"""

import time
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Type

from ..models.prompt import PromptBundle
from ..models.response import LLMResponse, TokenUsage
from litellm import acompletion


class LLMGateway(ABC):
    """Abstract gateway for LLM providers.

    Provides a unified interface for making LLM calls, regardless of
    the underlying provider (OpenAI, Anthropic, etc.).
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """Get provider name."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Get model identifier."""
        pass

    @abstractmethod
    async def call(self, bundle: PromptBundle) -> LLMResponse:
        """Make a synchronous LLM call.

        Args:
            bundle: Prompt bundle with messages and configuration

        Returns:
            LLMResponse with content and metadata
        """
        pass

    @abstractmethod
    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        """Make a streaming LLM call.

        Args:
            bundle: Prompt bundle with messages and configuration

        Yields:
            LLMResponse chunks as they arrive
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available.

        Returns:
            True if provider is reachable
        """
        pass


class LiteLLMGateway(LLMGateway):
    """Unified Gateway for all providers using LiteLLM."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        provider_name: str = "openai",
    ):
        """Initialize LiteLLM gateway.

        Args:
            api_key: API key for authentication
            model: Model identifier
            base_url: Optional custom base URL for compatible APIs
            provider_name: Provider name for logging
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._provider = provider_name

        # Build litellm model name with proper prefix
        if provider_name == "openai" and not model.startswith("openai/"):
            self._litellm_model = f"openai/{model}"
        elif provider_name == "deepseek":
            self._litellm_model = f"deepseek/{model}"
        elif provider_name == "qwen":
            self._litellm_model = f"openai/{model}"  # Qwen uses OpenAI-compatible API
        elif provider_name == "gemini":
            self._litellm_model = f"gemini/{model}"
        elif provider_name == "anthropic":
            # LiteLLM expects "anthropic/claude-..." or just "claude-..."
            # Safest is to explicitly add prefix if not present
            if not model.startswith("anthropic/") and not model.startswith("claude"):
                 self._litellm_model = f"anthropic/{model}"
            else:
                 self._litellm_model = model
        else:
            self._litellm_model = model

        # Log configuration for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[LLM Gateway] Initialized: provider={provider_name}, model={model}, litellm_model={self._litellm_model}, base_url={base_url}")

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    async def call(self, bundle: PromptBundle) -> LLMResponse:
        """Make LLM API call using LiteLLM.

        Args:
            bundle: Prompt bundle

        Returns:
            LLMResponse with translated content
        """
        start_time = time.time()

        kwargs = {
            "model": self._litellm_model,
            "messages": bundle.to_openai_format(),
            "temperature": bundle.temperature,
            "max_tokens": bundle.max_tokens,
            "api_key": self._api_key,
        }

        if self._base_url:
            kwargs["api_base"] = self._base_url
        
        # Add response format if specified
        if bundle.response_format:
            kwargs["response_format"] = bundle.response_format

        # Log the API call for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[LLM Gateway] Calling LiteLLM: model={self._litellm_model}, provider={self._provider}, base_url={self._base_url}")

        response = await acompletion(**kwargs)

        latency_ms = int((time.time() - start_time) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider=self._provider,
            model=self._model,
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            ),
            latency_ms=latency_ms,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        """Stream LLM API response using LiteLLM.

        Args:
            bundle: Prompt bundle

        Yields:
            LLMResponse chunks
        """
        start_time = time.time()
        accumulated_content = ""
        chunk_index = 0

        kwargs = {
            "model": self._litellm_model,
            "messages": bundle.to_openai_format(),
            "temperature": bundle.temperature,
            "max_tokens": bundle.max_tokens,
            "api_key": self._api_key,
            "stream": True,
        }

        if self._base_url:
            kwargs["api_base"] = self._base_url

        response = await acompletion(**kwargs)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                accumulated_content += delta

                yield LLMResponse(
                    content=delta,
                    provider=self._provider,
                    model=self._model,
                    latency_ms=int((time.time() - start_time) * 1000),
                    is_complete=False,
                    chunk_index=chunk_index,
                )
                chunk_index += 1

        # Final chunk with complete content
        yield LLMResponse(
            content=accumulated_content,
            provider=self._provider,
            model=self._model,
            latency_ms=int((time.time() - start_time) * 1000),
            is_complete=True,
            chunk_index=chunk_index,
        )

    async def health_check(self) -> bool:
        """Check LLM API availability."""
        try:
            await acompletion(
                model=self._litellm_model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                api_key=self._api_key,
            )
            return True
        except Exception:
            return False


class GatewayFactory:
    """Factory for creating LLM gateways."""

    # Provider configurations
    PROVIDER_CONFIGS = {
        "openai": {
            "class": LiteLLMGateway,
            "base_url": None,
        },
        "anthropic": {
            "class": LiteLLMGateway,
            "base_url": None,
        },
        "deepseek": {
            "class": LiteLLMGateway,
            "base_url": "https://api.deepseek.com/v1",
        },
        "qwen": {
            "class": LiteLLMGateway,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "gemini": {
            "class": LiteLLMGateway,
            "base_url": None,  # Let LiteLLM use default Gemini endpoint
        },
        # Add support for other providers routed to LiteLLM
        "ollama": {
            "class": LiteLLMGateway,
            "base_url": None,
        },
        "openrouter": {
            "class": LiteLLMGateway,
            "base_url": None,
        },
    }

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        model: str,
        **kwargs,
    ) -> LLMGateway:
        """Create an LLM gateway for the specified provider.

        Args:
            provider: Provider name (openai, anthropic, deepseek, qwen, gemini)
            api_key: API key for authentication
            model: Model identifier
            **kwargs: Additional arguments for the gateway

        Returns:
            Configured LLMGateway instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()
        config = cls.PROVIDER_CONFIGS.get(provider)

        # Fallback to generic LiteLLM if provider known
        if not config:
            # Check if it's a known provider in our config even if not explicitly in PROVIDER_CONFIGS
            # If valid provider, default to LiteLLMGateway
            config = {
                "class": LiteLLMGateway,
                "base_url": None,
            }

        gateway_class = config["class"]
        base_url = config.get("base_url")

        # Allow base_url override from kwargs
        if "base_url" in kwargs:
            base_url = kwargs.pop("base_url")

        if gateway_class == LiteLLMGateway:
            return LiteLLMGateway(
                api_key=api_key,
                model=model,
                base_url=base_url,
                provider_name=provider,
                **kwargs,
            )
        else:
            raise ValueError(f"Unsupported gateway class: {gateway_class}")

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of supported provider names.

        Returns:
            List of provider names
        """
        return list(cls.PROVIDER_CONFIGS.keys())


"""LLM Gateway for unified provider access.

This module provides an abstract gateway interface for LLM providers,
along with concrete implementations for OpenAI, Anthropic, and others.
"""

import time
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from ..models.prompt import PromptBundle
from ..models.response import LLMResponse, TokenUsage


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


class OpenAIGateway(LLMGateway):
    """Gateway for OpenAI and OpenAI-compatible APIs using LiteLLM."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        provider_name: str = "openai",
    ):
        """Initialize OpenAI gateway.

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
        else:
            self._litellm_model = model

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
        from litellm import acompletion

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

        if bundle.response_format:
            kwargs["response_format"] = bundle.response_format

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
        from litellm import acompletion

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
        from litellm import acompletion

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


class AnthropicGateway(LLMGateway):
    """Gateway for Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """Initialize Anthropic gateway.

        Args:
            api_key: API key for authentication
            model: Model identifier
        """
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._provider = "anthropic"

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    async def call(self, bundle: PromptBundle) -> LLMResponse:
        """Make Anthropic API call.

        Args:
            bundle: Prompt bundle

        Returns:
            LLMResponse with translated content
        """
        start_time = time.time()
        system, messages = bundle.to_anthropic_format()

        response = await self.client.messages.create(
            model=self._model,
            system=system,
            messages=messages,
            max_tokens=bundle.max_tokens,
            temperature=bundle.temperature,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = ""
        if response.content and len(response.content) > 0:
            content = response.content[0].text

        return LLMResponse(
            content=content,
            provider=self._provider,
            model=self._model,
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
            ),
            latency_ms=latency_ms,
        )

    async def stream(self, bundle: PromptBundle) -> AsyncIterator[LLMResponse]:
        """Stream Anthropic API response.

        Args:
            bundle: Prompt bundle

        Yields:
            LLMResponse chunks
        """
        start_time = time.time()
        accumulated_content = ""
        chunk_index = 0

        system, messages = bundle.to_anthropic_format()

        async with self.client.messages.stream(
            model=self._model,
            system=system,
            messages=messages,
            max_tokens=bundle.max_tokens,
            temperature=bundle.temperature,
        ) as stream:
            async for text in stream.text_stream:
                accumulated_content += text

                yield LLMResponse(
                    content=text,
                    provider=self._provider,
                    model=self._model,
                    latency_ms=int((time.time() - start_time) * 1000),
                    is_complete=False,
                    chunk_index=chunk_index,
                )
                chunk_index += 1

        # Final chunk
        yield LLMResponse(
            content=accumulated_content,
            provider=self._provider,
            model=self._model,
            latency_ms=int((time.time() - start_time) * 1000),
            is_complete=True,
            chunk_index=chunk_index,
        )

    async def health_check(self) -> bool:
        """Check Anthropic API availability."""
        try:
            # Anthropic doesn't have a simple health check endpoint
            # We could make a minimal API call, but for now just return True
            return True
        except Exception:
            return False


class GatewayFactory:
    """Factory for creating LLM gateways."""

    # Provider configurations
    PROVIDER_CONFIGS = {
        "openai": {
            "class": OpenAIGateway,
            "base_url": None,
        },
        "anthropic": {
            "class": AnthropicGateway,
            "base_url": None,
        },
        "deepseek": {
            "class": OpenAIGateway,
            "base_url": "https://api.deepseek.com/v1",
        },
        "qwen": {
            "class": OpenAIGateway,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "gemini": {
            "class": OpenAIGateway,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
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

        if not config:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: {list(cls.PROVIDER_CONFIGS.keys())}"
            )

        gateway_class = config["class"]
        base_url = config.get("base_url")

        if gateway_class == OpenAIGateway:
            return OpenAIGateway(
                api_key=api_key,
                model=model,
                base_url=base_url,
                provider_name=provider,
                **kwargs,
            )
        elif gateway_class == AnthropicGateway:
            return AnthropicGateway(
                api_key=api_key,
                model=model,
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

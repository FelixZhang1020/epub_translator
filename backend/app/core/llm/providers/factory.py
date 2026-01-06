"""LLM Provider Factory."""

from typing import Type

from app.core.llm.adapter import LLMAdapter
from app.core.llm.providers.openai import OpenAIAdapter
from app.core.llm.providers.anthropic import AnthropicAdapter
from app.core.llm.providers.gemini import GeminiAdapter
from app.core.llm.providers.qwen import QwenAdapter
from app.core.llm.providers.deepseek import DeepSeekAdapter


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    _providers: dict[str, Type[LLMAdapter]] = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "gemini": GeminiAdapter,
        "qwen": QwenAdapter,
        "deepseek": DeepSeekAdapter,
    }

    @classmethod
    def register(cls, name: str, provider_class: Type[LLMAdapter]):
        """Register a new provider."""
        cls._providers[name] = provider_class

    @classmethod
    def create(cls, provider: str, model: str, api_key: str, **kwargs) -> LLMAdapter:
        """Create a provider instance."""
        if provider not in cls._providers:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls._providers.keys())}")
        return cls._providers[provider](model=model, api_key=api_key, **kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        """List available providers."""
        return list(cls._providers.keys())

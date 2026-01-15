"""Unified LLM Gateway for all provider access.

This module provides a single gateway for all LLM calls across all stages.
It takes LLMRuntimeConfig directly, ensuring that configured parameters
(temperature, max_tokens) actually reach the LLM call.

Key benefits:
- Single entry point for all LLM calls
- Parameters from config flow directly to LLM
- Consistent logging and error handling
- Support for both sync and streaming calls
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from litellm import acompletion

from .runtime_config import LLMRuntimeConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    # For streaming responses
    is_complete: bool = True
    chunk_index: int = 0

    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def estimated_cost(self) -> float:
        """Estimate cost based on token counts.

        Note: This is a rough estimate. Actual pricing varies by model.
        TODO: Implement proper cost calculation based on model pricing.
        """
        # Placeholder - would need model-specific pricing
        return 0.0


class UnifiedLLMGateway:
    """Unified gateway for all LLM interactions.

    This gateway:
    1. Takes LLMRuntimeConfig directly (no separate parameter passing)
    2. Ensures temperature, max_tokens, etc. reach the LLM call
    3. Provides consistent interface for all stages
    4. Handles provider-specific model naming

    Usage:
        config = await resolve_llm_config(db, stage="translation")
        response = await UnifiedLLMGateway.execute(
            system_prompt="You are a translator...",
            user_prompt="Translate: Hello",
            config=config,
        )
    """

    @classmethod
    async def execute(
        cls,
        system_prompt: str,
        user_prompt: str,
        config: LLMRuntimeConfig,
        *,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Execute LLM call with given prompts and config.

        Args:
            system_prompt: System message content
            user_prompt: User message content
            config: Complete LLM configuration (temperature, max_tokens from here!)
            response_format: Optional JSON schema for structured output

        Returns:
            Standardized LLMResponse

        Raises:
            Exception: If LLM call fails
        """
        start_time = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Build kwargs from config - this is the key!
        # Temperature, max_tokens, etc. come from config, not hardcoded
        kwargs = config.to_litellm_kwargs()
        kwargs["messages"] = messages

        # Override response format if provided
        if response_format:
            kwargs["response_format"] = response_format

        logger.info(
            f"LLM call: model={config.model}, provider={config.provider}, "
            f"temperature={config.temperature}, max_tokens={config.max_tokens}"
        )

        try:
            response = await acompletion(**kwargs)

            latency_ms = int((time.time() - start_time) * 1000)

            result = LLMResponse(
                content=response.choices[0].message.content or "",
                model=config.model,
                provider=config.provider,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
                latency_ms=latency_ms,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

            logger.info(
                f"LLM response: tokens={result.total_tokens}, latency={latency_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(
                f"LLM call failed: model={config.model}, error={e}"
            )
            raise

    @classmethod
    async def execute_with_messages(
        cls,
        messages: List[Dict[str, str]],
        config: LLMRuntimeConfig,
        *,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Execute LLM call with pre-built messages array.

        Useful when you need more control over message structure
        (e.g., multi-turn conversations, assistant messages).

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Complete LLM configuration
            response_format: Optional JSON schema for structured output

        Returns:
            Standardized LLMResponse
        """
        start_time = time.time()

        kwargs = config.to_litellm_kwargs()
        kwargs["messages"] = messages

        if response_format:
            kwargs["response_format"] = response_format

        logger.info(
            f"LLM call (messages): model={config.model}, "
            f"temperature={config.temperature}, message_count={len(messages)}"
        )

        try:
            response = await acompletion(**kwargs)

            latency_ms = int((time.time() - start_time) * 1000)

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=config.model,
                provider=config.provider,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
                latency_ms=latency_ms,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except Exception as e:
            logger.error(f"LLM call (messages) failed: {e}")
            raise

    @classmethod
    async def stream(
        cls,
        system_prompt: str,
        user_prompt: str,
        config: LLMRuntimeConfig,
    ) -> AsyncIterator[LLMResponse]:
        """Stream LLM response.

        Yields partial responses as they arrive from the LLM.

        Args:
            system_prompt: System message content
            user_prompt: User message content
            config: Complete LLM configuration

        Yields:
            LLMResponse chunks with is_complete=False until final chunk
        """
        start_time = time.time()
        accumulated_content = ""
        chunk_index = 0

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = config.to_litellm_kwargs()
        kwargs["messages"] = messages
        kwargs["stream"] = True

        logger.info(
            f"LLM stream: model={config.model}, provider={config.provider}, "
            f"temperature={config.temperature}"
        )

        try:
            response = await acompletion(**kwargs)

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    accumulated_content += delta

                    yield LLMResponse(
                        content=delta,
                        model=config.model,
                        provider=config.provider,
                        latency_ms=int((time.time() - start_time) * 1000),
                        is_complete=False,
                        chunk_index=chunk_index,
                    )
                    chunk_index += 1

            # Final chunk with complete content
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"LLM stream complete: latency={latency_ms}ms")

            yield LLMResponse(
                content=accumulated_content,
                model=config.model,
                provider=config.provider,
                latency_ms=latency_ms,
                is_complete=True,
                chunk_index=chunk_index,
            )

        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    @classmethod
    async def health_check(cls, config: LLMRuntimeConfig) -> bool:
        """Check if the LLM provider is available.

        Args:
            config: LLM configuration to test

        Returns:
            True if provider responds successfully
        """
        try:
            kwargs = config.to_litellm_kwargs()
            kwargs["messages"] = [{"role": "user", "content": "Hi"}]
            kwargs["max_tokens"] = 5

            await acompletion(**kwargs)
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {config.model}: {e}")
            return False


# Convenience alias for shorter imports
LLMGateway = UnifiedLLMGateway


# Convenience function for simple calls
async def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: LLMRuntimeConfig,
    *,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """Convenience function for simple LLM calls.

    Returns just the content string instead of full LLMResponse.

    Example:
        config = await resolve_llm_config(db, stage="translation")
        result = await call_llm(
            system_prompt="You are a translator.",
            user_prompt="Translate: Hello",
            config=config,
        )
    """
    response = await UnifiedLLMGateway.execute(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        response_format=response_format,
    )
    return response.content


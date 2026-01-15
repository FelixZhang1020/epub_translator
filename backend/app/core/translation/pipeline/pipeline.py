"""Main translation pipeline orchestrator.

This module provides the TranslationPipeline class that coordinates
all pipeline components for end-to-end translation.
"""

from dataclasses import dataclass
from typing import AsyncIterator, Optional

from app.core.llm.runtime_config import LLMRuntimeConfig

from ..models.context import ExistingTranslation, TranslationContext, TranslationMode
from ..models.prompt import PromptBundle
from ..models.result import TranslationResult
from .llm_gateway import GatewayFactory, LLMGateway
from .output_processor import OutputProcessor
from .prompt_engine import PromptEngine


@dataclass
class PipelineConfig:
    """Configuration for translation pipeline.

    Supports two initialization modes:
    1. New: Pass llm_config (LLMRuntimeConfig) - recommended
    2. Legacy: Pass provider, model, api_key individually - for backward compatibility

    The llm_config takes precedence if provided.
    """

    # New way: unified config
    llm_config: Optional[LLMRuntimeConfig] = None

    # Legacy way: individual params (for backward compatibility)
    provider: str = ""
    model: str = ""
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None

    # Workflow params
    mode: TranslationMode = TranslationMode.DIRECT
    stream: bool = False
    max_retries: int = 3

    def __post_init__(self):
        """Initialize derived fields from llm_config if provided."""
        if self.llm_config:
            self.provider = self.llm_config.provider
            self.model = self.llm_config.model
            self.api_key = self.llm_config.api_key
            self.temperature = self.llm_config.temperature
            self.max_tokens = self.llm_config.max_tokens
            self.base_url = self.llm_config.base_url


class TranslationPipeline:
    """Main orchestrator for the translation pipeline.

    Coordinates the flow:
    Context -> PromptEngine -> PromptBundle -> LLMGateway -> OutputProcessor -> Result

    Supports:
    - Single-step translation (direct, author-aware, optimization)
    - Streaming responses
    - Prompt preview
    """

    def __init__(self, config: PipelineConfig):
        """Initialize translation pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.gateway = GatewayFactory.create(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
        )
        self.output_processor = OutputProcessor()

    async def translate(self, context: TranslationContext) -> TranslationResult:
        """Execute the full translation pipeline.

        Flow:
        1. Build prompts from context using PromptEngine
        2. Call LLM via gateway
        3. Process output

        Args:
            context: Complete translation context

        Returns:
            Processed TranslationResult
        """
        # Build prompt
        prompt_bundle = PromptEngine.build(context)

        # Apply config overrides
        if self.config.temperature is not None:
            prompt_bundle.temperature = self.config.temperature
        if self.config.max_tokens is not None:
            prompt_bundle.max_tokens = self.config.max_tokens

        # Call LLM
        response = await self.gateway.call(prompt_bundle)

        # Process output
        result = self.output_processor.process(response, context)

        return result

    async def translate_stream(
        self, context: TranslationContext
    ) -> AsyncIterator[str]:
        """Streaming translation for real-time UI updates.

        Yields partial translation chunks as they arrive from the LLM.

        Args:
            context: Translation context

        Yields:
            Translation text chunks
        """
        prompt_bundle = PromptEngine.build(context)

        async for chunk in self.gateway.stream(prompt_bundle):
            if not chunk.is_complete:
                yield chunk.content

    def preview(self, context: TranslationContext) -> dict:
        """Preview prompts without making LLM call.

        Useful for displaying prompts to users before execution.

        Args:
            context: Translation context

        Returns:
            Preview dictionary with rendered prompts and variables
        """
        return PromptEngine.preview_with_highlights(context)

    def preview_bundle(self, context: TranslationContext) -> PromptBundle:
        """Get the raw PromptBundle for inspection.

        Args:
            context: Translation context

        Returns:
            PromptBundle that would be sent to LLM
        """
        return PromptEngine.build(context)

    async def health_check(self) -> bool:
        """Check if LLM provider is available.

        Returns:
            True if provider is reachable
        """
        return await self.gateway.health_check()


class PipelineFactory:
    """Factory for creating translation pipelines."""

    @staticmethod
    def create(
        provider: str,
        model: str,
        api_key: str,
        mode: TranslationMode = TranslationMode.DIRECT,
        **kwargs,
    ) -> TranslationPipeline:
        """Create a configured translation pipeline.

        Args:
            provider: LLM provider name
            model: Model identifier
            api_key: API key
            mode: Translation mode
            **kwargs: Additional configuration options

        Returns:
            Configured TranslationPipeline
        """
        config = PipelineConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            mode=mode,
            **kwargs,
        )
        return TranslationPipeline(config)


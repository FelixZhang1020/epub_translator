"""Main translation pipeline orchestrator.

This module provides the TranslationPipeline class that coordinates
all pipeline components for end-to-end translation.
"""

from dataclasses import dataclass
from typing import AsyncIterator, Optional

from ..models.context import ExistingTranslation, TranslationContext, TranslationMode
from ..models.prompt import PromptBundle
from ..models.result import TranslationResult
from .llm_gateway import GatewayFactory, LLMGateway
from .output_processor import OutputProcessor
from .prompt_engine import PromptEngine


@dataclass
class PipelineConfig:
    """Configuration for translation pipeline."""

    provider: str
    model: str
    api_key: str
    mode: TranslationMode = TranslationMode.DIRECT
    stream: bool = False
    max_retries: int = 3
    temperature: Optional[float] = None  # Override default
    max_tokens: Optional[int] = None  # Override default


class TranslationPipeline:
    """Main orchestrator for the translation pipeline.

    Coordinates the flow:
    Context -> PromptEngine -> PromptBundle -> LLMGateway -> OutputProcessor -> Result

    Supports:
    - Single-step translation (direct, author-aware, optimization)
    - Multi-step iterative translation
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

    async def translate_iterative(
        self,
        context: TranslationContext,
        steps: int = 2,
    ) -> TranslationResult:
        """Multi-step iterative translation.

        Performs translation in multiple passes:
        1. Step 1: Create literal/accurate translation
        2. Step 2: Refine for naturalness

        Args:
            context: Translation context
            steps: Number of refinement steps (default 2)

        Returns:
            Final TranslationResult after all steps
        """
        from ..strategies import IterativeStrategy

        # Step 1: Initial translation (literal)
        step1_strategy = IterativeStrategy(step=1)
        step1_bundle = step1_strategy.build(context)

        step1_response = await self.gateway.call(step1_bundle)
        literal_text = self.output_processor._extract_translation(step1_response.content)

        # Step 2: Refinement
        step2_context = context.model_copy()
        step2_context.existing = ExistingTranslation(
            text=literal_text,
            provider=self.config.provider,
            model=self.config.model,
            version=1,
        )

        step2_strategy = IterativeStrategy(step=2)
        step2_bundle = step2_strategy.build(step2_context)

        step2_response = await self.gateway.call(step2_bundle)

        # Process final result
        result = self.output_processor.process(step2_response, step2_context)
        result.step_index = 2
        result.total_steps = steps

        # Add tokens from both steps
        result.tokens_used = (
            step1_response.usage.total_tokens + step2_response.usage.total_tokens
        )

        return result

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

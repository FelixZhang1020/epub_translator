"""Translation pipeline components.

This module provides the core pipeline components for translation:
- ContextBuilder: Builds TranslationContext from database entities
- PromptEngine: Builds prompts using strategy pattern
- LLMGateway: Unified interface for LLM providers
- OutputProcessor: Processes raw LLM responses
- TranslationPipeline: Orchestrates the complete flow
"""

from .context_builder import ContextBuilder
from .prompt_engine import PromptEngine
from .llm_gateway import LLMGateway, GatewayFactory
from .output_processor import OutputProcessor
from .pipeline import TranslationPipeline, PipelineConfig

__all__ = [
    "ContextBuilder",
    "PromptEngine",
    "LLMGateway",
    "GatewayFactory",
    "OutputProcessor",
    "TranslationPipeline",
    "PipelineConfig",
]


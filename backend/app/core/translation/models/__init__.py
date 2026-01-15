"""Translation pipeline data models.

This module provides structured data models for the translation pipeline,
ensuring type safety and clear contracts between components.
"""

from .context import (
    TranslationMode,
    SourceMaterial,
    ExistingTranslation,
    BookAnalysisContext,
    TranslationPrinciples,
    AdjacentContext,
    TranslationContext,
)
from .prompt import Message, PromptBundle
from .response import TokenUsage, LLMResponse
from .result import QualityFlag, TranslationResult

__all__ = [
    # Context models
    "TranslationMode",
    "SourceMaterial",
    "ExistingTranslation",
    "BookAnalysisContext",
    "TranslationPrinciples",
    "AdjacentContext",
    "TranslationContext",
    # Prompt models
    "Message",
    "PromptBundle",
    # Response models
    "TokenUsage",
    "LLMResponse",
    # Result models
    "QualityFlag",
    "TranslationResult",
]


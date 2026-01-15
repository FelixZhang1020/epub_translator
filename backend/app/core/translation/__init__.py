"""Translation package.

This package provides the translation pipeline and orchestration components.

Architecture:
- models/: Data models (TranslationContext, PromptBundle, etc.)
- strategies/: Prompt strategies for different translation modes
- pipeline/: Pipeline components (ContextBuilder, PromptEngine, etc.)
- orchestrator.py: Orchestrator using pipeline architecture
"""

# Re-export models for convenience
from .models import (
    # Context models
    TranslationMode,
    SourceMaterial,
    ExistingTranslation,
    BookAnalysisContext,
    TranslationPrinciples,
    AdjacentContext,
    TranslationContext,
    # Prompt models
    Message,
    PromptBundle,
    # Response models
    TokenUsage,
    LLMResponse,
    # Result models
    QualityFlag,
    TranslationResult,
)

# Re-export pipeline components
from .pipeline import (
    ContextBuilder,
    PromptEngine,
    LLMGateway,
    GatewayFactory,
    OutputProcessor,
    TranslationPipeline,
    PipelineConfig,
)

# Re-export orchestrator
from .orchestrator import TranslationOrchestrator


__all__ = [
    # Models
    "TranslationMode",
    "SourceMaterial",
    "ExistingTranslation",
    "BookAnalysisContext",
    "TranslationPrinciples",
    "AdjacentContext",
    "TranslationContext",
    "Message",
    "PromptBundle",
    "TokenUsage",
    "LLMResponse",
    "QualityFlag",
    "TranslationResult",
    # Pipeline
    "ContextBuilder",
    "PromptEngine",
    "LLMGateway",
    "GatewayFactory",
    "OutputProcessor",
    "TranslationPipeline",
    "PipelineConfig",
    # Orchestrator
    "TranslationOrchestrator",
]


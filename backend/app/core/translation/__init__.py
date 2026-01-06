"""Translation package.

This package provides the translation pipeline and orchestration components.

Architecture:
- models/: Data models (TranslationContext, PromptBundle, etc.)
- strategies/: Prompt strategies for different translation modes
- pipeline/: Pipeline components (ContextBuilder, PromptEngine, etc.)
- orchestrator.py: Legacy orchestrator (backwards compatible)
- orchestrator_v2.py: New orchestrator using pipeline architecture
"""

from typing import TYPE_CHECKING

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

# Lazy imports for orchestrators to avoid circular import issues
# and missing dependencies during development
if TYPE_CHECKING:
    from .orchestrator import TranslationOrchestrator
    from .orchestrator_v2 import TranslationOrchestratorV2


def get_orchestrator():
    """Get the legacy TranslationOrchestrator class."""
    from .orchestrator import TranslationOrchestrator
    return TranslationOrchestrator


def get_orchestrator_v2():
    """Get the new TranslationOrchestratorV2 class."""
    from .orchestrator_v2 import TranslationOrchestratorV2
    return TranslationOrchestratorV2


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
    # Orchestrator getters
    "get_orchestrator",
    "get_orchestrator_v2",
]

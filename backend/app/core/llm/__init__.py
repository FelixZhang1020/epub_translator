"""LLM integration package.

This package provides:
- LLM configuration management (LLMConfigService, LLMConfigManager)
- Model and provider information (LLMService with get_providers, get_models)
- Cost estimation and connection testing

For actual translation, use the translation pipeline:
- app.core.translation.pipeline.TranslationPipeline
- app.core.translation.pipeline.GatewayFactory
"""

from .service import (
    LLMService,
    llm_service,
    ModelInfo,
    ProviderInfo,
    CostEstimate,
)

from .config_service import LLMConfigService, llm_config_service, ResolvedLLMConfig

__all__ = [
    "LLMService",
    "llm_service",
    "ModelInfo",
    "ProviderInfo",
    "CostEstimate",

    "LLMConfigService",
    "llm_config_service",
    "ResolvedLLMConfig",
]


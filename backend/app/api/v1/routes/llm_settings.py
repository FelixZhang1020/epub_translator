"""LLM Settings API routes - Using LiteLLM for unified model access."""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_service, llm_config, ModelInfo, ProviderInfo
from app.core.llm.config import LLMProviderConfig, LLMModelConfig
from app.core.llm.config_service import LLMConfigService, llm_config_service
from app.models.database import get_db

router = APIRouter()


class TestConnectionRequest(BaseModel):
    """Request to test LLM connection."""
    model: str  # LiteLLM model ID (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
    api_key: Optional[str] = None  # Optional - can use env var


class EstimateCostRequest(BaseModel):
    """Request to estimate translation cost."""
    model: str
    text: str
    output_ratio: float = 1.5  # Chinese output typically 1.5x English input


class AddProviderRequest(BaseModel):
    """Request to add a custom provider."""
    name: str
    display_name: str
    api_key_env_var: str
    base_url: Optional[str] = None
    models: list[dict]


# ========== New LiteLLM-based endpoints ==========


@router.get("/llm/providers")
async def list_providers() -> list[ProviderInfo]:
    """List available LLM providers with their configuration status.

    Returns providers with:
    - name: Provider identifier
    - display_name: Human-readable name
    - api_key_env_var: Environment variable for API key
    - has_api_key: Whether API key is configured
    - model_count: Number of recommended models
    """
    return llm_service.get_providers()


@router.get("/llm/models")
async def list_models(provider: Optional[str] = None) -> list[ModelInfo]:
    """List available models with pricing information.

    Args:
        provider: Optional provider name to filter by

    Returns models with:
    - id: LiteLLM model ID
    - provider: Provider name
    - display_name: Human-readable name
    - input_cost_per_1k: Input cost per 1K tokens (USD)
    - output_cost_per_1k: Output cost per 1K tokens (USD)
    - max_tokens: Maximum output tokens
    - context_window: Maximum context length
    """
    return llm_service.get_models(provider)


@router.get("/llm/models/{provider}")
async def get_provider_models(provider: str) -> list[ModelInfo]:
    """Get models for a specific provider.

    Args:
        provider: Provider name (e.g., "openai", "anthropic", "gemini")
    """
    models = llm_service.get_models(provider)
    if not models:
        raise HTTPException(
            status_code=404,
            detail=f"No models found for provider '{provider}'"
        )
    return models


@router.post("/llm/test")
async def test_connection(request: TestConnectionRequest):
    """Test LLM model connection.

    Args:
        request: Model ID and optional API key

    Returns:
        success: Whether connection was successful
        message: Status message
    """
    try:
        is_success, message = await llm_service.test_connection(
            model=request.model,
            api_key=request.api_key,
        )
        return {
            "success": is_success,
            "message": message,
            "model": request.model,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "model": request.model,
        }


@router.post("/llm/estimate-cost")
async def estimate_cost(request: EstimateCostRequest):
    """Estimate translation cost for given text.

    Args:
        request: Model, text, and output ratio

    Returns:
        input_tokens: Estimated input tokens
        output_tokens_estimate: Estimated output tokens
        input_cost: Input cost in USD
        output_cost_estimate: Estimated output cost in USD
        total_cost_estimate: Total estimated cost in USD
        model: Model used for estimate
    """
    estimate = llm_service.estimate_cost(
        model=request.model,
        input_text=request.text,
        output_ratio=request.output_ratio,
    )
    return estimate


@router.get("/llm/all-models")
async def list_all_litellm_models() -> list[str]:
    """List all models available in LiteLLM (for debugging/discovery)."""
    return llm_service.get_all_litellm_models()


# ========== Legacy endpoints (for backwards compatibility) ==========


@router.get("/llm/config/providers")
async def list_config_providers():
    """[Legacy] List configured LLM providers and their models."""
    providers = llm_config.get_providers()
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "models": [m.model_dump() for m in p.models],
            "requires_api_key": True,
            "has_env_key": llm_config.get_api_key(p.name) is not None,
        }
        for p in providers
    ]


@router.get("/llm/config/providers/{provider_name}")
async def get_config_provider(provider_name: str):
    """[Legacy] Get a specific provider configuration."""
    provider = llm_config.get_provider(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
    return {
        "name": provider.name,
        "display_name": provider.display_name,
        "models": [m.model_dump() for m in provider.models],
        "base_url": provider.base_url,
        "has_env_key": llm_config.get_api_key(provider_name) is not None,
    }


@router.post("/llm/config/providers")
async def add_config_provider(request: AddProviderRequest):
    """[Legacy] Add or update a custom LLM provider."""
    provider = LLMProviderConfig(
        name=request.name,
        display_name=request.display_name,
        api_key_env_var=request.api_key_env_var,
        base_url=request.base_url,
        models=[LLMModelConfig(**m) for m in request.models],
    )
    llm_config.add_provider(provider)
    llm_config.save_config()
    return {"status": "added", "provider": request.name}


@router.delete("/llm/config/providers/{provider_name}")
async def remove_config_provider(provider_name: str):
    """[Legacy] Remove a custom LLM provider."""
    llm_config.remove_provider(provider_name)
    llm_config.save_config()
    return {"status": "removed", "provider": provider_name}


# ========== Database-backed LLM Configuration Endpoints ==========
# These endpoints store configurations in the database, allowing
# the backend to manage API keys securely.


class CreateLLMConfigRequest(BaseModel):
    """Request to create a new LLM configuration."""
    name: str  # User-friendly name
    provider: str  # openai, anthropic, gemini, etc.
    model: str  # gpt-4o-mini, claude-3-5-sonnet, etc.
    api_key: str  # API key for the provider
    base_url: Optional[str] = None  # Custom base URL (for Ollama, etc.)
    temperature: Optional[float] = 0.7  # LLM temperature (0.0-2.0)
    is_default: bool = False
    is_active: bool = False


class UpdateLLMConfigRequest(BaseModel):
    """Request to update an LLM configuration."""
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    """Response containing LLM configuration info."""
    id: str
    name: str
    provider: str
    model: str
    base_url: Optional[str]
    temperature: float
    is_default: bool
    is_active: bool
    has_api_key: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    last_used_at: Optional[str]


@router.get("/llm/configurations")
async def list_llm_configurations(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all stored LLM configurations.

    Returns configurations without exposing API keys.
    """
    return await LLMConfigService.list_configs(db, include_api_key=False)


@router.get("/llm/configurations/active")
async def get_active_llm_configuration(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the currently active LLM configuration.

    Returns the configuration that will be used for LLM operations
    when no specific config is specified.
    """
    try:
        config = await LLMConfigService.resolve_config(db)
        return {
            "id": config.config_id,
            "name": config.config_name,
            "provider": config.provider,
            "model": config.model,
            "has_api_key": bool(config.api_key),
            "source": "database" if config.config_id else "environment",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/llm/configurations/{config_id}")
async def get_llm_configuration(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a specific LLM configuration by ID."""
    configs = await LLMConfigService.list_configs(db, include_api_key=False)
    for config in configs:
        if config["id"] == config_id:
            return config
    raise HTTPException(status_code=404, detail=f"Configuration not found: {config_id}")


@router.post("/llm/configurations")
async def create_llm_configuration(
    request: CreateLLMConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new LLM configuration.

    The API key is stored securely in the database.
    """
    config_id = f"llm_{uuid.uuid4().hex[:12]}"

    config = await LLMConfigService.create_config(
        db,
        id=config_id,
        name=request.name,
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=request.temperature,
        is_default=request.is_default,
        is_active=request.is_active,
    )

    return config.to_dict(include_api_key=False)


@router.put("/llm/configurations/{config_id}")
async def update_llm_configuration(
    config_id: str,
    request: UpdateLLMConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an existing LLM configuration."""
    updates = request.model_dump(exclude_unset=True)

    config = await LLMConfigService.update_config(db, config_id, **updates)
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {config_id}")

    return config.to_dict(include_api_key=False)


@router.delete("/llm/configurations/{config_id}")
async def delete_llm_configuration(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete an LLM configuration."""
    success = await LLMConfigService.delete_config(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {config_id}")

    return {"status": "deleted", "id": config_id}


@router.post("/llm/configurations/{config_id}/activate")
async def activate_llm_configuration(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set a configuration as the active one."""
    success = await LLMConfigService.set_active(db, config_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {config_id}")

    return {"status": "activated", "id": config_id}


@router.post("/llm/configurations/{config_id}/test")
async def test_llm_configuration(
    config_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test an LLM configuration by making a simple API call."""
    try:
        config = await LLMConfigService.resolve_config(db, config_id=config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        is_success, message = await llm_service.test_connection(
            model=config.get_litellm_model(),
            api_key=config.api_key,
        )
        return {
            "success": is_success,
            "message": message,
            "config_id": config_id,
            "model": config.get_litellm_model(),
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "config_id": config_id,
        }


class DuplicateLLMConfigRequest(BaseModel):
    """Request to duplicate an LLM configuration."""
    new_name: str


@router.post("/llm/configurations/{config_id}/duplicate")
async def duplicate_llm_configuration(
    config_id: str,
    request: DuplicateLLMConfigRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Duplicate an existing LLM configuration including the API key.

    This is useful for creating a new config based on an existing one,
    e.g., to use a different model with the same API key.
    """
    new_id = f"llm_{uuid.uuid4().hex[:12]}"

    config = await LLMConfigService.duplicate_config(
        db,
        config_id=config_id,
        new_id=new_id,
        new_name=request.new_name,
    )

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration not found: {config_id}")

    return config.to_dict(include_api_key=False)

"""Shared LLM-related request schemas.

These base classes eliminate repetition of LLM configuration fields
across multiple API endpoints.
"""

from typing import Optional

from pydantic import BaseModel


class LLMConfigMixin(BaseModel):
    """Mixin for LLM configuration fields.

    Use this when an endpoint needs to accept LLM config either by:
    - Option 1: config_id (recommended) - uses stored configuration
    - Option 2: Direct parameters - provider/model/api_key
    """

    # Option 1: Use stored config (recommended)
    config_id: Optional[str] = None

    # Option 2: Direct parameters (for debugging/backwards compatibility)
    provider: Optional[str] = None  # "openai" | "anthropic" | "gemini" | "qwen"
    model: Optional[str] = None
    api_key: Optional[str] = None


class PromptOverrideMixin(BaseModel):
    """Mixin for custom prompt override fields.

    Use this when an endpoint allows custom system/user prompts.
    """

    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None


class LLMTaskRequest(LLMConfigMixin, PromptOverrideMixin):
    """Combined base for LLM task requests.

    Includes both LLM config and prompt override capabilities.
    Use this for endpoints that need full LLM task configuration.
    """

    pass


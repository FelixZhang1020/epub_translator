"""LiteLLM Service - Unified LLM interface with pricing and model info."""

import os
import re
from typing import Optional
from pydantic import BaseModel

import litellm
from litellm import acompletion
from litellm.utils import get_max_tokens


class ModelInfo(BaseModel):
    """Model information with pricing."""
    id: str
    provider: str
    display_name: str
    input_cost_per_million: float  # Cost per 1M input tokens in USD
    output_cost_per_million: float  # Cost per 1M output tokens in USD
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None


class ProviderInfo(BaseModel):
    """Provider information."""
    name: str
    display_name: str
    api_key_env_var: str
    has_api_key: bool = False
    model_count: int = 0
    manual_model: bool = False  # If true, user enters model name manually


class CostEstimate(BaseModel):
    """Translation cost estimate."""
    input_tokens: int
    output_tokens_estimate: int
    input_cost: float
    output_cost_estimate: float
    total_cost_estimate: float
    model: str


# Provider display names and env vars
# Only include the main providers for translation
PROVIDER_CONFIG = {
    "openai": {"display_name": "OpenAI", "env_var": "OPENAI_API_KEY"},
    "anthropic": {"display_name": "Claude (Anthropic)", "env_var": "ANTHROPIC_API_KEY"},
    "gemini": {"display_name": "Google Gemini", "env_var": "GEMINI_API_KEY"},
    "qwen": {"display_name": "Qwen (Alibaba)", "env_var": "DASHSCOPE_API_KEY"},
    "deepseek": {"display_name": "DeepSeek", "env_var": "DEEPSEEK_API_KEY"},
    "ollama": {"display_name": "Ollama (Local)", "env_var": "", "manual_model": True},
    "openrouter": {"display_name": "OpenRouter", "env_var": "OPENROUTER_API_KEY", "manual_model": True},
}

# Models to exclude (video, image, embedding, audio, etc.)
EXCLUDE_PATTERNS = [
    r"sora",
    r"veo",
    r"imagen",
    r"dall-e",
    r"whisper",
    r"tts",
    r"embed",
    r"moderation",
    r"container",
    r"realtime",
    r"audio",
    r"vision",  # exclude vision-only models
    r"-vl-",    # vision-language models
    r"vl-\d",   # vision-language models like vl-235b
    r"image-generation",  # image generation models
    r"search",
    r"learnlm",
    r"transcribe",  # audio transcription models
    r"diarize",     # speaker diarization models
    r"speech",      # speech models
    r":0$",  # exclude versioned duplicates like model:0
    r"v1:0$",
    # Exclude old Claude models (keep only 4.5 series)
    r"claude-3-",   # Exclude all Claude 3.x models
    r"claude-3\.",  # Exclude Claude 3.x with dot notation
    # Exclude Claude 4.x (not 4.5) - multiple formats
    r"claude-sonnet-4-(?!5)",  # claude-sonnet-4-20250514
    r"claude-opus-4-(?!5)",    # claude-opus-4-20250514
    r"claude-haiku-4-(?!5)",   # claude-haiku-4-20241022
    r"claude-sonnet-4@",       # claude-sonnet-4@20250514 (with @ separator)
    r"claude-opus-4@",         # claude-opus-4@20250514 (with @ separator)
    r"claude-haiku-4@",        # claude-haiku-4@20250514 (with @ separator)
    r"claude-4-sonnet",        # claude-4-sonnet
    r"claude-4-opus",          # claude-4-opus
    r"claude-4-haiku",         # claude-4-haiku
    r"claude-sonnet-4$",       # claude-sonnet-4 (exact match, no date)
    r"claude-opus-4$",         # claude-opus-4 (exact match, no date)
    r"claude-haiku-4$",        # claude-haiku-4 (exact match, no date)
]

# Priority keywords for sorting (higher = more preferred)
# Based on popularity and common usage
PRIORITY_KEYWORDS = [
    # Most popular/flagship models
    ("gpt-4o", 200),
    ("gpt-4", 180),
    ("claude-opus-4-5", 195),
    ("claude-sonnet-4-5", 190),
    ("claude-haiku-4-5", 185),
    ("gemini-3-pro", 190),
    ("gemini-3-flash", 180),
    ("gemini-2.5-pro", 185),
    ("gemini-2.5-flash", 175),
    ("deepseek-chat", 160),
    ("deepseek-v3", 170),
    ("qwen-max", 160),
    ("qwen-plus", 150),
    # Model tier keywords
    ("sonnet", 100),
    ("opus", 90),
    ("haiku", 80),
    ("pro", 70),
    ("max", 70),
    ("plus", 60),
    ("chat", 50),
    ("turbo", 40),
    ("mini", 30),
    ("flash", 30),
]

# Cost-effectiveness tiers (input cost per 1K tokens thresholds)
# Lower cost = higher bonus
COST_EFFECTIVENESS_TIERS = [
    (0.001, 100),   # Very cheap: < $0.001/1K tokens
    (0.005, 80),    # Cheap: < $0.005/1K tokens
    (0.01, 60),     # Moderate: < $0.01/1K tokens
    (0.05, 40),     # Expensive: < $0.05/1K tokens
    (0.1, 20),      # Very expensive: < $0.1/1K tokens
]

# Curated OpenAI model list - best models for translation tasks
# Format: (model_id, display_name)
# These are manually selected for translation quality and cost-effectiveness
OPENAI_RECOMMENDED_MODELS = [
    # GPT-5 series
    ("gpt-5.2", "GPT-5.2"),
    ("gpt-5-mini", "GPT-5 Mini"),
    ("gpt-5-nano", "GPT-5 Nano"),
]

# Curated DeepSeek model list - official API models only
# DeepSeek API uses these model names, which map to latest versions:
# - deepseek-chat: DeepSeek-V3.2 (non-thinking mode)
# - deepseek-reasoner: DeepSeek-R1 / V3.2 (thinking mode)
DEEPSEEK_RECOMMENDED_MODELS = [
    ("deepseek-chat", "DeepSeek Chat (V3.2)"),       # Latest V3.2, best for translation
    ("deepseek-reasoner", "DeepSeek Reasoner (R1)"), # Reasoning model, thinking mode
]

# Curated Qwen model list - DashScope API models only
# These are the official Alibaba DashScope API model names
QWEN_RECOMMENDED_MODELS = [
    ("qwen-max", "Qwen Max"),           # Most capable, best quality
    ("qwen-plus", "Qwen Plus"),         # Good balance of quality and cost
    ("qwq-plus", "QwQ Plus"),           # Reasoning model
    ("qwen-turbo", "Qwen Turbo"),       # Fast and cheap
    ("qwen-coder", "Qwen Coder"),       # Code-focused model
]


class LLMService:
    """Unified LLM service using LiteLLM."""

    def __init__(self):
        # Auto-drop unsupported parameters for cross-provider compatibility
        litellm.drop_params = True
        # Set default timeout
        litellm.request_timeout = 120
        # Cache for model list
        self._model_cache: Optional[dict[str, list[ModelInfo]]] = None

    def _get_provider_from_model(self, model: str) -> str:
        """Extract provider name from model ID."""
        model_lower = model.lower()

        # Handle prefixed models (provider/model-name)
        if "/" in model:
            provider = model.split("/")[0]
            model_name = model.split("/")[-1]

            # vertex_ai hosts multiple providers - detect actual model
            if provider == "vertex_ai":
                model_name_lower = model_name.lower()
                if "claude" in model_name_lower:
                    return "anthropic"  # Claude on Vertex AI
                elif "gemini" in model_name_lower:
                    return "gemini"
                elif "deepseek" in model_name_lower:
                    return "deepseek"  # DeepSeek on Vertex AI
                elif "llama" in model_name_lower:
                    return "meta"  # Llama on Vertex AI
                elif "mistral" in model_name_lower:
                    return "mistral"  # Mistral on Vertex AI
                return "vertex_ai"  # Other vertex models (don't assume gemini)

            # Normalize provider names
            if provider == "dashscope":
                return "qwen"  # DashScope is Alibaba's Qwen API
            if provider == "ollama" or provider == "ollama_chat":
                return "ollama"
            if provider == "openrouter":
                return "openrouter"

            return provider

        # Non-prefixed models
        if model_lower.startswith(("gpt-", "o1-", "o3-", "o4-")):
            return "openai"
        if model_lower.startswith("claude"):
            return "anthropic"
        if model_lower.startswith("gemini"):
            return "gemini"
        if model_lower.startswith(("qwen", "qwq")):
            return "qwen"
        if model_lower.startswith("deepseek"):
            return "deepseek"
        return "other"

    def _format_model_name(self, model_id: str) -> str:
        """Format model ID to display name."""
        # Remove provider prefix if present
        name = model_id.split("/")[-1] if "/" in model_id else model_id

        # Handle date suffix FIRST - format as (YYYY-MM-DD)
        # Must do this before version conversion to avoid mangling date
        date_suffix = ""

        # Match dash-separated date format like "2025-12-11" at end
        date_match = re.search(r'-(\d{4})-(\d{2})-(\d{2})$', name)
        if date_match:
            year, month, day = date_match.groups()
            date_suffix = f" ({year}-{month}-{day})"
            name = name[:date_match.start()]  # Remove date portion
        else:
            # Match compact date format with dash like "-20250514" at end
            date_match2 = re.search(r'-(\d{4})(\d{2})(\d{2})$', name)
            if date_match2:
                year, month, day = date_match2.groups()
                date_suffix = f" ({year}-{month}-{day})"
                name = name[:date_match2.start()]  # Remove date portion
            else:
                # Match compact date format with @ like "@20250514" at end (vertex models)
                date_match3 = re.search(r'@(\d{4})(\d{2})(\d{2})$', name)
                if date_match3:
                    year, month, day = date_match3.groups()
                    date_suffix = f" ({year}-{month}-{day})"
                    name = name[:date_match3.start()]  # Remove date portion

        # Now convert version patterns like "4-5" to "4.5"
        # This is safe since we already removed the date
        # But be careful not to match single digit followed by long number (date remnants)
        name = re.sub(r'(\d)-(\d)(?!\d{6,})', r'\1.\2', name)

        # Replace dots in provider-style names (e.g., "qwen.qwen3" -> "qwen3")
        if name.startswith("qwen."):
            name = name.replace("qwen.", "")

        # Replace remaining dashes and underscores with spaces
        name = name.replace("-", " ").replace("_", " ")

        # Capitalize each word, but keep version numbers and model specs
        parts = name.split()
        formatted_parts = []
        for p in parts:
            # Don't capitalize if it's a version number like "4.5" or spec like "80b"
            if re.match(r'^[\d.]+$', p) or re.match(r'^\d+[bBkKmM]$', p):
                formatted_parts.append(p.upper() if re.match(r'^\d+[bBkKmM]$', p) else p)
            else:
                formatted_parts.append(p.capitalize())

        return " ".join(formatted_parts) + date_suffix

    def _should_exclude_model(self, model_id: str) -> bool:
        """Check if model should be excluded."""
        model_lower = model_id.lower()
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, model_lower):
                return True
        return False

    def _get_model_priority(self, model_id: str, input_cost_per_1k: float = 0) -> int:
        """Get model priority for sorting (higher = more preferred).

        Prioritizes popular models and cost-effectiveness.
        """
        model_lower = model_id.lower()
        priority = 0

        # Add priority based on popularity keywords
        for keyword, score in PRIORITY_KEYWORDS:
            if keyword in model_lower:
                priority += score

        # Add cost-effectiveness bonus
        for threshold, bonus in COST_EFFECTIVENESS_TIERS:
            if input_cost_per_1k < threshold:
                priority += bonus
                break

        # Small bonus for models with version dates (usually more stable)
        if re.search(r"-\d{8}", model_id):
            priority += 5
        elif re.search(r"-v\d+", model_id):
            priority += 3

        return priority

    def _get_openai_curated_models(self) -> list[ModelInfo]:
        """Get curated list of OpenAI models with pricing from LiteLLM."""
        model_cost_data = litellm.model_cost
        models = []

        for model_id, display_name in OPENAI_RECOMMENDED_MODELS:
            # Get pricing from LiteLLM
            cost_info = model_cost_data.get(model_id, {})

            # Skip if model not found in LiteLLM's model_cost
            if not cost_info:
                continue

            input_cost = cost_info.get("input_cost_per_token", 0)
            output_cost = cost_info.get("output_cost_per_token", 0)
            max_tokens = cost_info.get("max_tokens")
            context_window = cost_info.get("max_input_tokens")

            if not max_tokens:
                try:
                    max_tokens = get_max_tokens(model_id)
                except Exception:
                    pass

            # Convert from per-token to per-million tokens
            input_cost_per_million = input_cost * 1_000_000
            output_cost_per_million = output_cost * 1_000_000

            models.append(ModelInfo(
                id=model_id,
                provider="openai",
                display_name=display_name,
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
                max_tokens=max_tokens,
                context_window=context_window,
            ))

        return models

    def _get_deepseek_curated_models(self) -> list[ModelInfo]:
        """Get curated list of DeepSeek models with pricing from LiteLLM."""
        model_cost_data = litellm.model_cost
        models = []

        for model_id, display_name in DEEPSEEK_RECOMMENDED_MODELS:
            # Get pricing from LiteLLM
            cost_info = model_cost_data.get(model_id, {})

            # Skip if model not found in LiteLLM's model_cost
            if not cost_info:
                continue

            input_cost = cost_info.get("input_cost_per_token", 0)
            output_cost = cost_info.get("output_cost_per_token", 0)
            max_tokens = cost_info.get("max_tokens")
            context_window = cost_info.get("max_input_tokens")

            if not max_tokens:
                try:
                    max_tokens = get_max_tokens(model_id)
                except Exception:
                    pass

            # Convert from per-token to per-million tokens
            input_cost_per_million = input_cost * 1_000_000
            output_cost_per_million = output_cost * 1_000_000

            models.append(ModelInfo(
                id=model_id,
                provider="deepseek",
                display_name=display_name,
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
                max_tokens=max_tokens,
                context_window=context_window,
            ))

        return models

    def _get_qwen_curated_models(self) -> list[ModelInfo]:
        """Get curated list of Qwen models with pricing from LiteLLM."""
        model_cost_data = litellm.model_cost
        models = []

        for model_id, display_name in QWEN_RECOMMENDED_MODELS:
            # DashScope models have dashscope/ prefix in LiteLLM
            litellm_model_id = f"dashscope/{model_id}"
            cost_info = model_cost_data.get(litellm_model_id, {})

            # Skip if model not found in LiteLLM's model_cost
            if not cost_info:
                continue

            input_cost = cost_info.get("input_cost_per_token", 0)
            output_cost = cost_info.get("output_cost_per_token", 0)
            max_tokens = cost_info.get("max_tokens")
            context_window = cost_info.get("max_input_tokens")

            if not max_tokens:
                try:
                    max_tokens = get_max_tokens(litellm_model_id)
                except Exception:
                    pass

            # Convert from per-token to per-million tokens
            input_cost_per_million = input_cost * 1_000_000
            output_cost_per_million = output_cost * 1_000_000

            # Use the clean model name (without dashscope/ prefix) as ID
            # since we handle the prefix in the translate methods
            models.append(ModelInfo(
                id=model_id,
                provider="qwen",
                display_name=display_name,
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
                max_tokens=max_tokens,
                context_window=context_window,
            ))

        return models

    def _get_models_for_provider(self, provider: str, limit: int = 7) -> list[ModelInfo]:
        """Get top N models for a provider from LiteLLM.

        Prioritizes popular and cost-effective models.
        For OpenAI and DeepSeek, uses curated lists of recommended models.
        """
        model_cost_data = litellm.model_cost

        # Use curated list for OpenAI
        if provider == "openai":
            return self._get_openai_curated_models()

        # Use curated list for DeepSeek (official API only)
        if provider == "deepseek":
            return self._get_deepseek_curated_models()

        # Use curated list for Qwen (DashScope API only)
        if provider == "qwen":
            return self._get_qwen_curated_models()

        models = []

        for model_id, cost_info in model_cost_data.items():
            # Get provider for this model
            model_provider = self._get_provider_from_model(model_id)
            if model_provider != provider:
                continue

            # Skip excluded models
            if self._should_exclude_model(model_id):
                continue

            # Skip models with zero cost (usually not text models)
            input_cost = cost_info.get("input_cost_per_token", 0)
            output_cost = cost_info.get("output_cost_per_token", 0)
            if input_cost == 0 and output_cost == 0:
                continue

            # Get max tokens
            max_tokens = cost_info.get("max_tokens")
            context_window = cost_info.get("max_input_tokens")

            if not max_tokens:
                try:
                    max_tokens = get_max_tokens(model_id)
                except Exception:
                    pass

            # Convert from per-token to per-million tokens
            input_cost_per_million = input_cost * 1_000_000
            output_cost_per_million = output_cost * 1_000_000
            models.append(ModelInfo(
                id=model_id,
                provider=model_provider,
                display_name=self._format_model_name(model_id),
                input_cost_per_million=input_cost_per_million,
                output_cost_per_million=output_cost_per_million,
                max_tokens=max_tokens,
                context_window=context_window,
            ))

        # Sort by priority (popularity + cost-effectiveness, highest first)
        models.sort(key=lambda m: self._get_model_priority(m.id, m.input_cost_per_million / 1000), reverse=True)

        # Remove duplicates (keep highest priority version)
        seen_base_names = set()
        unique_models = []
        for model in models:
            # Get base name without date/version suffixes
            base_name = model.id
            # Remove provider prefix first
            base_name = base_name.split("/")[-1] if "/" in base_name else base_name
            # Remove @ patterns and everything after (vertex models)
            base_name = re.sub(r"@.*$", "", base_name)
            # Remove compact date suffix like -20240620
            base_name = re.sub(r"-\d{8}$", "", base_name)
            # Remove dash-separated date like -2024-07-18
            base_name = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", base_name)
            # Remove short date patterns like -0215, -0409 (month-day)
            base_name = re.sub(r"-\d{4}$", "", base_name)
            # Remove hyphen-separated date patterns like -02-05, -03-25
            base_name = re.sub(r"-\d{2}-\d{2}$", "", base_name)
            # Remove version suffix like -v2 or -001, -002
            base_name = re.sub(r"-v?\d{1,3}$", "", base_name)
            # Remove -latest, -preview, -exp suffixes
            base_name = re.sub(r"-(latest|preview|exp)$", "", base_name)

            if base_name not in seen_base_names:
                seen_base_names.add(base_name)
                unique_models.append(model)

        return unique_models[:limit]

    def get_providers(self) -> list[ProviderInfo]:
        """Get list of supported providers with their configuration status."""
        providers = []

        for name, config in PROVIDER_CONFIG.items():
            env_var = config["env_var"]
            has_key = bool(os.environ.get(env_var)) if env_var else True
            manual_model = config.get("manual_model", False)

            # For manual_model providers, don't count models
            if manual_model:
                model_count = 0
            else:
                models = self._get_models_for_provider(name, limit=7)
                model_count = len(models)

            providers.append(ProviderInfo(
                name=name,
                display_name=config["display_name"],
                api_key_env_var=env_var,
                has_api_key=has_key,
                model_count=model_count,
                manual_model=manual_model,
            ))

        # Keep original order from PROVIDER_CONFIG (don't sort)
        # This preserves: OpenAI, Anthropic, Gemini, Qwen, DeepSeek, Ollama, OpenRouter

        return providers

    def get_models(self, provider: Optional[str] = None, limit: int = 7) -> list[ModelInfo]:
        """Get available models with pricing info.

        Args:
            provider: Optional provider name to filter by
            limit: Max models per provider (default 5)

        Returns:
            List of ModelInfo with pricing
        """
        if provider:
            return self._get_models_for_provider(provider, limit=limit)

        # Get models for all configured providers
        all_models = []
        for prov_name in PROVIDER_CONFIG.keys():
            models = self._get_models_for_provider(prov_name, limit=limit)
            all_models.extend(models)

        return all_models

    def get_all_litellm_models(self) -> list[str]:
        """Get all models from LiteLLM's model_cost."""
        return list(litellm.model_cost.keys())

    def estimate_cost(
        self,
        model: str,
        input_text: str,
        output_ratio: float = 1.5,
    ) -> CostEstimate:
        """Estimate translation cost.

        Args:
            model: LiteLLM model ID
            input_text: Text to be translated
            output_ratio: Expected output/input token ratio (Chinese typically 1.5x English)

        Returns:
            CostEstimate with token counts and costs
        """
        # Get model pricing
        cost_info = litellm.model_cost.get(model, {})
        if not cost_info:
            # Try without provider prefix
            simple_id = model.split("/")[-1] if "/" in model else model
            cost_info = litellm.model_cost.get(simple_id, {})

        input_cost_per_token = cost_info.get("input_cost_per_token", 0)
        output_cost_per_token = cost_info.get("output_cost_per_token", 0)

        # Estimate token count (rough: 4 chars per token for English)
        input_tokens = len(input_text) // 4
        output_tokens_estimate = int(input_tokens * output_ratio)

        input_cost = input_tokens * input_cost_per_token
        output_cost_estimate = output_tokens_estimate * output_cost_per_token

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens_estimate=output_tokens_estimate,
            input_cost=input_cost,
            output_cost_estimate=output_cost_estimate,
            total_cost_estimate=input_cost + output_cost_estimate,
            model=model,
        )

    async def test_connection(
        self,
        model: str,
        api_key: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Test if a model is accessible.

        Args:
            model: LiteLLM model ID
            api_key: Optional API key override

        Returns:
            Tuple of (success, message)
        """
        try:
            kwargs = {}
            actual_model = model

            if api_key:
                provider = self._get_provider_from_model(model)
                if provider == "openai":
                    kwargs["api_key"] = api_key
                    # Ensure openai/ prefix for proper routing
                    if not model.startswith("openai/"):
                        actual_model = f"openai/{model}"
                elif provider == "anthropic":
                    kwargs["api_key"] = api_key
                elif provider == "gemini":
                    kwargs["api_key"] = api_key
                    # Ensure gemini/ prefix for API key auth (not vertex_ai)
                    if not model.startswith("gemini/"):
                        actual_model = f"gemini/{model}"
                elif provider == "deepseek":
                    kwargs["api_key"] = api_key
                    # Ensure deepseek/ prefix for proper routing
                    if not model.startswith("deepseek/"):
                        actual_model = f"deepseek/{model}"
                elif provider == "qwen":
                    # Qwen uses DashScope - ensure dashscope/ prefix
                    kwargs["api_key"] = api_key
                    if not model.startswith("dashscope/"):
                        actual_model = f"dashscope/{model}"

            # Enforce: API key must be provided, never use env vars
            if "api_key" not in kwargs:
                return False, "API key must be provided. Environment variables are not allowed."

            response = await acompletion(
                model=actual_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
                **kwargs,
            )
            if response.choices:
                return True, "Connection successful"
            return False, "No response from model"
        except Exception as e:
            error_msg = str(e)
            # Extract meaningful error message
            if "AuthenticationError" in error_msg or "401" in error_msg:
                return False, "Invalid API key"
            elif "NotFoundError" in error_msg or "404" in error_msg:
                return False, f"Model '{model}' not found"
            elif "RateLimitError" in error_msg or "429" in error_msg:
                return False, "Rate limit exceeded, try again later"
            elif "timeout" in error_msg.lower():
                return False, "Connection timeout"
            elif "Connection" in error_msg:
                return False, "Connection error - check network"
            else:
                # Return a cleaned up error message
                return False, error_msg[:100] if len(error_msg) > 100 else error_msg


# Global service instance
llm_service = LLMService()

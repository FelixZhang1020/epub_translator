"""LLM Configuration Module - Centralized LLM provider configuration."""

from pathlib import Path
from typing import Optional
import json

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMModelConfig(BaseModel):
    """Configuration for a single LLM model."""
    id: str
    name: str
    context_window: int = 128000
    max_output_tokens: int = 4096
    supports_streaming: bool = True


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    name: str
    display_name: str
    api_key_env_var: str  # Environment variable name for API key
    base_url: Optional[str] = None
    models: list[LLMModelConfig] = Field(default_factory=list)
    enabled: bool = True


class LLMSettings(BaseSettings):
    """LLM settings loaded from environment or config file."""

    # API Keys - loaded from environment variables
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    dashscope_api_key: Optional[str] = Field(default=None, alias="DASHSCOPE_API_KEY")

    # Config file path
    llm_config_file: Path = Path("./llm_config.json")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "qwen": self.dashscope_api_key,
        }
        return key_map.get(provider)


# Default provider configurations
DEFAULT_PROVIDERS: list[LLMProviderConfig] = [
    LLMProviderConfig(
        name="openai",
        display_name="OpenAI",
        api_key_env_var="OPENAI_API_KEY",
        models=[
            LLMModelConfig(id="gpt-5.2", name="GPT-5.2", context_window=128000),
            LLMModelConfig(id="gpt-5-mini", name="GPT-5 Mini", context_window=128000),
            LLMModelConfig(id="gpt-5-nano", name="GPT-5 Nano", context_window=128000),
            LLMModelConfig(id="gpt-4o-mini", name="GPT-4o Mini", context_window=128000),
        ],
    ),
    LLMProviderConfig(
        name="anthropic",
        display_name="Claude (Anthropic)",
        api_key_env_var="ANTHROPIC_API_KEY",
        models=[
            LLMModelConfig(id="claude-sonnet-4-20250514", name="Claude Sonnet 4", context_window=200000),
            LLMModelConfig(id="claude-3-5-sonnet-20241022", name="Claude 3.5 Sonnet", context_window=200000),
            LLMModelConfig(id="claude-3-5-haiku-20241022", name="Claude 3.5 Haiku", context_window=200000),
        ],
    ),
    LLMProviderConfig(
        name="gemini",
        display_name="Google Gemini",
        api_key_env_var="GEMINI_API_KEY",
        models=[
            LLMModelConfig(id="gemini-3-pro-preview", name="Gemini 3 Pro (Preview)", context_window=1000000),
            LLMModelConfig(id="gemini-3-flash-preview", name="Gemini 3 Flash (Preview)", context_window=1000000),
            LLMModelConfig(id="gemini-2.5-pro", name="Gemini 2.5 Pro", context_window=1000000),
            LLMModelConfig(id="gemini-2.5-flash", name="Gemini 2.5 Flash", context_window=1000000),
        ],
    ),
    LLMProviderConfig(
        name="qwen",
        display_name="Qwen (Alibaba)",
        api_key_env_var="DASHSCOPE_API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=[
            LLMModelConfig(id="qwen-max", name="Qwen Max", context_window=32000),
            LLMModelConfig(id="qwen-plus", name="Qwen Plus", context_window=32000),
            LLMModelConfig(id="qwen-turbo", name="Qwen Turbo", context_window=32000),
        ],
    ),
]


class LLMConfigManager:
    """Manager for LLM configurations."""

    def __init__(self, config_file: Optional[Path] = None):
        self.settings = LLMSettings()
        self.config_file = config_file or self.settings.llm_config_file
        self._providers: list[LLMProviderConfig] = []
        self._load_config()

    def _load_config(self):
        """Load configuration from file or use defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._providers = [LLMProviderConfig(**p) for p in data.get("providers", [])]
            except Exception:
                self._providers = DEFAULT_PROVIDERS.copy()
        else:
            self._providers = DEFAULT_PROVIDERS.copy()

    def save_config(self):
        """Save current configuration to file."""
        data = {
            "providers": [p.model_dump() for p in self._providers]
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_providers(self) -> list[LLMProviderConfig]:
        """Get all configured providers."""
        return [p for p in self._providers if p.enabled]

    def get_provider(self, name: str) -> Optional[LLMProviderConfig]:
        """Get a specific provider by name."""
        for p in self._providers:
            if p.name == name:
                return p
        return None

    def add_provider(self, provider: LLMProviderConfig):
        """Add or update a provider."""
        for i, p in enumerate(self._providers):
            if p.name == provider.name:
                self._providers[i] = provider
                return
        self._providers.append(provider)

    def remove_provider(self, name: str):
        """Remove a provider."""
        self._providers = [p for p in self._providers if p.name != name]

    def get_api_key(self, provider: str, override_key: Optional[str] = None) -> Optional[str]:
        """Get API key for a provider, with optional override."""
        if override_key:
            return override_key
        return self.settings.get_api_key(provider)


# Global instance
llm_config = LLMConfigManager()

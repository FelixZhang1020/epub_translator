"""Abstract LLM Adapter interface."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel

from app.core.prompts.loader import PromptLoader


class TranslationRequest(BaseModel):
    """Translation request payload."""
    source_text: str
    source_language: str = "en"
    target_language: str = "zh"
    mode: str  # "author_based" or "optimization"
    author_background: Optional[str] = None
    custom_prompts: Optional[list[str]] = None
    existing_translation: Optional[str] = None  # For optimization mode
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None
    analysis_text: Optional[str] = None  # Raw analysis output text from analysis step
    # Variable context from VariableService (includes project, derived, user variables)
    variable_context: Optional[dict[str, Any]] = None
    # Paragraph context for coherent translation
    paragraph_index: Optional[int] = None
    chapter_index: Optional[int] = None
    previous_original: Optional[str] = None
    previous_translation: Optional[str] = None


class TranslationResponse(BaseModel):
    """Translation response."""
    translated_text: str
    tokens_used: int
    model: str
    provider: str


class LLMAdapter(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, api_key: str, **kwargs):
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Perform translation."""
        pass

    @abstractmethod
    async def translate_stream(
        self,
        request: TranslationRequest,
    ) -> AsyncIterator[str]:
        """Stream translation for real-time display."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        pass

    def build_system_prompt(self, request: TranslationRequest) -> str:
        """Build system prompt based on translation mode.

        Uses PromptLoader to load and render the translation prompt template
        with full variable context including project, derived, and user variables.
        """
        # Use custom system prompt if provided (but still render variables)
        if request.custom_system_prompt:
            variables = self._build_variables(request)
            return PromptLoader.render(request.custom_system_prompt, variables)

        # Select template based on mode
        if request.mode == "optimization":
            template = PromptLoader.load_template("optimization")
        else:
            # Default to translation template for author_based and other modes
            template = PromptLoader.load_template("translation")

        # Build complete variables for rendering
        variables = self._build_variables(request)

        return PromptLoader.render(template.system_prompt, variables)

    def build_user_prompt(self, request: TranslationRequest) -> str:
        """Build user prompt with the text to translate.

        Uses PromptLoader to load and render the user prompt template
        with full variable context.
        """
        # Use custom user prompt if provided (but still render variables)
        if request.custom_user_prompt:
            variables = self._build_variables(request)
            return PromptLoader.render(request.custom_user_prompt, variables)

        # Select template based on mode
        if request.mode == "optimization":
            template = PromptLoader.load_template("optimization")
        else:
            template = PromptLoader.load_template("translation")

        # Build complete variables for rendering
        variables = self._build_variables(request)

        return PromptLoader.render(template.user_prompt_template, variables)

    def _build_variables(self, request: TranslationRequest) -> dict[str, Any]:
        """Build complete variable context for prompt rendering.

        Merges:
        1. Variable context from VariableService (project, derived, user variables)
        2. Request-specific variables (source_text, existing_translation, etc.)
        3. Legacy variables (author_background, custom_prompts) for backwards compatibility
        """
        # Start with variable context from VariableService if available
        variables = {}
        if request.variable_context:
            variables.update(request.variable_context)

        # Add/override with request-specific content variables
        variables["content.source_text"] = request.source_text
        variables["source_text"] = request.source_text  # Also flat for backwards compat

        if request.existing_translation:
            variables["pipeline.existing_translation"] = request.existing_translation
            variables["existing_translation"] = request.existing_translation

        if request.previous_original:
            variables["pipeline.previous_original"] = request.previous_original
            variables["previous_original"] = request.previous_original

        if request.previous_translation:
            variables["pipeline.previous_translation"] = request.previous_translation
            variables["previous_translation"] = request.previous_translation

        if request.paragraph_index is not None:
            variables["content.paragraph_index"] = request.paragraph_index

        if request.chapter_index is not None:
            variables["content.chapter_index"] = request.chapter_index

        # Legacy variables for backwards compatibility
        if request.author_background:
            variables["author_background"] = request.author_background

        if request.custom_prompts:
            variables["custom_prompts"] = request.custom_prompts

        if request.analysis_text:
            variables["analysis_text"] = request.analysis_text

        return variables

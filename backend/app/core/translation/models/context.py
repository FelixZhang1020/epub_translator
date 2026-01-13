"""Translation context models.

This module defines the input data structures for the translation pipeline,
providing a unified context model that encapsulates all translation parameters.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TranslationMode(str, Enum):
    """Supported translation modes."""

    DIRECT = "direct"  # Simple direct translation
    AUTHOR_AWARE = "author_aware"  # Style-preserving with author context
    OPTIMIZATION = "optimization"  # Improve existing translation


class SourceMaterial(BaseModel):
    """Content to be translated with metadata."""

    text: str = Field(..., description="The source text to translate")
    language: str = Field(default="en", description="Source language code")
    word_count: int = Field(default=0, description="Word count of source text")
    paragraph_index: Optional[int] = Field(
        default=None, description="Paragraph number within chapter"
    )
    chapter_index: Optional[int] = Field(
        default=None, description="Chapter number within book"
    )

    def model_post_init(self, __context: Any) -> None:
        """Calculate word count if not provided."""
        if not self.word_count and self.text:
            self.word_count = len(self.text.split())


class ExistingTranslation(BaseModel):
    """Previous translation for optimization mode."""

    text: str = Field(..., description="The existing translated text")
    provider: Optional[str] = Field(default=None, description="LLM provider used")
    model: Optional[str] = Field(default=None, description="Model used")
    version: int = Field(default=1, description="Translation version number")
    quality_score: Optional[float] = Field(
        default=None, description="Quality score if available"
    )


class TranslationPrinciples(BaseModel):
    """Translation principles from book analysis."""

    priority_order: List[str] = Field(
        default_factory=lambda: ["faithfulness", "expressiveness", "elegance"],
        description="Priority order for translation principles",
    )
    faithfulness_boundary: Optional[str] = Field(
        default=None,
        description="Content that must be translated with high fidelity",
    )
    permissible_adaptation: Optional[str] = Field(
        default=None,
        description="Allowed adaptations for readability",
    )
    style_constraints: Optional[str] = Field(
        default=None,
        description="Style requirements and restrictions",
    )
    red_lines: Optional[str] = Field(
        default=None,
        description="Behaviors to avoid during translation",
    )


class BookAnalysisContext(BaseModel):
    """Structured book analysis data for context-aware translation."""

    author_name: Optional[str] = Field(default=None, description="Author's name")
    author_biography: Optional[str] = Field(
        default=None, description="Author background and context"
    )
    writing_style: Optional[str] = Field(
        default=None, description="Author's writing style description"
    )
    tone: Optional[str] = Field(default=None, description="Overall tone of the work")
    genre: Optional[str] = Field(default=None, description="Book genre")
    target_audience: Optional[str] = Field(
        default=None, description="Intended audience"
    )
    genre_conventions: Optional[str] = Field(
        default=None, description="Genre-specific conventions"
    )
    key_terminology: Dict[str, str] = Field(
        default_factory=dict,
        description="Term -> translation mapping for consistency",
    )
    translation_principles: Optional[TranslationPrinciples] = Field(
        default=None, description="Translation principles and guidelines"
    )
    custom_guidelines: List[str] = Field(
        default_factory=list,
        description="Additional custom translation guidelines",
    )

    @classmethod
    def from_raw_analysis(cls, raw: Dict[str, Any]) -> "BookAnalysisContext":
        """Factory method to create from raw analysis JSON.

        Args:
            raw: Raw analysis dictionary from BookAnalysis.raw_analysis

        Returns:
            Structured BookAnalysisContext instance
        """
        import json

        def to_string(value: Any) -> Optional[str]:
            """Convert value to string, handling dicts and other types."""
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                # Convert dict to formatted JSON string
                return json.dumps(value, ensure_ascii=False, indent=2)
            return str(value)


        # Placeholder values that should be filtered out
        INVALID_PLACEHOLDERS = {"undefined", "null", "n/a", "none", "tbd", ""}

        def is_valid_translation(value: Any) -> bool:
            """Check if a translation value is valid (not a placeholder)."""
            if value is None:
                return False
            if not isinstance(value, str):
                return bool(value)
            return value.strip().lower() not in INVALID_PLACEHOLDERS

        def to_terminology_dict(value: Any) -> Dict[str, str]:
            """Convert terminology to dict format, filtering out invalid translations."""
            if value is None:
                return {}
            if isinstance(value, dict):
                # Filter out invalid translations from existing dict
                return {k: v for k, v in value.items() if is_valid_translation(v)}
            if isinstance(value, list):
                # Convert list of term dicts to simple dict
                result = {}
                for item in value:
                    if isinstance(item, dict):
                        # Handle format: {"english_term": "X", "chinese_translation": "Y"}
                        # Support multiple field name conventions from different analysis prompts
                        en = item.get("english_term") or item.get("english") or item.get("term")
                        zh = item.get("chinese_translation") or item.get("recommended_chinese") or item.get("chinese") or item.get("translation")
                        if en and is_valid_translation(zh):
                            result[en] = zh
                return result
            return {}

        def to_guidelines_list(value: Any) -> List[str]:
            """Convert guidelines to list format."""
            if value is None:
                return []
            if isinstance(value, list):
                return [str(item) if not isinstance(item, str) else item for item in value]
            if isinstance(value, str):
                return [value]
            return []

        # Extract translation principles if present
        principles = None
        tp = raw.get("translation_principles")
        if tp:
            if isinstance(tp, dict):
                principles = TranslationPrinciples(
                    priority_order=tp.get("priority_order", ["faithfulness", "expressiveness", "elegance"]),
                    faithfulness_boundary=to_string(tp.get("faithfulness_boundary") or tp.get("must_be_literal")),
                    permissible_adaptation=to_string(tp.get("permissible_adaptation") or tp.get("allowed_adjustment")),
                    style_constraints=to_string(tp.get("style_constraints")),
                    red_lines=to_string(tp.get("red_lines")),
                )

        # Extract work_profile fields if present
        work_profile = raw.get("work_profile", {})

        return cls(
            author_name=to_string(raw.get("author_name") or raw.get("meta", {}).get("author")),
            author_biography=to_string(raw.get("author_biography")),
            writing_style=to_string(raw.get("writing_style") or work_profile.get("writing_style")),
            tone=to_string(raw.get("tone") or work_profile.get("tone")),
            genre=to_string(raw.get("genre") or work_profile.get("genre")),
            target_audience=to_string(raw.get("target_audience") or work_profile.get("target_audience")),
            genre_conventions=to_string(raw.get("genre_conventions")),
            key_terminology=to_terminology_dict(raw.get("key_terminology")),
            translation_principles=principles,
            custom_guidelines=to_guidelines_list(raw.get("custom_guidelines") or raw.get("custom_watchlist")),
        )

    def has_content(self) -> bool:
        """Check if any meaningful content exists."""
        return bool(
            self.author_biography
            or self.writing_style
            or self.tone
            or self.key_terminology
            or self.translation_principles
        )


class AdjacentContext(BaseModel):
    """Surrounding paragraphs for translation coherence."""

    previous_original: Optional[str] = Field(
        default=None, description="Previous paragraph in source language"
    )
    previous_translation: Optional[str] = Field(
        default=None, description="Translation of previous paragraph"
    )
    next_original: Optional[str] = Field(
        default=None, description="Next paragraph in source language (for context)"
    )


class TranslationContext(BaseModel):
    """Complete context for a single translation request.

    This is the PRIMARY input contract for the translation pipeline.
    All necessary information for translation is encapsulated here.
    """

    # Core content
    source: SourceMaterial = Field(..., description="Source material to translate")
    target_language: str = Field(default="zh", description="Target language code")

    # Mode configuration
    mode: TranslationMode = Field(
        default=TranslationMode.DIRECT, description="Translation mode to use"
    )

    # Rich context
    book_analysis: Optional[BookAnalysisContext] = Field(
        default=None, description="Book analysis context"
    )
    adjacent: Optional[AdjacentContext] = Field(
        default=None, description="Adjacent paragraphs for coherence"
    )
    existing: Optional[ExistingTranslation] = Field(
        default=None, description="Existing translation for optimization mode"
    )

    # Custom overrides
    custom_system_prompt: Optional[str] = Field(
        default=None, description="Custom system prompt override"
    )
    custom_user_prompt: Optional[str] = Field(
        default=None, description="Custom user prompt override"
    )

    # Processing hints
    preserve_formatting: bool = Field(
        default=True, description="Whether to preserve source formatting"
    )
    preserve_proper_nouns: bool = Field(
        default=True, description="Whether to preserve proper noun translations"
    )

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "TranslationContext":
        """Validate context completeness for selected mode."""
        if self.mode == TranslationMode.OPTIMIZATION and not self.existing:
            raise ValueError("Optimization mode requires existing translation")
        return self

    def get_terminology_list(self) -> List[str]:
        """Get formatted terminology list for prompt injection."""
        if not self.book_analysis or not self.book_analysis.key_terminology:
            return []
        return [
            f"- {en}: {zh}"
            for en, zh in self.book_analysis.key_terminology.items()
        ]

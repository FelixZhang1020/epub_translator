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
    ITERATIVE = "iterative"  # Multi-pass refinement


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
        # Extract translation principles if present
        principles = None
        if raw.get("translation_principles"):
            tp = raw["translation_principles"]
            principles = TranslationPrinciples(
                priority_order=tp.get("priority_order", ["faithfulness", "expressiveness", "elegance"]),
                faithfulness_boundary=tp.get("faithfulness_boundary"),
                permissible_adaptation=tp.get("permissible_adaptation"),
                style_constraints=tp.get("style_constraints"),
                red_lines=tp.get("red_lines"),
            )

        return cls(
            author_name=raw.get("author_name"),
            author_biography=raw.get("author_biography"),
            writing_style=raw.get("writing_style"),
            tone=raw.get("tone"),
            genre=raw.get("genre"),
            target_audience=raw.get("target_audience"),
            genre_conventions=raw.get("genre_conventions"),
            key_terminology=raw.get("key_terminology", {}),
            translation_principles=principles,
            custom_guidelines=raw.get("custom_guidelines", []),
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

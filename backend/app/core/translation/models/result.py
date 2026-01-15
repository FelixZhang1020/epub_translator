"""Translation result models.

This module defines the final output data structures from the translation pipeline,
including quality indicators and metadata.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QualityFlag(str, Enum):
    """Quality indicators for translation output."""

    CONFIDENT = "confident"  # High confidence translation
    UNCERTAIN = "uncertain"  # Some uncertainty in translation
    NEEDS_REVIEW = "needs_review"  # Requires human review
    FORMATTING_LOST = "formatting_lost"  # Source formatting may be lost


class TranslationResult(BaseModel):
    """Final processed translation output.

    This is the output contract of the translation pipeline.
    Contains the translated text along with quality and cost metadata.
    """

    # Core output
    translated_text: str = Field(..., description="The translated text")

    # Quality metadata
    quality_flag: QualityFlag = Field(
        default=QualityFlag.CONFIDENT, description="Quality indicator"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )

    # Processing metadata
    mode_used: str = Field(..., description="Translation mode that was used")
    provider: str = Field(..., description="LLM provider used")
    model: str = Field(..., description="Model used")

    # Cost tracking
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")

    # Formatting preservation
    preserved_elements: List[str] = Field(
        default_factory=list,
        description="List of preserved formatting elements",
    )

    # For debugging
    raw_llm_response: Optional[str] = Field(
        default=None, description="Raw LLM response before processing"
    )

    # Chain information (for multi-step translation)
    step_index: int = Field(default=0, description="Current step in multi-step flow")
    total_steps: int = Field(default=1, description="Total steps in translation flow")

    def is_high_quality(self) -> bool:
        """Check if translation is high quality.

        Returns:
            True if quality is confident and confidence score >= 0.8
        """
        if self.quality_flag != QualityFlag.CONFIDENT:
            return False
        if self.confidence_score is not None and self.confidence_score < 0.8:
            return False
        return True

    def needs_human_review(self) -> bool:
        """Check if translation needs human review.

        Returns:
            True if quality flag indicates review needed
        """
        return self.quality_flag in (QualityFlag.NEEDS_REVIEW, QualityFlag.UNCERTAIN)


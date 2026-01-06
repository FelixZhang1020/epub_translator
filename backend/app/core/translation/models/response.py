"""LLM response models.

This module defines the response data structures from LLM providers,
providing a provider-agnostic representation.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token consumption details."""

    prompt_tokens: int = Field(default=0, description="Tokens in the prompt")
    completion_tokens: int = Field(default=0, description="Tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens used")

    def model_post_init(self, __context: Any) -> None:
        """Calculate total if not provided."""
        if not self.total_tokens and (self.prompt_tokens or self.completion_tokens):
            self.total_tokens = self.prompt_tokens + self.completion_tokens

    def estimate_cost_usd(
        self,
        input_cost_per_million: float = 3.0,
        output_cost_per_million: float = 15.0,
    ) -> float:
        """Estimate cost in USD based on token usage.

        Args:
            input_cost_per_million: Cost per million input tokens
            output_cost_per_million: Cost per million output tokens

        Returns:
            Estimated cost in USD
        """
        input_cost = (self.prompt_tokens / 1_000_000) * input_cost_per_million
        output_cost = (self.completion_tokens / 1_000_000) * output_cost_per_million
        return input_cost + output_cost


class LLMResponse(BaseModel):
    """Raw response from LLM provider.

    Provider-agnostic representation of an LLM response.
    """

    content: str = Field(..., description="Response content from LLM")

    # Provider info
    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier used")

    # Usage statistics
    usage: TokenUsage = Field(
        default_factory=TokenUsage, description="Token usage details"
    )

    # Timing
    latency_ms: int = Field(default=0, description="Response latency in milliseconds")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )

    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Raw provider response for debugging"
    )

    # Streaming metadata
    is_complete: bool = Field(
        default=True, description="Whether this is a complete response"
    )
    chunk_index: Optional[int] = Field(
        default=None, description="Chunk index for streaming responses"
    )

    @property
    def estimated_cost_usd(self) -> float:
        """Get estimated cost in USD."""
        return self.usage.estimate_cost_usd()

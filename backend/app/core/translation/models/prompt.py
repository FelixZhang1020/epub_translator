"""Prompt bundle models.

This module defines the prompt data structures that are passed to LLM providers,
providing a unified interface for different provider formats.
"""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Single message in LLM conversation."""

    role: str = Field(
        ..., description="Message role: 'system', 'user', or 'assistant'"
    )
    content: str = Field(..., description="Message content")


class PromptBundle(BaseModel):
    """Complete prompt package ready for LLM.

    This is the output of the PromptEngine and input to LLMGateway.
    Contains all information needed to make an LLM API call.
    """

    messages: List[Message] = Field(..., description="Conversation messages")

    # Model configuration
    temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=4096, gt=0, description="Maximum tokens in response"
    )

    # Response format (for JSON mode)
    response_format: Optional[Dict[str, Any]] = Field(
        default=None, description="Response format specification"
    )

    # Metadata for logging and debugging
    mode: str = Field(default="direct", description="Translation mode used")
    estimated_input_tokens: int = Field(
        default=0, description="Estimated input token count"
    )

    # Variables used for preview (before rendering)
    template_variables: Dict[str, Any] = Field(
        default_factory=dict, description="Variables used in prompt templates"
    )

    @property
    def system_prompt(self) -> Optional[str]:
        """Extract system prompt from messages."""
        for msg in self.messages:
            if msg.role == "system":
                return msg.content
        return None

    @property
    def user_prompt(self) -> Optional[str]:
        """Extract user prompt from messages."""
        for msg in self.messages:
            if msg.role == "user":
                return msg.content
        return None

    def to_openai_format(self) -> List[Dict[str, str]]:
        """Convert to OpenAI API message format.

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def to_anthropic_format(self) -> Tuple[str, List[Dict[str, str]]]:
        """Convert to Anthropic API format.

        Returns:
            Tuple of (system_prompt, messages) where messages exclude system
        """
        system = self.system_prompt or ""
        messages = [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role != "system"
        ]
        return system, messages

    def to_preview_dict(self) -> Dict[str, Any]:
        """Convert to preview format for API response.

        Returns:
            Dict with system_prompt, user_prompt, variables, and metadata
        """
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "variables": self.template_variables,
            "mode": self.mode,
            "estimated_tokens": self.estimated_input_tokens,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def estimate_tokens(self) -> int:
        """Estimate total input tokens.

        Uses a simple heuristic: ~4 characters per token for English,
        ~2 characters per token for Chinese.

        Returns:
            Estimated token count
        """
        total_chars = sum(len(m.content) for m in self.messages)
        # Rough estimate: average 3 chars per token (mix of EN/ZH)
        return total_chars // 3

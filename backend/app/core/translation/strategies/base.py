"""Base prompt strategy.

This module defines the abstract base class for all translation prompt strategies.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models.context import TranslationContext
from ..models.prompt import PromptBundle
from app.utils.text import safe_truncate


class PromptStrategy(ABC):
    """Abstract base class for translation prompt strategies.

    Each strategy encapsulates the logic for building prompts for a specific
    translation mode. Strategies are responsible for:
    1. Building the system prompt with appropriate instructions
    2. Building the user prompt with source text and context
    3. Setting appropriate model parameters (temperature, max_tokens)
    """

    @abstractmethod
    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle from translation context.

        Args:
            context: Complete translation context

        Returns:
            PromptBundle ready for LLM call
        """
        pass

    @abstractmethod
    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract template variables for preview.

        Args:
            context: Translation context

        Returns:
            Dictionary of variable names to values used in prompts
        """
        pass

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple heuristic based on character count.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 chars per token for English, ~2 for Chinese
        # Use average of 3 for mixed content
        return len(text) // 3

    def _truncate_for_context(
        self, text: str, max_chars: int = 500
    ) -> str:
        """Truncate text for context inclusion.

        Uses safe_truncate to avoid breaking multi-byte characters.

        Args:
            text: Text to truncate
            max_chars: Maximum characters to include

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_chars:
            return text
        return safe_truncate(text, max_chars)


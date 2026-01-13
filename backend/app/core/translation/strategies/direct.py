"""Direct translation strategy.

This module provides a simple, direct translation strategy without
extensive context or author-aware features.
"""

import logging
from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle
from app.core.prompts.loader import PromptLoader

logger = logging.getLogger(__name__)


class DirectTranslationStrategy(PromptStrategy):
    """Simple direct translation strategy.

    This strategy provides basic translation with minimal context.
    Suitable for straightforward translation tasks without specific
    author style requirements.

    Prompts are loaded from:
    - backend/prompts/translation/system.default.md
    - backend/prompts/translation/user.default.md
    """

    # Language name mapping
    LANGUAGE_NAMES = {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
    }

    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle for direct translation.

        Args:
            context: Translation context

        Returns:
            PromptBundle with system and user messages
        """
        variables = self.get_template_variables(context)

        # Load prompts from .md files using configured default template
        try:
            template_name = PromptLoader.get_default_template("translation")
            template = PromptLoader.load_template("translation", template_name)
            system_prompt = PromptLoader.render(template.system_prompt, variables)
            user_prompt = PromptLoader.render(template.user_prompt_template, variables)
        except Exception as e:
            logger.warning(f"Failed to load prompts from files: {e}. Using fallback.")
            system_prompt = self._get_fallback_system_prompt(variables)
            user_prompt = self._get_fallback_user_prompt(variables)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            mode="direct",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract template variables for direct translation.

        Args:
            context: Translation context

        Returns:
            Dictionary with variables for template rendering
        """
        target_lang_name = self.LANGUAGE_NAMES.get(
            context.target_language, context.target_language
        )

        return {
            "content.source": context.source.text,
            "content": {"source": context.source.text},
            "source_text": context.source.text,
            "target_language": context.target_language,
            "target_language_name": target_lang_name,
            "project": {
                "title": "",
                "author": "",
            },
        }

    def _get_fallback_system_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback system prompt in English."""
        return f"""You are a professional translator, fluent in English to {variables.get('target_language_name', 'Chinese')} translation.

## Translation Requirements
1. Accurately convey the meaning and emotion of the original text
2. Use natural, fluent {variables.get('target_language_name', 'Chinese')} expressions
3. Preserve the format and paragraph structure of the original
4. Use common translations for proper nouns

## Output Requirements
Output only the translation, without any explanation or commentary."""

    def _get_fallback_user_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback user prompt in English."""
        return f"""Please translate the following English text:

{variables.get('source_text', variables.get('content.source', ''))}"""

"""Optimization translation strategy.

This module provides a strategy for improving existing translations,
making them more natural and modern while preserving meaning.
"""

import logging
from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle
from app.core.prompts.loader import PromptLoader

logger = logging.getLogger(__name__)


class OptimizationStrategy(PromptStrategy):
    """Optimization strategy for improving existing translations.

    This strategy takes an existing translation and the original text,
    then produces an improved version with:
    - Updated expressions for modern Chinese
    - Improved fluency and readability
    - Preserved original meaning and author style

    Prompts are loaded from:
    - backend/prompts/optimization/system.default.md
    - backend/prompts/optimization/user.default.md
    """

    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle for translation optimization.

        Args:
            context: Translation context with existing translation

        Returns:
            PromptBundle for optimization

        Raises:
            ValueError: If existing translation is not provided
        """
        if not context.existing:
            raise ValueError("Optimization mode requires existing translation")

        variables = self.get_template_variables(context)

        # Load prompts from .md files using configured default template
        try:
            template_name = PromptLoader.get_default_template("optimization")
            template = PromptLoader.load_template("optimization", template_name)
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
            mode="optimization",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract template variables for optimization.

        Args:
            context: Translation context

        Returns:
            Dictionary with source text, existing translation, and style info
        """
        variables: Dict[str, Any] = {
            "content.source": context.source.text,
            "content.target": context.existing.text if context.existing else "",
            "content": {
                "source": context.source.text,
                "target": context.existing.text if context.existing else "",
            },
            "source_text": context.source.text,
            "existing_translation": context.existing.text if context.existing else "",
            "derived": {},
        }

        # Extract style information if available
        if context.book_analysis:
            ba = context.book_analysis
            variables["derived"].update({
                "writing_style": ba.writing_style,
                "tone": ba.tone,
                "has_analysis": True,
            })

            # Terminology list
            if ba.key_terminology:
                term_rows = [f"| {en} | {zh} |" for en, zh in ba.key_terminology.items()]
                variables["derived"]["terminology_table"] = (
                    "| English | Chinese |\n| --- | --- |\n" + "\n".join(term_rows)
                )
                variables["derived"]["has_terminology"] = True

        return variables

    def _get_fallback_system_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback system prompt in English."""
        return """You are a Chinese language optimization expert. Your task is to improve existing Chinese translations to better conform to modern Chinese expression conventions.

## Optimization Requirements
1. Update outdated or obscure expressions
2. Use contemporary common vocabulary
3. Improve sentence fluency and readability
4. Maintain accuracy of the original meaning
5. Preserve the original author's tone and style

## Output Format
Output only the optimized translation, without any explanation."""

    def _get_fallback_user_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback user prompt in English."""
        source = variables.get("source_text", variables.get("content.source", ""))
        existing = variables.get("existing_translation", variables.get("content.target", ""))
        return f"""Original text (English):
{source}

Existing translation (to be optimized):
{existing}

Please optimize the above translation:"""

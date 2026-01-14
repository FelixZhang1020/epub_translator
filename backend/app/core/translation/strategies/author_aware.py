"""Author-aware translation strategy.

This module provides a context-rich translation strategy that incorporates
book analysis, author background, and translation principles.
"""

import logging
from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle
from app.core.prompts.loader import PromptLoader

logger = logging.getLogger(__name__)


class AuthorAwareStrategy(PromptStrategy):
    """Author-aware translation strategy with rich context.

    This strategy builds comprehensive prompts that include:
    - Author biography and background
    - Writing style characteristics
    - Translation principles and red lines
    - Key terminology mappings
    - Adjacent paragraph context for coherence

    Prompts are loaded from:
    - backend/prompts/translation/system.default.md
    - backend/prompts/translation/user.default.md
    """

    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle with author-aware context.

        Args:
            context: Translation context with book analysis

        Returns:
            PromptBundle with comprehensive system and user messages
        """
        variables = self.get_template_variables(context)

        # Load prompts from .md files using configured default template
        try:
            template_name = PromptLoader.get_default_template("translation")
            logger.info(f"Loading translation template: {template_name}")
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
            mode="author_aware",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract all template variables for author-aware translation.

        Args:
            context: Translation context

        Returns:
            Dictionary with all variables used in prompts
        """
        variables: Dict[str, Any] = {
            "content.source": context.source.text,
            "content": {"source": context.source.text},
            "source_text": context.source.text,
            "target_language": context.target_language,
            "project": {
                "title": context.project.title if context.project else "",
                "author": context.project.author if context.project else "",
                "author_background": context.project.author_background if context.project else "",
            },
            "derived": {},
        }

        # Extract book analysis variables
        if context.book_analysis:
            ba = context.book_analysis
            variables["derived"].update({
                "writing_style": ba.writing_style,
                "tone": ba.tone,
                "target_audience": ba.target_audience,
                "genre_conventions": ba.genre_conventions,
                "has_analysis": True,
            })

            # Terminology as formatted table
            if ba.key_terminology:
                term_rows = [f"| {en} | {zh} |" for en, zh in ba.key_terminology.items()]
                variables["derived"]["terminology_table"] = (
                    "| English | Chinese |\n| --- | --- |\n" + "\n".join(term_rows)
                )
                variables["derived"]["has_terminology"] = True

            # Translation principles
            if ba.translation_principles:
                tp = ba.translation_principles
                variables["derived"].update({
                    "priority_order": tp.priority_order,
                    "faithfulness_boundary": tp.faithfulness_boundary,
                    "permissible_adaptation": tp.permissible_adaptation,
                    "style_constraints": tp.style_constraints,
                    "red_lines": tp.red_lines,
                    "has_translation_principles": bool(
                        tp.faithfulness_boundary or tp.permissible_adaptation or tp.red_lines
                    ),
                })

            # Custom guidelines
            if ba.custom_guidelines:
                variables["derived"]["custom_guidelines"] = ba.custom_guidelines
                variables["derived"]["has_custom_guidelines"] = True

        # Extract adjacent context
        if context.adjacent:
            adj = context.adjacent
            if adj.previous_original:
                variables["context.previous_source"] = self._truncate_for_context(
                    adj.previous_original
                )
            if adj.previous_translation:
                variables["context.previous_target"] = self._truncate_for_context(
                    adj.previous_translation
                )
            variables["context"] = {
                "previous_source": variables.get("context.previous_source", ""),
                "previous_target": variables.get("context.previous_target", ""),
            }

        return variables

    def _get_fallback_system_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback system prompt in English."""
        return """You are a professional literary translator, specializing in English to Chinese translation.

## Translation Requirements
1. Use modern Chinese expressions that suit contemporary readers
2. Accurately convey the meaning and emotion of the original text
3. Translate proper nouns according to Chinese conventions
4. Maintain the author's writing style and tone
5. Ensure the translation flows naturally

## Output Requirements
Output only the translation, without any explanation or commentary."""

    def _get_fallback_user_prompt(self, variables: Dict[str, Any]) -> str:
        """Get fallback user prompt in English."""
        source = variables.get("source_text", variables.get("content.source", ""))
        return f"""Please translate the following English text:

{source}"""

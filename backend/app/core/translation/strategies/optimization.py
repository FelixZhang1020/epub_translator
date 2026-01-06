"""Optimization translation strategy.

This module provides a strategy for improving existing translations,
making them more natural and modern while preserving meaning.
"""

from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle


class OptimizationStrategy(PromptStrategy):
    """Optimization strategy for improving existing translations.

    This strategy takes an existing translation and the original text,
    then produces an improved version with:
    - Updated expressions for modern Chinese
    - Improved fluency and readability
    - Preserved original meaning and author style
    """

    SYSTEM_TEMPLATE = """你是一位中文语言优化专家。你的任务是优化已有的中文翻译，使其更符合现代汉语表达习惯。

## 优化要求
1. 更新过时或生僻的表达方式
2. 使用当代常用词汇
3. 提高句子的流畅性和可读性
4. 保持原文含义的准确性
5. 保留原作者的语气和风格

{style_section}
{terminology_section}
## 输出格式
直接输出优化后的翻译，不要添加任何解释。"""

    STYLE_SECTION = """## 风格参考
- 写作风格：{writing_style}
- 语气：{tone}
"""

    TERMINOLOGY_SECTION = """## 术语一致性（请保持以下译法）
{terminology_list}
"""

    USER_TEMPLATE = """原文（英文）：
{source_text}

现有翻译（待优化）：
{existing_translation}

请优化上述翻译："""

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

        # Build system prompt with optional sections
        system_prompt = self._build_system_prompt(context, variables)

        # Build user prompt
        user_prompt = self.USER_TEMPLATE.format(**variables)

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
            "source_text": context.source.text,
            "existing_translation": context.existing.text if context.existing else "",
        }

        # Extract style information if available
        if context.book_analysis:
            ba = context.book_analysis
            variables.update({
                "writing_style": ba.writing_style,
                "tone": ba.tone,
            })

            # Terminology list
            if ba.key_terminology:
                term_list = [
                    f"- {en}: {zh}"
                    for en, zh in ba.key_terminology.items()
                ]
                variables["terminology_list"] = "\n".join(term_list)

        return variables

    def _build_system_prompt(
        self, context: TranslationContext, variables: Dict[str, Any]
    ) -> str:
        """Build system prompt with conditional sections.

        Args:
            context: Translation context
            variables: Pre-extracted variables

        Returns:
            System prompt string
        """
        style_section = ""
        terminology_section = ""

        # Add style section if available
        if variables.get("writing_style") or variables.get("tone"):
            style_section = self.STYLE_SECTION.format(
                writing_style=variables.get("writing_style", "N/A"),
                tone=variables.get("tone", "N/A"),
            )

        # Add terminology section if available
        if variables.get("terminology_list"):
            terminology_section = self.TERMINOLOGY_SECTION.format(
                terminology_list=variables["terminology_list"]
            )

        return self.SYSTEM_TEMPLATE.format(
            style_section=style_section,
            terminology_section=terminology_section,
        )

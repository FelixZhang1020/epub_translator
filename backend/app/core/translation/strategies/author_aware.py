"""Author-aware translation strategy.

This module provides a context-rich translation strategy that incorporates
book analysis, author background, and translation principles.
"""

from typing import Any, Dict, List, Optional

from .base import PromptStrategy
from ..models.context import TranslationContext, BookAnalysisContext
from ..models.prompt import Message, PromptBundle


class AuthorAwareStrategy(PromptStrategy):
    """Author-aware translation strategy with rich context.

    This strategy builds comprehensive prompts that include:
    - Author biography and background
    - Writing style characteristics
    - Translation principles and red lines
    - Key terminology mappings
    - Adjacent paragraph context for coherence
    """

    # Base system prompt components
    SYSTEM_BASE = """你是一位专业的文学翻译家，精通英文到中文的翻译。

## 翻译要求
1. 使用现代汉语表达，符合当代读者的阅读习惯
2. 准确传达原文的含义和情感
3. 人名地名等专有名词采用中国习惯的翻译方式
4. 保持原作者的写作风格和语气
5. 译文流畅自然，不生硬"""

    # Section templates
    AUTHOR_SECTION = """
## 作者背景
{author_biography}"""

    STYLE_SECTION = """
## 写作风格
{writing_style}"""

    TONE_SECTION = """
## 语气特点
{tone}"""

    AUDIENCE_SECTION = """
## 目标读者
{target_audience}"""

    PRINCIPLES_SECTION = """
## 翻译原则
- 优先级：{priority_order}
- 忠实度边界：{faithfulness_boundary}
- 允许的调整：{permissible_adaptation}
- 风格约束：{style_constraints}"""

    REDLINES_SECTION = """
## 翻译红线（必须避免）
{red_lines}"""

    TERMINOLOGY_SECTION = """
## 术语表（请保持一致）
{terminology_list}"""

    GUIDELINES_SECTION = """
## 自定义要求
{guidelines_list}"""

    OUTPUT_SECTION = """
## 输出要求
直接输出翻译结果，不要添加任何解释或注释。"""

    # User prompt with optional adjacent context
    USER_WITH_CONTEXT = """[上文参考]
原文：{prev_original}
译文：{prev_translation}

[请翻译以下段落]
{source_text}"""

    USER_SIMPLE = """请翻译以下英文：

{source_text}"""

    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle with author-aware context.

        Args:
            context: Translation context with book analysis

        Returns:
            PromptBundle with comprehensive system and user messages
        """
        variables = self.get_template_variables(context)

        # Build system prompt from sections
        system_prompt = self._build_system_prompt(context, variables)

        # Build user prompt with optional adjacent context
        user_prompt = self._build_user_prompt(context, variables)

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
            "source_text": context.source.text,
            "target_language": context.target_language,
        }

        # Extract book analysis variables
        if context.book_analysis:
            ba = context.book_analysis
            variables.update({
                "author_biography": ba.author_biography,
                "writing_style": ba.writing_style,
                "tone": ba.tone,
                "target_audience": ba.target_audience,
                "genre_conventions": ba.genre_conventions,
            })

            # Terminology as formatted list
            if ba.key_terminology:
                term_list = [
                    f"- {en}: {zh}"
                    for en, zh in ba.key_terminology.items()
                ]
                variables["terminology_list"] = "\n".join(term_list)
                variables["key_terminology"] = ba.key_terminology

            # Translation principles
            if ba.translation_principles:
                tp = ba.translation_principles
                variables.update({
                    "priority_order": " > ".join(tp.priority_order),
                    "faithfulness_boundary": tp.faithfulness_boundary,
                    "permissible_adaptation": tp.permissible_adaptation,
                    "style_constraints": tp.style_constraints,
                    "red_lines": tp.red_lines,
                })

            # Custom guidelines as formatted list
            if ba.custom_guidelines:
                guidelines = [f"- {g}" for g in ba.custom_guidelines]
                variables["guidelines_list"] = "\n".join(guidelines)

        # Extract adjacent context
        if context.adjacent:
            adj = context.adjacent
            if adj.previous_original:
                variables["prev_original"] = self._truncate_for_context(
                    adj.previous_original
                )
            if adj.previous_translation:
                variables["prev_translation"] = self._truncate_for_context(
                    adj.previous_translation
                )

        return variables

    def _build_system_prompt(
        self, context: TranslationContext, variables: Dict[str, Any]
    ) -> str:
        """Build system prompt from sections based on available data.

        Args:
            context: Translation context
            variables: Pre-extracted template variables

        Returns:
            Complete system prompt string
        """
        sections = [self.SYSTEM_BASE]

        # Add sections conditionally based on available data
        if variables.get("author_biography"):
            sections.append(
                self.AUTHOR_SECTION.format(
                    author_biography=variables["author_biography"]
                )
            )

        if variables.get("writing_style"):
            sections.append(
                self.STYLE_SECTION.format(writing_style=variables["writing_style"])
            )

        if variables.get("tone"):
            sections.append(self.TONE_SECTION.format(tone=variables["tone"]))

        if variables.get("target_audience"):
            sections.append(
                self.AUDIENCE_SECTION.format(
                    target_audience=variables["target_audience"]
                )
            )

        # Add translation principles if available
        if (
            context.book_analysis
            and context.book_analysis.translation_principles
        ):
            tp = context.book_analysis.translation_principles
            if any([tp.faithfulness_boundary, tp.permissible_adaptation, tp.style_constraints]):
                sections.append(
                    self.PRINCIPLES_SECTION.format(
                        priority_order=variables.get("priority_order", "faithfulness > expressiveness > elegance"),
                        faithfulness_boundary=variables.get("faithfulness_boundary", "N/A"),
                        permissible_adaptation=variables.get("permissible_adaptation", "N/A"),
                        style_constraints=variables.get("style_constraints", "N/A"),
                    )
                )

            if tp.red_lines:
                sections.append(
                    self.REDLINES_SECTION.format(red_lines=variables["red_lines"])
                )

        # Add terminology section
        if variables.get("terminology_list"):
            sections.append(
                self.TERMINOLOGY_SECTION.format(
                    terminology_list=variables["terminology_list"]
                )
            )

        # Add custom guidelines
        if variables.get("guidelines_list"):
            sections.append(
                self.GUIDELINES_SECTION.format(
                    guidelines_list=variables["guidelines_list"]
                )
            )

        # Always add output section
        sections.append(self.OUTPUT_SECTION)

        return "\n".join(sections)

    def _build_user_prompt(
        self, context: TranslationContext, variables: Dict[str, Any]
    ) -> str:
        """Build user prompt with optional adjacent context.

        Args:
            context: Translation context
            variables: Pre-extracted template variables

        Returns:
            User prompt string
        """
        # Include adjacent context if available
        if (
            context.adjacent
            and context.adjacent.previous_original
            and context.adjacent.previous_translation
        ):
            return self.USER_WITH_CONTEXT.format(
                prev_original=variables["prev_original"],
                prev_translation=variables["prev_translation"],
                source_text=variables["source_text"],
            )

        return self.USER_SIMPLE.format(source_text=variables["source_text"])

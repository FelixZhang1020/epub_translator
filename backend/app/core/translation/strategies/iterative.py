"""Iterative translation strategy.

This module provides a multi-step translation strategy that first creates
a literal translation, then refines it for naturalness.
"""

from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle


class IterativeStrategy(PromptStrategy):
    """Multi-step iterative translation strategy.

    This strategy performs translation in multiple steps:
    1. Step 1: Create a literal, accurate translation
    2. Step 2: Refine for naturalness while preserving meaning

    Use get_step() to determine which step to build prompts for.
    """

    # Step 1: Literal translation
    STEP1_SYSTEM = """你是一位精确的翻译者。请创建一个直译版本，优先保证准确性。

## 翻译要求
1. 尽可能贴近原文的句式结构
2. 确保每个概念都准确传达
3. 暂时不必追求中文的优美流畅
4. 专有名词按通用译法翻译

## 输出格式
<literal>
你的直译内容
</literal>"""

    STEP1_USER = """请直译以下英文：

{source_text}"""

    # Step 2: Refinement
    STEP2_SYSTEM = """你是一位中文润色专家。请基于提供的直译版本进行润色，使其成为优美流畅的中文。

## 润色要求
1. 在保持原意的前提下，调整为自然的中文表达
2. 消除翻译腔，使用地道的中文用语
3. 保持原文的语气和风格
4. 确保专业术语准确

{style_section}
## 输出格式
直接输出润色后的译文，不要添加任何解释。"""

    STEP2_STYLE_SECTION = """## 风格参考
- 写作风格：{writing_style}
- 语气：{tone}
"""

    STEP2_USER = """原文（英文）：
{source_text}

直译版本：
{literal_translation}

请润色为自然流畅的中文："""

    def __init__(self, step: int = 1):
        """Initialize strategy for specific step.

        Args:
            step: Which step to build prompts for (1 or 2)
        """
        self.step = step

    def build(self, context: TranslationContext) -> PromptBundle:
        """Build prompt bundle for the configured step.

        Args:
            context: Translation context

        Returns:
            PromptBundle for the current step
        """
        if self.step == 1:
            return self._build_step1(context)
        else:
            return self._build_step2(context)

    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract template variables for iterative translation.

        Args:
            context: Translation context

        Returns:
            Dictionary with variables for the current step
        """
        variables: Dict[str, Any] = {
            "source_text": context.source.text,
            "step": self.step,
        }

        # For step 2, include literal translation
        if self.step == 2 and context.existing:
            variables["literal_translation"] = context.existing.text

        # Style information for step 2
        if context.book_analysis:
            variables.update({
                "writing_style": context.book_analysis.writing_style,
                "tone": context.book_analysis.tone,
            })

        return variables

    def _build_step1(self, context: TranslationContext) -> PromptBundle:
        """Build prompt for step 1: literal translation.

        Args:
            context: Translation context

        Returns:
            PromptBundle for literal translation
        """
        variables = self.get_template_variables(context)

        system_prompt = self.STEP1_SYSTEM
        user_prompt = self.STEP1_USER.format(source_text=variables["source_text"])

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.2,  # Lower temperature for accuracy
            max_tokens=4096,
            mode="iterative_step1",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

    def _build_step2(self, context: TranslationContext) -> PromptBundle:
        """Build prompt for step 2: refinement.

        Args:
            context: Translation context (should include literal translation)

        Returns:
            PromptBundle for refinement

        Raises:
            ValueError: If literal translation is not available
        """
        if not context.existing:
            raise ValueError(
                "Step 2 requires literal translation from step 1 in context.existing"
            )

        variables = self.get_template_variables(context)

        # Build style section if available
        style_section = ""
        if variables.get("writing_style") or variables.get("tone"):
            style_section = self.STEP2_STYLE_SECTION.format(
                writing_style=variables.get("writing_style", "N/A"),
                tone=variables.get("tone", "N/A"),
            )

        system_prompt = self.STEP2_SYSTEM.format(style_section=style_section)
        user_prompt = self.STEP2_USER.format(
            source_text=variables["source_text"],
            literal_translation=variables["literal_translation"],
        )

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        return PromptBundle(
            messages=messages,
            temperature=0.4,  # Slightly higher for creativity in polishing
            max_tokens=4096,
            mode="iterative_step2",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

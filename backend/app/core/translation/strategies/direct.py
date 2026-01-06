"""Direct translation strategy.

This module provides a simple, direct translation strategy without
extensive context or author-aware features.
"""

from typing import Any, Dict

from .base import PromptStrategy
from ..models.context import TranslationContext
from ..models.prompt import Message, PromptBundle


class DirectTranslationStrategy(PromptStrategy):
    """Simple direct translation strategy.

    This strategy provides basic translation with minimal context.
    Suitable for straightforward translation tasks without specific
    author style requirements.
    """

    # System prompt template - kept in Chinese as per project spec
    # (prompt content is allowed to be in Chinese)
    SYSTEM_TEMPLATE = """你是一位专业的翻译，精通英文到{target_language_name}的翻译。

## 翻译要求
1. 准确传达原文的含义和情感
2. 使用自然、流畅的{target_language_name}表达
3. 保持原文的格式和段落结构
4. 专有名词采用通用译法

## 输出要求
直接输出翻译结果，不要添加任何解释或注释。"""

    USER_TEMPLATE = """请翻译以下英文：

{source_text}"""

    # Language name mapping
    LANGUAGE_NAMES = {
        "zh": "中文",
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

        # Build system prompt
        system_prompt = self.SYSTEM_TEMPLATE.format(**variables)

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
            mode="direct",
            estimated_input_tokens=self.estimate_tokens(system_prompt + user_prompt),
            template_variables=variables,
        )

    def get_template_variables(self, context: TranslationContext) -> Dict[str, Any]:
        """Extract template variables for direct translation.

        Args:
            context: Translation context

        Returns:
            Dictionary with source_text and target_language_name
        """
        target_lang_name = self.LANGUAGE_NAMES.get(
            context.target_language, context.target_language
        )

        return {
            "source_text": context.source.text,
            "target_language": context.target_language,
            "target_language_name": target_lang_name,
        }

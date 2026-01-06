"""Output processor for translation results.

This module provides processing and validation of raw LLM responses,
transforming them into structured TranslationResult objects.
"""

import re
from typing import Tuple

from ..models.context import TranslationContext
from ..models.response import LLMResponse
from ..models.result import QualityFlag, TranslationResult


class OutputProcessor:
    """Processes raw LLM responses into final translation results.

    Responsibilities:
    1. Extract translation text from various response formats
    2. Assess translation quality
    3. Apply post-processing transformations
    4. Build structured TranslationResult
    """

    # Patterns for extracting translation from various formats
    EXTRACTION_PATTERNS = [
        # XML-like tags
        (r"<translation>(.*?)</translation>", re.DOTALL),
        (r"<literal>(.*?)</literal>", re.DOTALL),
        (r"<refined>(.*?)</refined>", re.DOTALL),
        (r"<result>(.*?)</result>", re.DOTALL),
    ]

    def process(
        self,
        response: LLMResponse,
        context: TranslationContext,
    ) -> TranslationResult:
        """Process raw LLM response into translation result.

        Args:
            response: Raw response from LLM
            context: Original translation context

        Returns:
            Processed TranslationResult
        """
        # 1. Extract translation text
        translated_text = self._extract_translation(response.content)

        # 2. Assess quality
        quality_flag, confidence = self._assess_quality(translated_text, context)

        # 3. Post-process
        translated_text = self._post_process(translated_text, context)

        # 4. Build result
        return TranslationResult(
            translated_text=translated_text,
            quality_flag=quality_flag,
            confidence_score=confidence,
            mode_used=context.mode.value,
            provider=response.provider,
            model=response.model,
            tokens_used=response.usage.total_tokens,
            estimated_cost_usd=response.usage.estimate_cost_usd(),
            raw_llm_response=response.content,
        )

    def _extract_translation(self, content: str) -> str:
        """Extract translation text from response content.

        Handles various response formats:
        - Plain text
        - Markdown code blocks
        - XML-like tags

        Args:
            content: Raw response content

        Returns:
            Extracted translation text
        """
        content = content.strip()

        # Try to extract from markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (``` markers)
            if len(lines) >= 3:
                content = "\n".join(lines[1:-1])

        # Try to extract from XML-like tags
        for pattern, flags in self.EXTRACTION_PATTERNS:
            match = re.search(pattern, content, flags)
            if match:
                return match.group(1).strip()

        # Return as-is if no special format detected
        return content.strip()

    def _assess_quality(
        self,
        translated: str,
        context: TranslationContext,
    ) -> Tuple[QualityFlag, float]:
        """Assess translation quality based on heuristics.

        Checks:
        - Length ratio (Chinese typically 0.5-1.0x English length)
        - Presence of untranslated English
        - Formatting preservation

        Args:
            translated: Translated text
            context: Original translation context

        Returns:
            Tuple of (QualityFlag, confidence_score)
        """
        confidence = 1.0
        flag = QualityFlag.CONFIDENT
        issues = []

        source_text = context.source.text

        # Check for empty translation
        if not translated.strip():
            return QualityFlag.NEEDS_REVIEW, 0.0

        # Check length ratio
        ratio = len(translated) / len(source_text) if source_text else 0
        if ratio < 0.3:
            issues.append("too_short")
            confidence *= 0.6
        elif ratio > 1.5:
            issues.append("too_long")
            confidence *= 0.8

        # Check for untranslated English chunks (10+ consecutive letters)
        english_pattern = r"[a-zA-Z]{10,}"
        english_chunks = re.findall(english_pattern, translated)
        if english_chunks:
            # Filter out common preserved terms (proper nouns, technical terms)
            # These are acceptable in translations
            suspicious_chunks = [
                chunk for chunk in english_chunks
                if chunk.lower() not in self._get_common_preserved_terms()
            ]
            if suspicious_chunks:
                issues.append("untranslated_english")
                confidence *= 0.7

        # Check formatting preservation
        source_has_breaks = "\n\n" in source_text
        trans_has_breaks = "\n\n" in translated
        if source_has_breaks and not trans_has_breaks:
            issues.append("formatting_lost")

        # Determine final quality flag
        if "too_short" in issues or confidence < 0.5:
            flag = QualityFlag.NEEDS_REVIEW
        elif "untranslated_english" in issues:
            flag = QualityFlag.UNCERTAIN
        elif "formatting_lost" in issues:
            flag = QualityFlag.FORMATTING_LOST

        return flag, max(0.0, min(1.0, confidence))

    def _post_process(
        self,
        text: str,
        context: TranslationContext,
    ) -> str:
        """Apply post-processing transformations.

        Args:
            text: Translated text
            context: Translation context

        Returns:
            Post-processed text
        """
        # Normalize excessive newlines (3+ -> 2)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        # Normalize Chinese punctuation if needed
        text = self._normalize_punctuation(text)

        return text

    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation to Chinese style.

        Args:
            text: Text to normalize

        Returns:
            Text with normalized punctuation
        """
        # Common replacements for Chinese text
        replacements = {
            ",": "，",  # English comma to Chinese comma
            ":": "：",  # English colon to Chinese colon
            ";": "；",  # English semicolon to Chinese semicolon
            "!": "！",  # English exclamation to Chinese
            "?": "？",  # English question mark to Chinese
            "(": "（",  # Parentheses
            ")": "）",
        }

        # Only replace if the text is predominantly Chinese
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        total_chars = len(text.replace(" ", "").replace("\n", ""))

        if total_chars > 0 and chinese_chars / total_chars > 0.5:
            for eng, chn in replacements.items():
                # Only replace if not inside English words
                text = re.sub(
                    rf"(?<=[\u4e00-\u9fff]){re.escape(eng)}",
                    chn,
                    text
                )
                text = re.sub(
                    rf"{re.escape(eng)}(?=[\u4e00-\u9fff])",
                    chn,
                    text
                )

        return text

    def _get_common_preserved_terms(self) -> set:
        """Get set of terms commonly preserved in translation.

        Returns:
            Set of lowercase terms that are acceptable in translations
        """
        return {
            # Technical terms
            "python", "javascript", "typescript", "react", "vue", "angular",
            "api", "http", "https", "url", "html", "css", "json", "xml",
            "sql", "database", "server", "client", "docker", "kubernetes",
            # Common brands/proper nouns
            "google", "facebook", "twitter", "microsoft", "apple", "amazon",
            "youtube", "instagram", "linkedin", "github", "stackoverflow",
            # Common abbreviations
            "email", "wifi", "usb", "pdf", "jpg", "png", "gif",
        }

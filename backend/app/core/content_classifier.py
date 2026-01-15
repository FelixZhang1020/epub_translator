"""Content classifier for chapters and paragraphs.

Classifies content to determine what should be included in proofreading
and what is front/back matter, image captions, or publishing content.
"""

import re
from typing import Optional

from app.models.database.enums import ChapterType, ContentType


class ContentClassifier:
    """Classify chapters and paragraphs by content type."""

    # Front matter indicators (chapter titles) - lowercase for matching
    FRONT_MATTER_KEYWORDS = {
        # Copyright and legal
        "copyright", "legal", "rights reserved", "isbn",
        "legal notice", "disclaimer",
        # Dedication and epigraph
        "dedication", "epigraph", "frontispiece",
        # Title pages
        "title page", "half title", "series page", "also by",
        # Table of contents
        "table of contents", "contents", "toc",
        # Introductory matter
        "preface", "foreword", "introduction", "prologue",
        "note to the reader", "author's note",
    }

    # Back matter indicators - lowercase for matching
    BACK_MATTER_KEYWORDS = {
        # Appendices and notes
        "appendix", "appendices", "annex",
        "notes", "endnotes", "footnotes", "source notes",
        # References
        "bibliography", "references", "works cited", "sources",
        "further reading", "recommended reading",
        # Glossary and index
        "glossary", "index", "list of terms",
        # Author info
        "about the author", "author bio", "biography",
        "about the translator", "translator's note",
        # Other books
        "also by", "other books", "more from",
        # Closing matter
        "afterword", "epilogue", "postscript",
        "acknowledgments", "acknowledgements",
        "colophon", "credits", "permissions",
    }

    # Publishing/legal content patterns (regex)
    PUBLISHING_PATTERNS = [
        r"all\s+rights\s+reserved",
        r"isbn[:\s]*[\d\-x]+",
        r"copyright\s*[©]?\s*\d{4}",
        r"published\s+by",
        r"printed\s+in",
        r"first\s+(edition|printing|published)",
        r"library\s+of\s+congress",
        r"cataloging.in.publication",
        r"no\s+part\s+of\s+this\s+(book|publication)",
        r"without\s+(the\s+)?prior\s+(written\s+)?permission",
        r"registered\s+trademark",
        r"^\s*\d+\s*$",  # Page numbers only
    ]

    # Image caption patterns (regex)
    IMAGE_CAPTION_PATTERNS = [
        r"^fig(ure)?\.?\s*\d+",
        r"^image\s*\d+",
        r"^photo(graph)?\s*\d+",
        r"^illustration\s*\d+",
        r"^plate\s*\d+",
        r"^diagram\s*\d+",
        r"^chart\s*\d+",
        r"^table\s*\d+",
        r"^map\s*\d+",
    ]

    # Compile patterns for efficiency
    _publishing_re = [re.compile(p, re.IGNORECASE) for p in PUBLISHING_PATTERNS]
    _caption_re = [re.compile(p, re.IGNORECASE) for p in IMAGE_CAPTION_PATTERNS]

    def classify_chapter(
        self,
        title: Optional[str],
        chapter_number: int,
        total_chapters: int,
    ) -> ChapterType:
        """Determine chapter type based on title and position.

        Args:
            title: Chapter title (may be None)
            chapter_number: 1-based chapter number
            total_chapters: Total number of chapters in the book

        Returns:
            ChapterType enum value
        """
        if not title:
            # No title - check position heuristics
            # First 1-2 chapters might be front matter
            if chapter_number <= 2 and total_chapters > 5:
                return ChapterType.FRONT_MATTER
            return ChapterType.MAIN_CONTENT

        title_lower = title.lower().strip()

        # Check for front matter keywords
        for keyword in self.FRONT_MATTER_KEYWORDS:
            if keyword in title_lower:
                return ChapterType.FRONT_MATTER

        # Check for back matter keywords
        for keyword in self.BACK_MATTER_KEYWORDS:
            if keyword in title_lower:
                return ChapterType.BACK_MATTER

        # Position-based heuristics for untitled or generic chapters
        # First chapter with generic title might be front matter
        if chapter_number == 1 and total_chapters > 5:
            # Check if it looks like a title page or copyright
            if len(title_lower) < 20 and not title_lower.startswith("chapter"):
                # Short title at the start - might be title page
                pass  # Let it be main content for now

        # Last 1-2 chapters might be back matter
        if chapter_number >= total_chapters - 1 and total_chapters > 5:
            # Only if title suggests back matter content
            pass  # Already checked keywords above

        return ChapterType.MAIN_CONTENT

    def classify_paragraph(
        self,
        text: str,
        html_tag: str,
        chapter_type: ChapterType,
    ) -> ContentType:
        """Determine paragraph content type.

        Args:
            text: Paragraph text content
            html_tag: HTML tag (p, h1, figcaption, etc.)
            chapter_type: Parent chapter's type

        Returns:
            ContentType enum value
        """
        if not text:
            return ContentType.METADATA

        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Check for image captions by tag
        if html_tag == "figcaption":
            return ContentType.IMAGE_CAPTION

        # Check for image caption patterns
        for pattern in self._caption_re:
            if pattern.match(text_lower):
                return ContentType.IMAGE_CAPTION

        # Check for publishing content in front matter
        if chapter_type == ChapterType.FRONT_MATTER:
            for pattern in self._publishing_re:
                if pattern.search(text_lower):
                    return ContentType.PUBLISHING

        # Very short text in front/back matter is often metadata
        if len(text_stripped) < 20:
            if chapter_type in (ChapterType.FRONT_MATTER, ChapterType.BACK_MATTER):
                # Check if it's just a number or very short
                if text_stripped.isdigit():
                    return ContentType.NAVIGATION
                # Short phrases in front/back matter
                return ContentType.METADATA

        return ContentType.MAIN

    def is_proofreadable(
        self,
        content_type: ContentType,
        chapter_type: ChapterType,
    ) -> bool:
        """Determine if content should be included in proofreading.

        Args:
            content_type: Paragraph's content type
            chapter_type: Parent chapter's type

        Returns:
            True if should be proofread, False otherwise
        """
        # Only main content in main chapters should be proofread
        if chapter_type != ChapterType.MAIN_CONTENT:
            return False

        if content_type != ContentType.MAIN:
            return False

        return True

    def classify_and_set_proofreadable(
        self,
        text: str,
        html_tag: str,
        chapter_title: Optional[str],
        chapter_number: int,
        total_chapters: int,
    ) -> tuple[ChapterType, ContentType, bool]:
        """Convenience method to classify and determine proofreadability.

        Args:
            text: Paragraph text
            html_tag: HTML tag
            chapter_title: Parent chapter title
            chapter_number: Chapter number (1-based)
            total_chapters: Total chapters in book

        Returns:
            Tuple of (chapter_type, content_type, is_proofreadable)
        """
        chapter_type = self.classify_chapter(
            chapter_title, chapter_number, total_chapters
        )
        content_type = self.classify_paragraph(text, html_tag, chapter_type)
        proofreadable = self.is_proofreadable(content_type, chapter_type)

        return chapter_type, content_type, proofreadable


# Module-level instance for convenience
classifier = ContentClassifier()


"""Text content extractor for copyright-compliant exports.

Extracts text-only content from chapters/paragraphs, stripping all
copyrighted assets like images while preserving semantic structure.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from html import escape as html_escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph


@dataclass
class ExtractedParagraph:
    """A paragraph extracted for export."""

    id: str
    paragraph_number: int
    original_text: str
    translated_text: Optional[str]
    html_tag: str
    is_heading: bool = False


@dataclass
class ExtractedChapter:
    """A chapter extracted for export."""

    id: str
    chapter_number: int
    title: Optional[str]
    paragraphs: list[ExtractedParagraph] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        """Count words in translated content."""
        total = 0
        for para in self.paragraphs:
            text = para.translated_text or para.original_text
            total += len(text.split())
        return total


@dataclass
class TOCEntry:
    """Table of contents entry."""

    title: str
    chapter_id: str
    level: int = 0
    children: list["TOCEntry"] = field(default_factory=list)


@dataclass
class ExtractedContent:
    """Complete extracted content for export."""

    project_title: str
    project_author: Optional[str]
    chapters: list[ExtractedChapter]
    toc: list[TOCEntry]

    @property
    def total_paragraphs(self) -> int:
        """Count total paragraphs."""
        return sum(len(ch.paragraphs) for ch in self.chapters)

    @property
    def translated_paragraphs(self) -> int:
        """Count paragraphs with translations."""
        count = 0
        for ch in self.chapters:
            for para in ch.paragraphs:
                if para.translated_text:
                    count += 1
        return count


class TextContentExtractor:
    """Extract text-only content for copyright-compliant exports.

    Strips all images and complex formatting while preserving:
    - Semantic structure (headings, paragraphs, lists)
    - TOC hierarchy
    - Translations
    """

    # Allowed semantic HTML tags (no images, no complex formatting)
    ALLOWED_TAGS = {
        "h1", "h2", "h3", "h4", "h5", "h6",
        "p", "blockquote",
        "ul", "ol", "li",
        "em", "strong", "br",
    }

    # Tags that indicate headings
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    async def extract(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_ids: Optional[list[str]] = None,
        include_untranslated: bool = True,
    ) -> ExtractedContent:
        """Extract text content from project.

        Args:
            db: Database session
            project_id: Project ID
            chapter_ids: Optional list of chapter IDs to include
            include_untranslated: Include paragraphs without translations

        Returns:
            ExtractedContent with all chapters and TOC
        """
        from app.models.database.project import Project

        # Get project info
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Build chapter query
        query = (
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .options(selectinload(Chapter.paragraphs).selectinload(Paragraph.translations))
            .order_by(Chapter.chapter_number)
        )

        if chapter_ids:
            query = query.where(Chapter.id.in_(chapter_ids))

        result = await db.execute(query)
        chapters = result.scalars().all()

        # Extract chapters
        extracted_chapters = []
        toc_entries = []

        for chapter in chapters:
            extracted = self._extract_chapter(chapter, include_untranslated)
            if extracted.paragraphs:  # Only include chapters with content
                extracted_chapters.append(extracted)
                toc_entries.append(TOCEntry(
                    title=chapter.title or f"Chapter {chapter.chapter_number}",
                    chapter_id=chapter.id,
                    level=0,
                ))

        return ExtractedContent(
            project_title=project.epub_title or project.name,
            project_author=project.epub_author,
            chapters=extracted_chapters,
            toc=toc_entries,
        )

    def _extract_chapter(
        self,
        chapter: Chapter,
        include_untranslated: bool,
    ) -> ExtractedChapter:
        """Extract a single chapter."""
        paragraphs = []

        for para in sorted(chapter.paragraphs, key=lambda p: p.paragraph_number):
            # Get latest translation
            translated_text = None
            if para.translations:
                latest = max(para.translations, key=lambda t: t.created_at)
                translated_text = latest.translated_text

            # Skip untranslated if not including them
            if not include_untranslated and not translated_text:
                continue

            # Clean the text (strip any remaining HTML/images)
            original_clean = self._clean_text(para.original_text)
            translated_clean = self._clean_text(translated_text) if translated_text else None

            paragraphs.append(ExtractedParagraph(
                id=para.id,
                paragraph_number=para.paragraph_number,
                original_text=original_clean,
                translated_text=translated_clean,
                html_tag=para.html_tag,
                is_heading=para.html_tag in self.HEADING_TAGS,
            ))

        return ExtractedChapter(
            id=chapter.id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            paragraphs=paragraphs,
        )

    def _clean_text(self, text: str) -> str:
        """Clean text by removing any remaining HTML tags except allowed ones."""
        if not text:
            return ""

        # Remove image tags completely
        text = re.sub(r"<img[^>]*>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<figure[^>]*>.*?</figure>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Remove style and script tags
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def render_html(
        self,
        content: ExtractedContent,
        mode: str = "bilingual",
    ) -> str:
        """Render extracted content as clean HTML.

        Args:
            content: Extracted content
            mode: "bilingual" or "translated"

        Returns:
            Complete HTML document string
        """
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="UTF-8">',
            f"<title>{html_escape(content.project_title)}</title>",
            "<style>",
            self._get_css(),
            "</style>",
            "</head>",
            "<body>",
        ]

        # Title page
        html_parts.append('<div class="title-page">')
        html_parts.append(f'<h1 class="book-title">{html_escape(content.project_title)}</h1>')
        if content.project_author:
            html_parts.append(f'<p class="book-author">{html_escape(content.project_author)}</p>')
        html_parts.append("</div>")

        # Table of contents
        html_parts.append('<nav class="toc">')
        html_parts.append("<h2>Contents</h2>")
        html_parts.append("<ul>")
        for entry in content.toc:
            html_parts.append(
                f'<li><a href="#chapter-{entry.chapter_id}">{html_escape(entry.title)}</a></li>'
            )
        html_parts.append("</ul>")
        html_parts.append("</nav>")

        # Chapters
        for chapter in content.chapters:
            html_parts.append(f'<section class="chapter" id="chapter-{chapter.id}">')
            if chapter.title:
                html_parts.append(f"<h2>{html_escape(chapter.title)}</h2>")

            for para in chapter.paragraphs:
                html_parts.append(self._render_paragraph(para, mode))

            html_parts.append("</section>")

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def _render_paragraph(self, para: ExtractedParagraph, mode: str) -> str:
        """Render a single paragraph as HTML."""
        tag = para.html_tag if para.html_tag in self.ALLOWED_TAGS else "p"

        if mode == "translated":
            # Translation only
            text = para.translated_text or para.original_text
            return f"<{tag}>{html_escape(text)}</{tag}>"
        else:
            # Bilingual
            parts = ['<div class="bilingual-pair">']
            parts.append(f'<div class="original">{html_escape(para.original_text)}</div>')
            if para.translated_text:
                parts.append(f'<div class="translation">{html_escape(para.translated_text)}</div>')
            else:
                parts.append('<div class="translation untranslated">[Not translated]</div>')
            parts.append("</div>")
            return "\n".join(parts)

    def _get_css(self) -> str:
        """Get minimal CSS for text-only exports."""
        return """
body {
    font-family: Georgia, "Noto Serif SC", serif;
    line-height: 1.8;
    max-width: 45em;
    margin: 0 auto;
    padding: 2em;
    color: #333;
}

.title-page {
    text-align: center;
    margin: 4em 0;
    page-break-after: always;
}

.book-title {
    font-size: 2em;
    margin-bottom: 0.5em;
}

.book-author {
    font-size: 1.2em;
    color: #666;
}

.toc {
    margin: 2em 0;
    page-break-after: always;
}

.toc h2 {
    margin-bottom: 1em;
}

.toc ul {
    list-style: none;
    padding: 0;
}

.toc li {
    margin: 0.5em 0;
}

.toc a {
    color: #333;
    text-decoration: none;
}

.toc a:hover {
    text-decoration: underline;
}

.chapter {
    margin: 2em 0;
    page-break-before: always;
}

.chapter h2 {
    margin-bottom: 1.5em;
}

.bilingual-pair {
    margin: 1em 0;
    padding: 0.5em 0;
    border-bottom: 1px solid #eee;
}

.original {
    color: #666;
    font-size: 0.95em;
}

.translation {
    color: #000;
    margin-top: 0.5em;
}

.untranslated {
    color: #999;
    font-style: italic;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 3px solid #ccc;
    color: #555;
}

@media print {
    body {
        max-width: none;
        padding: 0;
    }

    .chapter {
        page-break-before: always;
    }
}
"""

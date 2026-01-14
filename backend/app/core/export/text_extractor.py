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

        # Filter out empty strings and only apply filter if there are valid chapter IDs
        valid_chapter_ids = [cid for cid in (chapter_ids or []) if cid]
        if valid_chapter_ids:
            query = query.where(Chapter.id.in_(valid_chapter_ids))

        result = await db.execute(query)
        chapters = result.scalars().all()

        # Build chapter map for TOC
        chapter_map = {c.id: c for c in chapters}
        valid_chapter_ids = set(c.id for c in chapters)

        # Extract chapters
        extracted_chapters = []
        for chapter in chapters:
            extracted = self._extract_chapter(chapter, include_untranslated)
            if extracted.paragraphs:  # Only include chapters with content
                extracted_chapters.append(extracted)

        # Build hierarchical TOC from project's stored structure
        toc_entries = self._build_hierarchical_toc(
            project.toc_structure,
            chapter_map,
            valid_chapter_ids,
            level=0,
        )

        # If no stored TOC structure, create flat list
        if not toc_entries:
            for chapter in chapters:
                if chapter.id in {ec.id for ec in extracted_chapters}:
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

    def _build_hierarchical_toc(
        self,
        toc_items: Optional[list[dict]],
        chapter_map: dict[str, "Chapter"],
        valid_chapter_ids: set[str],
        level: int = 0,
    ) -> list[TOCEntry]:
        """Build hierarchical TOC entries from stored TOC structure."""
        if not toc_items:
            return []

        entries = []
        for item in toc_items:
            # Find matching chapter by href
            href = item.get("href", "")
            base_href = href.split("#")[0] if href else None

            # Find chapter that matches this href
            matching_chapter = None
            for chapter in chapter_map.values():
                if chapter.html_path == base_href:
                    matching_chapter = chapter
                    break

            # Build children recursively
            children = self._build_hierarchical_toc(
                item.get("children", []),
                chapter_map,
                valid_chapter_ids,
                level=level + 1,
            )

            # Include entry if it has a valid chapter or has children with content
            chapter_id = matching_chapter.id if matching_chapter else None
            has_valid_chapter = chapter_id and chapter_id in valid_chapter_ids
            has_children = len(children) > 0

            if has_valid_chapter or has_children:
                entries.append(TOCEntry(
                    title=item.get("title", "Untitled"),
                    chapter_id=chapter_id or "",
                    level=level,
                    children=children,
                ))

        return entries

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
        """Render extracted content as clean HTML with navigation sidebar.

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
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"<title>{html_escape(content.project_title)}</title>",
            "<style>",
            self._get_css(),
            "</style>",
            "</head>",
            "<body>",
        ]

        # Navigation sidebar
        html_parts.append('<nav class="sidebar" id="sidebar">')
        html_parts.append('<div class="sidebar-header">')
        html_parts.append(f'<h3>{html_escape(content.project_title)}</h3>')
        html_parts.append('<button class="sidebar-toggle" onclick="toggleSidebar()">&times;</button>')
        html_parts.append('</div>')
        html_parts.append('<ul class="nav-list">')
        self._render_nav_entries(html_parts, content.toc)
        html_parts.append('</ul>')
        html_parts.append('</nav>')

        # Toggle button for collapsed sidebar
        html_parts.append('<button class="sidebar-open" id="sidebar-open" onclick="toggleSidebar()">')
        html_parts.append('<span>&#9776;</span>')
        html_parts.append('</button>')

        # Main content
        html_parts.append('<main class="content">')

        # Title page
        html_parts.append('<div class="title-page">')
        html_parts.append(f'<h1 class="book-title">{html_escape(content.project_title)}</h1>')
        if content.project_author:
            html_parts.append(f'<p class="book-author">{html_escape(content.project_author)}</p>')
        html_parts.append("</div>")

        # Chapters
        for chapter in content.chapters:
            html_parts.append(f'<section class="chapter" id="chapter-{chapter.id}">')
            if chapter.title:
                html_parts.append(f"<h2>{html_escape(chapter.title)}</h2>")

            for para in chapter.paragraphs:
                html_parts.append(self._render_paragraph(para, mode))

            html_parts.append("</section>")

        html_parts.append('</main>')

        # JavaScript for navigation
        html_parts.append('<script>')
        html_parts.append(self._get_nav_script())
        html_parts.append('</script>')

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

    def _render_nav_entries(self, html_parts: list[str], toc_entries: list[TOCEntry]) -> None:
        """Render hierarchical navigation entries as nested HTML lists.

        Args:
            html_parts: List to append HTML strings to
            toc_entries: List of TOCEntry objects to render
        """
        for entry in toc_entries:
            html_parts.append('<li>')
            # Only add link if entry has a chapter_id (some parent entries may not)
            if entry.chapter_id:
                html_parts.append(
                    f'<a href="#chapter-{entry.chapter_id}" '
                    f'class="nav-link" data-level="{entry.level}">'
                    f'{html_escape(entry.title)}</a>'
                )
            else:
                # Parent entry without chapter - render as non-clickable text
                html_parts.append(
                    f'<span class="nav-parent" data-level="{entry.level}">'
                    f'{html_escape(entry.title)}</span>'
                )

            # Render children recursively
            if entry.children:
                html_parts.append('<ul class="nav-sublist">')
                self._render_nav_entries(html_parts, entry.children)
                html_parts.append('</ul>')

            html_parts.append('</li>')

    def _get_css(self) -> str:
        """Get CSS for text-only exports with navigation sidebar."""
        return """
* {
    box-sizing: border-box;
}

body {
    font-family: Georgia, "Noto Serif SC", serif;
    line-height: 1.8;
    margin: 0;
    padding: 0;
    color: #333;
    display: flex;
}

/* Sidebar Navigation */
.sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 280px;
    height: 100vh;
    background: #f8f9fa;
    border-right: 1px solid #e0e0e0;
    overflow-y: auto;
    z-index: 1000;
    transition: transform 0.3s ease;
}

.sidebar.collapsed {
    transform: translateX(-100%);
}

.sidebar-header {
    position: sticky;
    top: 0;
    background: #f8f9fa;
    padding: 1em;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sidebar-header h3 {
    margin: 0;
    font-size: 1em;
    color: #333;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
}

.sidebar-toggle {
    background: none;
    border: none;
    font-size: 1.5em;
    cursor: pointer;
    color: #666;
    padding: 0 0.25em;
}

.sidebar-toggle:hover {
    color: #333;
}

.nav-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.nav-list li {
    border-bottom: 1px solid #eee;
}

.nav-link, .nav-parent {
    display: block;
    padding: 0.75em 1em;
    color: #555;
    text-decoration: none;
    font-size: 0.9em;
    transition: background 0.2s;
}

.nav-parent {
    font-weight: 600;
    color: #333;
}

.nav-link:hover {
    background: #e9ecef;
    color: #333;
}

.nav-link.active {
    background: #e3f2fd;
    color: #1976d2;
    border-left: 3px solid #1976d2;
}

/* Nested navigation for hierarchy */
.nav-sublist {
    list-style: none;
    padding: 0;
    margin: 0;
}

.nav-sublist li {
    border-bottom: 1px solid #f5f5f5;
}

.nav-sublist .nav-link, .nav-sublist .nav-parent {
    padding-left: 2em;
    font-size: 0.85em;
}

.nav-sublist .nav-sublist .nav-link, .nav-sublist .nav-sublist .nav-parent {
    padding-left: 3em;
    font-size: 0.8em;
}

.nav-sublist .nav-sublist .nav-sublist .nav-link {
    padding-left: 4em;
    font-size: 0.75em;
}

/* Sidebar open button (when collapsed) */
.sidebar-open {
    position: fixed;
    left: 10px;
    top: 10px;
    z-index: 999;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 1.2em;
    display: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.sidebar-open.visible {
    display: block;
}

/* Main content */
.content {
    flex: 1;
    margin-left: 280px;
    max-width: 50em;
    padding: 2em 3em;
    transition: margin-left 0.3s ease;
}

.content.expanded {
    margin-left: 0;
}

.title-page {
    text-align: center;
    margin: 4em 0;
    padding-bottom: 2em;
    border-bottom: 2px solid #eee;
}

.book-title {
    font-size: 2em;
    margin-bottom: 0.5em;
}

.book-author {
    font-size: 1.2em;
    color: #666;
}

.chapter {
    margin: 2em 0;
    padding-top: 1em;
}

.chapter h2 {
    margin-bottom: 1.5em;
    padding-bottom: 0.5em;
    border-bottom: 1px solid #eee;
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

/* Responsive */
@media (max-width: 900px) {
    .sidebar {
        transform: translateX(-100%);
    }
    .sidebar.open {
        transform: translateX(0);
    }
    .sidebar-open {
        display: block;
    }
    .content {
        margin-left: 0;
        padding: 1em;
    }
}

@media print {
    .sidebar, .sidebar-open {
        display: none !important;
    }
    .content {
        margin-left: 0;
        max-width: none;
        padding: 0;
    }
    .chapter {
        page-break-before: always;
    }
}
"""

    def _get_nav_script(self) -> str:
        """Get JavaScript for navigation functionality."""
        return """
// Toggle sidebar visibility
function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    var content = document.querySelector('.content');
    var openBtn = document.getElementById('sidebar-open');

    sidebar.classList.toggle('collapsed');
    content.classList.toggle('expanded');
    openBtn.classList.toggle('visible');
}

// Build a map of chapter IDs to their nav links for quick lookup
var navLinkMap = {};
document.querySelectorAll('.nav-link').forEach(function(link) {
    var href = link.getAttribute('href');
    if (href && href.startsWith('#chapter-')) {
        var chapterId = href.substring(9); // Remove '#chapter-'
        navLinkMap[chapterId] = link;
    }
});

// Highlight active chapter on scroll
function highlightActiveChapter() {
    var chapters = document.querySelectorAll('.chapter');
    var scrollPos = window.scrollY + 100;
    var activeChapterId = null;

    chapters.forEach(function(chapter) {
        var rect = chapter.getBoundingClientRect();
        var top = rect.top + window.scrollY;
        var bottom = top + rect.height;

        if (scrollPos >= top && scrollPos < bottom) {
            // Extract chapter ID from element ID (format: "chapter-{id}")
            var id = chapter.getAttribute('id');
            if (id && id.startsWith('chapter-')) {
                activeChapterId = id.substring(8);
            }
        }
    });

    // Update active state using the map
    document.querySelectorAll('.nav-link').forEach(function(link) {
        link.classList.remove('active');
    });

    if (activeChapterId && navLinkMap[activeChapterId]) {
        navLinkMap[activeChapterId].classList.add('active');
        // Scroll nav item into view if needed
        navLinkMap[activeChapterId].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
}

// Smooth scroll to chapter when clicking nav link
document.querySelectorAll('.nav-link').forEach(function(link) {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        var targetId = this.getAttribute('href').substring(1);
        var target = document.getElementById(targetId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
            // Update active state
            document.querySelectorAll('.nav-link').forEach(function(l) { l.classList.remove('active'); });
            this.classList.add('active');
        }
    });
});

// Listen for scroll events
window.addEventListener('scroll', highlightActiveChapter);

// Initial highlight
highlightActiveChapter();
"""

"""Text-only ePub generator for copyright-compliant exports.

Generates minimal ePub files with text and TOC only, no images or complex formatting.
"""

import uuid
from io import BytesIO
from html import escape as html_escape

from ebooklib import epub

from app.core.export.text_extractor import ExtractedContent, ExtractedChapter


class TextOnlyEpubGenerator:
    """Generate text-only ePub files.

    Creates minimal ePub 3 files with:
    - Text content only (no images)
    - Clean TOC navigation
    - Minimal CSS styling
    - Bilingual or translation-only modes
    """

    def generate(
        self,
        content: ExtractedContent,
        mode: str = "bilingual",
    ) -> bytes:
        """Generate ePub file from extracted content.

        Args:
            content: Extracted content from TextContentExtractor
            mode: "bilingual" or "translated"

        Returns:
            ePub file as bytes
        """
        book = epub.EpubBook()

        # Set metadata
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(content.project_title)
        book.set_language("zh" if mode == "translated" else "en")

        if content.project_author:
            book.add_author(content.project_author)

        # Add CSS
        css = epub.EpubItem(
            uid="style",
            file_name="style/main.css",
            media_type="text/css",
            content=self._get_css().encode("utf-8"),
        )
        book.add_item(css)

        # Create chapters
        epub_chapters = []
        toc_items = []

        for chapter in content.chapters:
            epub_chapter = self._create_chapter(chapter, mode, css)
            book.add_item(epub_chapter)
            epub_chapters.append(epub_chapter)
            toc_items.append(epub.Link(
                epub_chapter.file_name,
                chapter.title or f"Chapter {chapter.chapter_number}",
                epub_chapter.id,
            ))

        # Set TOC and spine
        book.toc = toc_items
        book.spine = ["nav"] + epub_chapters

        # Add navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Write to bytes
        output = BytesIO()
        epub.write_epub(output, book)
        return output.getvalue()

    def _create_chapter(
        self,
        chapter: ExtractedChapter,
        mode: str,
        css: epub.EpubItem,
    ) -> epub.EpubHtml:
        """Create an ePub chapter from extracted chapter."""
        chapter_id = f"chapter_{chapter.chapter_number}"

        epub_chapter = epub.EpubHtml(
            title=chapter.title or f"Chapter {chapter.chapter_number}",
            file_name=f"{chapter_id}.xhtml",
            lang="zh" if mode == "translated" else "en",
        )
        epub_chapter.add_item(css)

        # Build HTML content
        html_parts = []

        if chapter.title:
            html_parts.append(f"<h1>{html_escape(chapter.title)}</h1>")

        for para in chapter.paragraphs:
            html_parts.append(self._render_paragraph(para, mode))

        epub_chapter.content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{html_escape(chapter.title or '')}</title>
    <link rel="stylesheet" type="text/css" href="style/main.css"/>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""

        return epub_chapter

    def _render_paragraph(self, para: "ExtractedParagraph", mode: str) -> str:
        """Render a paragraph as XHTML."""
        from app.core.export.text_extractor import ExtractedParagraph

        if mode == "translated":
            # Translation only
            text = para.translated_text or para.original_text
            tag = "h2" if para.is_heading else "p"
            return f"<{tag}>{html_escape(text)}</{tag}>\n"
        else:
            # Bilingual mode
            parts = ['<div class="bilingual-pair">']
            parts.append(f'<p class="original">{html_escape(para.original_text)}</p>')
            if para.translated_text:
                parts.append(f'<p class="translation">{html_escape(para.translated_text)}</p>')
            else:
                parts.append('<p class="translation untranslated">[Not translated]</p>')
            parts.append("</div>\n")
            return "".join(parts)

    def _get_css(self) -> str:
        """Get minimal CSS for ePub."""
        return """
body {
    font-family: Georgia, serif;
    line-height: 1.8;
    margin: 1em;
}

h1 {
    font-size: 1.5em;
    text-align: center;
    margin: 2em 0 1em 0;
}

h2 {
    font-size: 1.2em;
    margin: 1.5em 0 0.5em 0;
}

p {
    margin: 0.5em 0;
    text-indent: 2em;
}

.bilingual-pair {
    margin: 1em 0;
    padding-bottom: 0.5em;
    border-bottom: 1px solid #ddd;
}

.original {
    color: #666;
    font-size: 0.95em;
    text-indent: 0;
}

.translation {
    color: #000;
    margin-top: 0.3em;
    text-indent: 0;
}

.untranslated {
    color: #999;
    font-style: italic;
}

blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 2px solid #ccc;
    font-style: italic;
}
"""

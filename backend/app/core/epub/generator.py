"""EPUB Generator - Create bilingual EPUB files."""

from pathlib import Path
from typing import Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.database.project import Project
from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph


class EPUBGenerator:
    """Generate bilingual EPUB from translated content."""

    def __init__(self, project_id: str, db: AsyncSession):
        self.project_id = project_id
        self.db = db

    async def generate(self) -> Path:
        """Generate bilingual EPUB file."""
        # Load project with all related data
        result = await self.db.execute(
            select(Project)
            .where(Project.id == self.project_id)
            .options(
                selectinload(Project.chapters)
                .selectinload(Chapter.paragraphs)
                .selectinload(Paragraph.translations)
            )
        )
        project = result.scalar_one()

        # Read original EPUB
        original_book = epub.read_epub(project.original_file_path)

        # Create new EPUB
        book = epub.EpubBook()

        # Copy metadata
        book.set_identifier(f"bilingual-{project.id}")
        book.set_title(f"{project.epub_title} (Bilingual)")
        book.set_language("zh")
        book.add_author(project.epub_author or "Unknown")

        # Add CSS for bilingual layout
        bilingual_css = epub.EpubItem(
            uid="bilingual_style",
            file_name="style/bilingual.css",
            media_type="text/css",
            content=self._get_bilingual_css(),
        )
        book.add_item(bilingual_css)

        # Process each chapter
        chapters_for_spine = []
        chapters_for_toc = []

        for chapter in sorted(project.chapters, key=lambda c: c.chapter_number):
            # Generate bilingual HTML
            bilingual_html = await self._generate_bilingual_chapter(chapter)

            # Create EPUB chapter
            epub_chapter = epub.EpubHtml(
                title=chapter.title or f"Chapter {chapter.chapter_number}",
                file_name=chapter.html_path,
                lang="zh",
            )
            epub_chapter.content = bilingual_html
            epub_chapter.add_item(bilingual_css)

            book.add_item(epub_chapter)
            chapters_for_spine.append(epub_chapter)
            chapters_for_toc.append(epub_chapter)

        # Copy non-document items (images, styles, etc.)
        for item in original_book.get_items():
            if item.get_type() in [ebooklib.ITEM_IMAGE, ebooklib.ITEM_FONT]:
                book.add_item(item)

        # Set table of contents and spine
        book.toc = chapters_for_toc
        book.spine = ["nav"] + chapters_for_spine

        # Add navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Write EPUB
        output_path = settings.output_dir / f"{project.id}_bilingual.epub"
        epub.write_epub(str(output_path), book)

        return output_path

    async def _generate_bilingual_chapter(self, chapter: Chapter) -> str:
        """Generate bilingual HTML content for a chapter."""
        # Parse original HTML
        soup = BeautifulSoup(chapter.original_html, "lxml")
        body = soup.find("body")

        if not body:
            return chapter.original_html

        # Build paragraph lookup by text (for matching)
        para_translations = {}
        for para in chapter.paragraphs:
            latest = para.latest_translation
            if latest:
                para_translations[para.original_text] = latest.translated_text

        # Process each text element
        for tag_name in ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]:
            for tag in body.find_all(tag_name):
                original_text = tag.get_text(strip=True)

                if original_text in para_translations:
                    translated_text = para_translations[original_text]

                    # Create bilingual container
                    container = soup.new_tag("div")
                    container["class"] = "bilingual-pair"

                    # Original text
                    en_div = soup.new_tag("div")
                    en_div["class"] = "original-text"
                    en_div["lang"] = "en"
                    en_p = soup.new_tag(tag.name)
                    en_p.string = original_text
                    en_div.append(en_p)

                    # Translated text
                    cn_div = soup.new_tag("div")
                    cn_div["class"] = "translated-text"
                    cn_div["lang"] = "zh"
                    cn_p = soup.new_tag(tag.name)
                    cn_p.string = translated_text
                    cn_div.append(cn_p)

                    container.append(en_div)
                    container.append(cn_div)

                    # Replace original tag
                    tag.replace_with(container)

        return str(soup)

    async def generate_preview(self, chapter_id: Optional[str] = None) -> str:
        """Generate HTML preview of bilingual content."""
        if chapter_id:
            result = await self.db.execute(
                select(Chapter)
                .where(Chapter.id == chapter_id)
                .options(
                    selectinload(Chapter.paragraphs)
                    .selectinload(Paragraph.translations)
                )
            )
            chapters = [result.scalar_one()]
        else:
            result = await self.db.execute(
                select(Chapter)
                .where(Chapter.project_id == self.project_id)
                .options(
                    selectinload(Chapter.paragraphs)
                    .selectinload(Paragraph.translations)
                )
                .order_by(Chapter.chapter_number)
            )
            chapters = result.scalars().all()

        html_parts = [
            "<html><head>",
            "<style>",
            self._get_bilingual_css().decode("utf-8"),
            "</style>",
            "</head><body>",
        ]

        for chapter in chapters:
            html_parts.append(await self._generate_bilingual_chapter(chapter))

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _get_bilingual_css(self) -> bytes:
        """Get CSS styles for bilingual layout."""
        css = """
        .bilingual-pair {
            margin-bottom: 1.5em;
            padding: 0.5em;
            border-left: 3px solid #e0e0e0;
        }

        .original-text {
            color: #333;
            margin-bottom: 0.5em;
        }

        .translated-text {
            color: #0066cc;
            font-style: italic;
        }

        .original-text p,
        .translated-text p {
            margin: 0;
        }

        /* Headings */
        .bilingual-pair h1,
        .bilingual-pair h2,
        .bilingual-pair h3 {
            margin: 0.25em 0;
        }

        /* Responsive */
        @media (min-width: 768px) {
            .bilingual-pair {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1em;
                border-left: none;
                border-bottom: 1px solid #e0e0e0;
            }

            .translated-text {
                font-style: normal;
            }
        }
        """
        return css.encode("utf-8")

"""EPUB Generator - Create bilingual EPUB files."""

import base64
import os
from pathlib import Path
from typing import Dict, Optional

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

    def __init__(self, project_id: str, db: AsyncSession, output_dir: Optional[Path] = None):
        self.project_id = project_id
        self.db = db
        self.output_dir = output_dir or settings.output_dir
        self._image_cache: Dict[str, str] = {}  # Cache for base64 encoded images

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
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{project.id}_bilingual.epub"
        epub.write_epub(str(output_path), book)

        return output_path

    async def _generate_bilingual_chapter(
        self,
        chapter: Chapter,
        embed_images: bool = False,
        image_map: Optional[Dict[str, str]] = None,
        filter_copyright: bool = False,
    ) -> str:
        """Generate bilingual HTML content for a chapter.

        Args:
            chapter: The chapter to process
            embed_images: If True, convert images to base64 data URLs (for preview)
            image_map: Pre-loaded map of image paths to base64 data URLs
            filter_copyright: If True, only include proofreadable paragraphs
        """
        # Parse original HTML
        soup = BeautifulSoup(chapter.original_html or "", "lxml")
        body = soup.find("body")

        if not body:
            return chapter.original_html or ""

        # For preview, extract only the body content (avoid nested html/head/body)
        if embed_images:
            # Get inner content of body, not the body tag itself
            body_content = "".join(str(child) for child in body.children)
            # Re-parse just the body content
            soup = BeautifulSoup(f"<div>{body_content}</div>", "lxml")
            body = soup.find("div")

        # Handle images based on context
        if embed_images and image_map:
            # Convert image src to base64 data URLs for preview
            # Handle regular <img> tags
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if src and not src.startswith("data:"):
                    data_url = self._find_image_in_map(src, chapter.html_path, image_map)
                    if data_url:
                        img["src"] = data_url

            # Handle SVG <image> tags with xlink:href (common for EPUB covers)
            for img in soup.find_all("image"):
                # SVG image elements use xlink:href or href
                src = img.get("xlink:href") or img.get("href", "")
                if src and not src.startswith("data:"):
                    data_url = self._find_image_in_map(src, chapter.html_path, image_map)
                    if data_url:
                        # Update both xlink:href and href for compatibility
                        if img.get("xlink:href"):
                            img["xlink:href"] = data_url
                        if img.get("href"):
                            img["href"] = data_url
        elif not embed_images:
            # For EPUB generation, keep images as-is (they're handled separately)
            pass

        # Build paragraph lookup by text (for matching)
        # When filter_copyright is True, only include proofreadable paragraphs
        para_translations = {}
        proofreadable_texts = set()
        for para in chapter.paragraphs:
            if filter_copyright and not para.is_proofreadable:
                continue
            proofreadable_texts.add(para.original_text)
            latest = para.latest_translation
            if latest:
                para_translations[para.original_text] = latest.translated_text

        # Process each text element
        for tag_name in ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]:
            for tag in body.find_all(tag_name):
                original_text = tag.get_text(strip=True)

                # Skip empty tags
                if not original_text:
                    continue

                # Skip non-proofreadable content when filter_copyright is enabled
                if filter_copyright and original_text not in proofreadable_texts:
                    # Remove the tag entirely (copyright/image caption content)
                    tag.decompose()
                    continue

                # Check if we have a translation for this paragraph
                has_translation = original_text in para_translations
                translated_text = para_translations.get(original_text, "")

                # Create bilingual container (always wrap for consistent filtering)
                container = soup.new_tag("div")
                container_classes = ["bilingual-pair"]
                if not has_translation:
                    container_classes.append("untranslated")
                container["class"] = " ".join(container_classes)

                # Original text
                en_div = soup.new_tag("div")
                en_div["class"] = "original-text"
                en_div["lang"] = "en"
                en_p = soup.new_tag(tag.name)
                en_p.string = original_text
                en_div.append(en_p)

                # Translated text (only add if we have a translation)
                if has_translation:
                    cn_div = soup.new_tag("div")
                    cn_div["class"] = "translated-text"
                    cn_div["lang"] = "zh"
                    cn_p = soup.new_tag(tag.name)
                    cn_p.string = translated_text
                    cn_div.append(cn_p)

                container.append(en_div)
                if has_translation:
                    container.append(cn_div)

                # Replace original tag
                tag.replace_with(container)

        # For preview mode, return just the body content (the wrapping div)
        if embed_images and body:
            return str(body)
        return str(soup)

    def _find_image_in_map(
        self, src: str, chapter_path: Optional[str], image_map: Dict[str, str]
    ) -> Optional[str]:
        """Find an image in the image map using multiple matching strategies.

        Args:
            src: The src/href attribute from the image tag
            chapter_path: The path of the chapter HTML file in the EPUB
            image_map: Map of image paths to base64 data URLs

        Returns:
            The base64 data URL if found, None otherwise
        """
        # Strategy 1: Direct match
        if src in image_map:
            return image_map[src]

        # Strategy 2: Normalize the path using chapter location
        if chapter_path:
            normalized_src = self._normalize_image_path(src, chapter_path)
            if normalized_src in image_map:
                return image_map[normalized_src]

        # Strategy 3: Try just the filename
        filename = os.path.basename(src)
        if filename in image_map:
            return image_map[filename]

        # Strategy 4: Try stripping leading ./ and ../
        clean_src = src
        while clean_src.startswith("./") or clean_src.startswith("../"):
            if clean_src.startswith("./"):
                clean_src = clean_src[2:]
            elif clean_src.startswith("../"):
                clean_src = clean_src[3:]
        if clean_src in image_map:
            return image_map[clean_src]

        return None

    def _normalize_image_path(self, src: str, chapter_path: str) -> str:
        """Normalize image path relative to the EPUB root.

        Args:
            src: The src attribute from the img tag
            chapter_path: The path of the chapter HTML file in the EPUB
        """
        if src.startswith("data:") or src.startswith("http"):
            return src

        # Get the directory of the chapter
        chapter_dir = os.path.dirname(chapter_path)

        # Resolve relative path
        if src.startswith("../"):
            # Go up from chapter directory and resolve
            full_path = os.path.normpath(os.path.join(chapter_dir, src))
        elif src.startswith("./"):
            full_path = os.path.normpath(os.path.join(chapter_dir, src[2:]))
        elif not src.startswith("/"):
            full_path = os.path.normpath(os.path.join(chapter_dir, src))
        else:
            full_path = src.lstrip("/")

        return full_path

    async def _load_images_from_epub(self, epub_path: str) -> Dict[str, str]:
        """Load all images from the EPUB and convert to base64 data URLs.

        Returns:
            Dict mapping image file paths to base64 data URLs
        """
        image_map = {}

        try:
            book = epub.read_epub(epub_path)

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    file_name = item.get_name()
                    content = item.get_content()
                    media_type = item.media_type or "image/jpeg"

                    # Convert to base64 data URL
                    b64_content = base64.b64encode(content).decode("utf-8")
                    data_url = f"data:{media_type};base64,{b64_content}"

                    # Store with multiple path variations for robust matching
                    # 1. Full path as-is
                    image_map[file_name] = data_url

                    # 2. Just the filename
                    basename = os.path.basename(file_name)
                    image_map[basename] = data_url

                    # 3. With ../ prefix (common in EPUB HTML)
                    image_map[f"../{file_name}"] = data_url

                    # 4. Without leading directories
                    if "/" in file_name:
                        # e.g., "images/00001.jpeg" -> also store as-is
                        pass  # Already stored above

        except Exception as e:
            # Log error but don't fail - preview will just have missing images
            print(f"Error loading images from EPUB: {e}")

        return image_map

    async def generate_preview(
        self,
        chapter_id: Optional[str] = None,
        width: str = "medium",
        strip_images: bool = False,
        filter_copyright: bool = False,
    ) -> str:
        """Generate HTML preview of bilingual content.

        Args:
            chapter_id: Optional chapter ID to preview specific chapter
            width: Content width option (narrow/medium/wide/full)
            strip_images: If True, remove all images from the preview
            filter_copyright: If True, filter out non-proofreadable paragraphs
        """
        # Load project to get the original EPUB path
        result = await self.db.execute(
            select(Project).where(Project.id == self.project_id)
        )
        project = result.scalar_one_or_none()

        # Load images from original EPUB for preview (unless stripping)
        image_map: Dict[str, str] = {}
        if not strip_images and project and project.original_file_path:
            image_map = await self._load_images_from_epub(project.original_file_path)

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
            self._get_bilingual_css(width=width).decode("utf-8"),
            "</style>",
            "</head><body>",
        ]

        for chapter in chapters:
            chapter_html = await self._generate_bilingual_chapter(
                chapter,
                embed_images=not strip_images,
                image_map=image_map,
                filter_copyright=filter_copyright,
            )
            # Strip images from HTML if requested
            if strip_images:
                chapter_html = self._strip_images_from_html(chapter_html)
            html_parts.append(chapter_html)

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _strip_images_from_html(self, html: str) -> str:
        """Remove all image elements from HTML content.

        Removes: <img>, <figure>, <svg>, <image>, <picture> tags
        """
        import re
        # Remove <img> tags (self-closing or not)
        html = re.sub(r'<img[^>]*/?>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove <figure> tags with content
        html = re.sub(r'<figure[^>]*>.*?</figure>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove <picture> tags with content
        html = re.sub(r'<picture[^>]*>.*?</picture>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove <svg> tags with content
        html = re.sub(r'<svg[^>]*>.*?</svg>', '', html, flags=re.IGNORECASE | re.DOTALL)
        return html

    def _get_bilingual_css(self, width: str = "medium") -> bytes:
        """Get CSS styles for bilingual layout.

        Args:
            width: Content width option (narrow/medium/wide/full)
        """
        # Width mappings
        width_map = {
            "narrow": "600px",
            "medium": "800px",
            "wide": "1000px",
            "full": "100%",
        }
        max_width = width_map.get(width, "800px")

        css = f"""
        body {{
            max-width: {max_width};
            margin: 0;
            padding: 1em 2em;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            background-color: #fafafa;
        }}

        .bilingual-pair {{
            margin-bottom: 1.5em;
            padding: 0.5em 0;
            border-bottom: 1px solid #e0e0e0;
        }}

        .original-text {{
            color: #333;
            margin-bottom: 0.5em;
        }}

        .translated-text {{
            color: #0066cc;
        }}

        .original-text p,
        .translated-text p {{
            margin: 0;
        }}

        /* Headings */
        .bilingual-pair h1,
        .bilingual-pair h2,
        .bilingual-pair h3,
        .bilingual-pair h4,
        .bilingual-pair h5,
        .bilingual-pair h6 {{
            margin: 0.25em 0;
        }}

        /* Images centered */
        img, svg {{
            display: block;
            margin: 1em auto;
            max-width: 100%;
        }}
        """
        return css.encode("utf-8")


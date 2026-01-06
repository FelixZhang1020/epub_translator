"""EPUB Parser - Extract content from EPUB files."""

import re
from pathlib import Path
from typing import Optional, Any

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph


class EPUBParser:
    """Parse EPUB files and extract structured content."""

    # Tags that contain translatable text
    TEXT_TAGS = {
        "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "blockquote", "figcaption",
        "dt", "dd",  # Definition lists
        "caption",   # Table captions
        "th", "td",  # Table cells (may contain important content)
    }

    # Block-level container tags that may have direct text content
    CONTAINER_TAGS = {"div", "section", "article", "aside"}

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.book = epub.read_epub(str(self.file_path))

    async def get_metadata(self) -> dict:
        """Extract EPUB metadata."""
        metadata = {}

        # Title
        title = self.book.get_metadata("DC", "title")
        if title:
            metadata["title"] = title[0][0]

        # Author
        creator = self.book.get_metadata("DC", "creator")
        if creator:
            metadata["author"] = creator[0][0]

        # Language
        language = self.book.get_metadata("DC", "language")
        if language:
            metadata["language"] = language[0][0]

        # Description
        description = self.book.get_metadata("DC", "description")
        if description:
            metadata["description"] = description[0][0]

        # Publisher
        publisher = self.book.get_metadata("DC", "publisher")
        if publisher:
            metadata["publisher"] = publisher[0][0]

        # Identifier (ISBN, etc.)
        identifier = self.book.get_metadata("DC", "identifier")
        if identifier:
            metadata["identifier"] = identifier[0][0]

        return metadata

    def extract_toc_structure(self) -> list[dict]:
        """Extract hierarchical table of contents from EPUB.

        Returns a list of TOC items, where each item has:
        - title: string
        - href: string (file path in EPUB)
        - children: list of nested items (for sections)
        """
        toc = self.book.toc
        return self._parse_toc_items(toc)

    def _parse_toc_items(self, items: Any) -> list[dict]:
        """Recursively parse TOC items into a hierarchical structure."""
        result = []

        if not items:
            return result

        for item in items:
            if isinstance(item, tuple):
                # Nested section: (Section/Link, [children])
                parent = item[0]
                children = item[1] if len(item) > 1 else []

                toc_item = {
                    "title": getattr(parent, "title", None) or str(parent),
                    "href": getattr(parent, "href", None),
                    "children": self._parse_toc_items(children),
                }
                result.append(toc_item)

            elif isinstance(item, epub.Link):
                # Simple link
                result.append({
                    "title": item.title,
                    "href": item.href,
                    "children": [],
                })

            elif isinstance(item, epub.Section):
                # Section without children (unusual but possible)
                result.append({
                    "title": item.title,
                    "href": getattr(item, "href", None),
                    "children": [],
                })

            elif hasattr(item, "title"):
                # EpubHtml or other item with title
                result.append({
                    "title": item.title,
                    "href": getattr(item, "file_name", None) or getattr(item, "href", None),
                    "children": [],
                })

        return result

    async def extract_chapters(self) -> list[dict]:
        """Extract all chapters with their content."""
        chapters = []
        chapter_number = 0

        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content().decode("utf-8")
                soup = BeautifulSoup(content, "lxml")

                # Extract title from heading or filename
                title = self._extract_title(soup, item.get_name())

                # Skip empty or very short content (like cover pages)
                body = soup.find("body")
                if not body:
                    continue

                # Use separator to get proper spacing
                text_content = body.get_text(separator=" ", strip=True)
                if len(text_content) < 50:
                    continue

                chapter_number += 1
                # Pass title to filter out redundant heading paragraphs
                paragraphs = self._extract_paragraphs(soup, chapter_title=title)

                # Extract images for this chapter
                images = self._extract_images(soup, item.get_name())

                if paragraphs:
                    chapters.append({
                        "chapter_number": chapter_number,
                        "title": title,
                        "html_path": item.get_name(),
                        "original_html": content,
                        "paragraphs": paragraphs,
                        "images": images,
                        "word_count": sum(p["word_count"] for p in paragraphs),
                    })

        return chapters

    def _extract_title(self, soup: BeautifulSoup, filename: str) -> str:
        """Extract chapter title from content or filename."""
        # Try to find title in heading tags
        # Use find_all to iterate through all headings in case the first is empty
        for tag in ["h1", "h2", "title"]:
            headings = soup.find_all(tag)
            for heading in headings:
                text = self._extract_text_smart(heading)
                if text and len(text) < 200:
                    return text

        # Fallback to filename
        name = Path(filename).stem
        # Clean up filename
        name = re.sub(r"[-_]", " ", name)
        name = re.sub(r"\d+", "", name).strip()
        return name.title() if name else "Chapter"

    def _extract_text_smart(self, element: Any) -> str:
        """Extract text from element, handling drop-cap patterns.

        This handles EPUB styling patterns where first letters are styled differently:
        1. W<small>HO</small> N<small>EEDS</small> -> "WHO NEEDS"
        2. <span class="let">W</span>hen -> "When"
        """
        # Work on a copy to avoid modifying the original
        element_copy = BeautifulSoup(str(element), "lxml")

        # Check if element has small tags (indicates drop-cap styling)
        has_small_tags = bool(element_copy.find("small"))

        # Pattern 1: Handle small tags (drop-cap pattern)
        # Unwrap all small tags - this preserves spacing in the original HTML
        for small_tag in list(element_copy.find_all("small")):
            small_tag.unwrap()

        if has_small_tags:
            # For drop-cap content, extract without separator to preserve original spacing
            # e.g., W<small>HO</small> I<small>S</small> -> "WHO IS"
            text = element_copy.get_text()
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()
        else:
            # For normal content without drop-caps, use separator for better spacing
            text = element_copy.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)

        # Pattern 2: Handle span tags containing single capital letters
        # e.g., <span class="let">W</span>hen -> When
        element_copy2 = BeautifulSoup(str(element), "lxml")
        has_dropcap_span = False

        for span_tag in list(element_copy2.find_all("span")):
            span_text = span_tag.get_text().strip()
            if len(span_text) == 1 and span_text.isupper():
                # Check if next sibling starts with lowercase
                next_sibling = span_tag.next_sibling
                if next_sibling and isinstance(next_sibling, str):
                    next_text = next_sibling.lstrip()
                    if next_text and next_text[0].islower():
                        # Merge: <span>W</span>hen -> When
                        next_sibling.extract()
                        combined = span_text + str(next_sibling)
                        span_tag.replace_with(combined)
                        has_dropcap_span = True
                        continue
            span_tag.unwrap()

        # If we had span drop-cap patterns, use that extraction
        if has_dropcap_span:
            text = element_copy2.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)

        return text

    def _extract_images(self, soup: BeautifulSoup, file_path: str = "") -> list[dict]:
        """Extract images with their context from HTML.

        Returns a list of image info dicts with:
        - src: image file path (resolved to absolute path within EPUB)
        - alt: alt text (if any)
        - caption: figcaption text (if in figure)
        - position: sequential position in document
        """
        from pathlib import Path
        from posixpath import normpath, join as posix_join

        images = []
        body = soup.find("body")
        if not body:
            return images

        # Get directory of the HTML file for resolving relative paths
        file_dir = str(Path(file_path).parent) if file_path else ""

        for i, img in enumerate(body.find_all("img")):
            raw_src = img.get("src", "")
            alt = img.get("alt", "")

            # Resolve relative path to absolute path within EPUB
            if raw_src and not raw_src.startswith(('http://', 'https://', 'data:')):
                if file_dir and file_dir != '.':
                    src = normpath(posix_join(file_dir, raw_src))
                else:
                    src = normpath(raw_src)
                # Remove leading ./ if present
                if src.startswith('./'):
                    src = src[2:]
            else:
                src = raw_src

            # Check if image is in a figure with caption
            caption = ""
            figure = img.find_parent("figure")
            if figure:
                figcaption = figure.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(strip=True)

            # Skip placeholder alt texts like "Description à venir"
            if alt and alt.lower() in ("description à venir", "image", ""):
                alt = ""

            images.append({
                "src": src,
                "alt": alt,
                "caption": caption,
                "position": i,
            })

        return images

    def _extract_paragraphs(
        self, soup: BeautifulSoup, chapter_title: str = ""
    ) -> list[dict]:
        """Extract all translatable paragraphs from HTML.

        Args:
            soup: BeautifulSoup object of the HTML content
            chapter_title: The chapter title to skip if found as a redundant heading

        Returns:
            List of paragraph dicts with text and metadata
        """
        paragraphs = []
        paragraph_number = 0
        seen_texts = set()  # Track seen texts to avoid duplicates

        # Normalize chapter title for comparison
        normalized_title = re.sub(r"\s+", " ", chapter_title).strip().upper()

        body = soup.find("body")
        if not body:
            return paragraphs

        # First pass: extract from standard text tags
        for tag in body.find_all(self.TEXT_TAGS):
            # Skip if this tag is nested inside another TEXT_TAG
            # (to avoid duplicating content)
            parent = tag.parent
            while parent and parent != body:
                if parent.name in self.TEXT_TAGS:
                    break
                parent = parent.parent
            else:
                para = self._process_text_element(tag, seen_texts)
                if para:
                    # Skip heading paragraphs that just repeat the chapter title
                    # This avoids redundancy since title is shown in UI header
                    para_normalized = re.sub(r"\s+", " ", para["original_text"]).strip().upper()
                    if (
                        tag.name in ("h1", "h2", "h3")
                        and para_normalized == normalized_title
                    ):
                        continue

                    paragraph_number += 1
                    para["paragraph_number"] = paragraph_number
                    paragraphs.append(para)

        # Second pass: check container tags for direct text content
        # that wasn't captured by standard tags
        for tag in body.find_all(self.CONTAINER_TAGS):
            # Only process if the container has direct text children
            # (not just whitespace and nested elements)
            direct_text = "".join(
                child.strip() for child in tag.strings
                if child.parent == tag and child.strip()
            )
            if direct_text and len(direct_text) >= 10:
                # Check if this text is not already captured
                normalized = re.sub(r"\s+", " ", direct_text).strip()
                if normalized not in seen_texts:
                    alpha_ratio = sum(1 for c in normalized if c.isalpha()) / len(normalized)
                    if alpha_ratio >= 0.5:
                        seen_texts.add(normalized)
                        paragraph_number += 1
                        paragraphs.append({
                            "paragraph_number": paragraph_number,
                            "original_text": normalized,
                            "html_tag": tag.name,
                            "word_count": len(normalized.split()),
                        })

        return paragraphs

    def _process_text_element(
        self, tag: Any, seen_texts: set[str]
    ) -> dict | None:
        """Process a single text element and return paragraph dict if valid."""
        # Use smart extraction to handle drop-cap patterns
        text = self._extract_text_smart(tag)

        # Skip empty or very short text
        if not text or len(text) < 10:
            return None

        # Skip if we've already seen this exact text
        if text in seen_texts:
            return None

        # Skip if mostly non-text content (numbers, punctuation)
        # Use unicode-aware check for alphabetic characters
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count / len(text) < 0.5:
            return None

        seen_texts.add(text)
        return {
            "original_text": text,
            "html_tag": tag.name,
            "word_count": len(text.split()),
        }

    async def save_to_db(
        self,
        db: AsyncSession,
        project_id: str,
        chapters: list[dict],
    ) -> int:
        """Save extracted chapters and paragraphs to database."""
        total_paragraphs = 0

        for chapter_data in chapters:
            # Create chapter
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_data["chapter_number"],
                title=chapter_data["title"],
                html_path=chapter_data["html_path"],
                original_html=chapter_data["original_html"],
                word_count=chapter_data["word_count"],
                paragraph_count=len(chapter_data["paragraphs"]),
            )
            db.add(chapter)
            await db.flush()

            # Create paragraphs
            for para_data in chapter_data["paragraphs"]:
                paragraph = Paragraph(
                    chapter_id=chapter.id,
                    paragraph_number=para_data["paragraph_number"],
                    original_text=para_data["original_text"],
                    html_tag=para_data["html_tag"],
                    word_count=para_data["word_count"],
                )
                db.add(paragraph)
                total_paragraphs += 1

        return total_paragraphs


class BilingualEPUBMatcher:
    """Match paragraphs between English and Chinese EPUB files for optimization mode."""

    def __init__(self, english_path: Path | str, chinese_path: Path | str):
        self.english_parser = EPUBParser(english_path)
        self.chinese_parser = EPUBParser(chinese_path)

    async def match_paragraphs(self) -> list[dict]:
        """Match paragraphs between EN and CN EPUBs."""
        en_chapters = await self.english_parser.extract_chapters()
        cn_chapters = await self.chinese_parser.extract_chapters()

        matched = []

        # Simple matching by chapter and paragraph number
        for en_ch, cn_ch in zip(en_chapters, cn_chapters):
            en_paras = en_ch["paragraphs"]
            cn_paras = cn_ch["paragraphs"]

            for en_p, cn_p in zip(en_paras, cn_paras):
                matched.append({
                    "chapter_number": en_ch["chapter_number"],
                    "paragraph_number": en_p["paragraph_number"],
                    "english_text": en_p["original_text"],
                    "chinese_text": cn_p["original_text"],
                })

        return matched

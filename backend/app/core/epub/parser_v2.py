"""EPUB Parser V2 - lxml-based parser with full structure preservation.

This parser uses lxml for proper XML/XHTML handling and preserves:
- XPath locations for reconstruction
- Inline formatting (bold, italic, etc.)
- Document hierarchy and structure
- Images with context

Configuration options allow customization for different EPUB formats.
"""

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional, Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from lxml import etree
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.chapter import Chapter
from app.models.database.paragraph import Paragraph
from app.core.content_classifier import ContentClassifier


# =============================================================================
# Standard XML Namespaces (EPUB specification - do not modify)
# =============================================================================

# XHTML namespace
XHTML_NS = "http://www.w3.org/1999/xhtml"
XHTML_NSMAP = {"x": XHTML_NS}

# OPF namespace
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_NSMAP = {
    "opf": OPF_NS,
    "dc": DC_NS,
}

# NCX namespace for TOC
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
NCX_NSMAP = {"ncx": NCX_NS}

# SVG namespace for cover images
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


# =============================================================================
# Parser Configuration
# =============================================================================

@dataclass
class ParserConfig:
    """Configuration options for EPUB parsing.

    Adjust these values to customize parsing behavior for different EPUB formats.
    """

    # Minimum text length to be considered a paragraph (characters)
    # Set to 1 to include even single characters, 0 to include empty elements
    min_text_length: int = 1

    # Minimum ratio of alphabetic characters (0.0 to 1.0)
    # Set to 0.0 to disable this filter (useful for books with lots of numbers)
    # Set to 0.3 for lenient filtering, 0.5 for moderate
    min_alpha_ratio: float = 0.3

    # Maximum title length (characters)
    # Titles longer than this are likely paragraphs, not titles
    max_title_length: int = 300

    # Whether to skip duplicate text content
    skip_duplicates: bool = True

    # Whether to skip text that matches chapter title exactly
    skip_redundant_titles: bool = True

    # Placeholder alt texts to ignore (case-insensitive)
    # Add common placeholder texts used in EPUBs
    placeholder_alt_texts: set[str] = field(default_factory=lambda: {
        "", "description", "image", "photo", "picture", "figure",
        "description à venir", "coming soon", "placeholder",
        "cover", "cover image", "book cover",
    })

    # Tags containing translatable text content
    # Comprehensive list covering most EPUB formats
    translatable_tags: set[str] = field(default_factory=lambda: {
        # Headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # Paragraphs and blocks
        "p", "blockquote", "pre",
        # Lists
        "li", "dt", "dd",
        # Tables
        "caption", "th", "td",
        # Figures
        "figcaption",
        # Semantic HTML5
        "summary", "details",
        # Legacy elements sometimes used
        "cite", "q",
    })

    # Inline formatting tags to preserve during text extraction
    inline_formatting_tags: set[str] = field(default_factory=lambda: {
        "b", "strong", "i", "em", "u", "s", "strike", "del", "ins",
        "sub", "sup", "span", "small", "big", "mark",
        "code", "kbd", "samp", "var",
        "a",  # Links - preserve for reference
        "abbr", "acronym",
        "ruby", "rt", "rp",  # Ruby annotations (CJK)
    })

    # Container tags that may have direct text (extracted if no child translatable tags)
    container_tags: set[str] = field(default_factory=lambda: {
        "div", "section", "article", "aside", "header", "footer",
        "main", "nav", "figure",
    })

    # Tags to use for title extraction (in priority order)
    title_tags: list[str] = field(default_factory=lambda: [
        "h1", "h2", "h3", "h4", "h5", "h6", "title"
    ])


# =============================================================================
# Predefined Configuration Presets
# =============================================================================

# Default configuration - balanced settings for most EPUBs
DEFAULT_CONFIG = ParserConfig()

# Strict configuration - filters out more noise
STRICT_CONFIG = ParserConfig(
    min_text_length=10,
    min_alpha_ratio=0.5,
    skip_duplicates=True,
    skip_redundant_titles=True,
)

# Lenient configuration - includes more content (good for technical/math books)
LENIENT_CONFIG = ParserConfig(
    min_text_length=1,
    min_alpha_ratio=0.0,  # Disable alpha ratio check
    skip_duplicates=True,
    skip_redundant_titles=False,
)

# CJK configuration - optimized for Chinese/Japanese/Korean content
CJK_CONFIG = ParserConfig(
    min_text_length=1,
    min_alpha_ratio=0.0,  # CJK characters are not "alpha" in ASCII sense
    skip_duplicates=True,
    skip_redundant_titles=True,
)


@dataclass
class TranslatableSegment:
    """A segment of text that can be translated."""

    xpath: str  # XPath to locate in document
    file_path: str  # Which XHTML file
    original_html: str  # Raw HTML including tags
    original_text: str  # Plain text for translation
    html_tag: str  # p, h1, li, etc.
    context: dict = field(default_factory=dict)  # Chapter, section info
    word_count: int = 0
    has_inline_formatting: bool = False
    paragraph_number: int = 0


@dataclass
class EPUBImage:
    """An image in the EPUB."""

    src: str  # Path in EPUB
    alt: str  # Alt text (translatable)
    caption: str  # Figure caption (translatable)
    context_xpath: str  # Where in document
    file_path: str  # Which XHTML file
    position: int  # Order in document


@dataclass
class TOCItem:
    """Table of contents item."""

    title: str
    href: str
    children: list["TOCItem"] = field(default_factory=list)


class EPUBParserV2:
    """Parse EPUB while preserving full structure for reconstruction.

    Key improvements over V1:
    - Uses lxml for proper XML/XHTML handling
    - Stores XPath for element reconstruction
    - Preserves inline formatting information
    - Extracts images with context
    - Handles drop-cap patterns natively
    - Configurable parsing options for different EPUB formats

    Usage:
        # With default config
        parser = EPUBParserV2("book.epub")

        # With custom config
        config = ParserConfig(min_text_length=5, min_alpha_ratio=0.0)
        parser = EPUBParserV2("book.epub", config=config)
    """

    def __init__(self, epub_path: Path | str, config: ParserConfig | None = None):
        self.epub_path = Path(epub_path)
        self.zip_file = ZipFile(self.epub_path)
        self.config = config or DEFAULT_CONFIG

        # Parsed structure
        self.opf_path: str = ""
        self.opf_dir: str = ""
        self.manifest: dict[str, dict] = {}  # id -> {href, media-type}
        self.spine: list[str] = []  # List of item IDs in reading order
        self.metadata: dict = {}
        self.toc_path: str = ""

        self._parse_structure()

    def _parse_structure(self):
        """Parse OPF to get manifest and spine order."""
        # Find OPF file from container.xml
        container_path = "META-INF/container.xml"
        container_content = self.zip_file.read(container_path)
        container_tree = etree.fromstring(container_content)

        # Get OPF path from container
        rootfile = container_tree.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )
        if rootfile is not None:
            self.opf_path = rootfile.get("full-path", "")
            self.opf_dir = str(Path(self.opf_path).parent)
            if self.opf_dir == ".":
                self.opf_dir = ""

        # Parse OPF
        opf_content = self.zip_file.read(self.opf_path)
        opf_tree = etree.fromstring(opf_content)

        # Extract metadata
        self._parse_metadata(opf_tree)

        # Build manifest
        for item in opf_tree.findall(".//{%s}item" % OPF_NS):
            item_id = item.get("id")
            href = item.get("href")
            media_type = item.get("media-type")
            if item_id and href:
                # Resolve path relative to OPF
                full_path = self._resolve_path(href)
                self.manifest[item_id] = {
                    "href": href,
                    "full_path": full_path,
                    "media-type": media_type,
                }

                # Check for TOC
                if media_type == "application/x-dtbncx+xml":
                    self.toc_path = full_path

        # Build spine (reading order)
        for itemref in opf_tree.findall(".//{%s}itemref" % OPF_NS):
            idref = itemref.get("idref")
            if idref and idref in self.manifest:
                self.spine.append(idref)

        # Also check for nav document (EPUB3)
        nav_item = opf_tree.find(".//{%s}item[@properties='nav']" % OPF_NS)
        if nav_item is not None:
            nav_href = nav_item.get("href")
            if nav_href:
                self.toc_path = self._resolve_path(nav_href)

    def _resolve_path(self, href: str) -> str:
        """Resolve href relative to OPF directory."""
        if self.opf_dir:
            return f"{self.opf_dir}/{href}"
        return href

    def _parse_metadata(self, opf_tree: etree._Element):
        """Extract metadata from OPF."""
        metadata_elem = opf_tree.find(".//{%s}metadata" % OPF_NS)
        if metadata_elem is None:
            return

        # Title
        title = metadata_elem.find(".//{%s}title" % DC_NS)
        if title is not None and title.text:
            self.metadata["title"] = title.text

        # Creator/Author
        creator = metadata_elem.find(".//{%s}creator" % DC_NS)
        if creator is not None and creator.text:
            self.metadata["author"] = creator.text

        # Language
        language = metadata_elem.find(".//{%s}language" % DC_NS)
        if language is not None and language.text:
            self.metadata["language"] = language.text

        # Description
        description = metadata_elem.find(".//{%s}description" % DC_NS)
        if description is not None and description.text:
            self.metadata["description"] = description.text

        # Publisher
        publisher = metadata_elem.find(".//{%s}publisher" % DC_NS)
        if publisher is not None and publisher.text:
            self.metadata["publisher"] = publisher.text

        # Identifier
        identifier = metadata_elem.find(".//{%s}identifier" % DC_NS)
        if identifier is not None and identifier.text:
            self.metadata["identifier"] = identifier.text

    async def get_metadata(self) -> dict:
        """Return parsed metadata."""
        return self.metadata.copy()

    def get_spine_files(self) -> list[str]:
        """Get list of content files in reading order."""
        files = []
        for item_id in self.spine:
            if item_id in self.manifest:
                files.append(self.manifest[item_id]["full_path"])
        return files

    def _parse_xhtml(self, file_path: str) -> etree._Element:
        """Parse XHTML file with proper XML handling."""
        content = self.zip_file.read(file_path)

        # Use recover=True to handle malformed XML gracefully
        parser = etree.XMLParser(recover=True, remove_blank_text=False)
        try:
            tree = etree.fromstring(content, parser)
        except etree.XMLSyntaxError:
            # Fallback: try as HTML
            from lxml import html
            tree = html.fromstring(content)

        return tree

    def _get_element_xpath(self, element: etree._Element, root: etree._Element) -> str:
        """Generate XPath for an element relative to root."""
        path_parts = []
        current = element

        while current is not None and current != root:
            parent = current.getparent()
            if parent is None:
                break

            # Get tag name without namespace
            tag = etree.QName(current.tag).localname if current.tag else "unknown"

            # Count siblings with same tag
            siblings = [
                c for c in parent
                if etree.QName(c.tag).localname == tag
            ]
            if len(siblings) > 1:
                index = siblings.index(current) + 1
                path_parts.append(f"{tag}[{index}]")
            else:
                path_parts.append(tag)

            current = parent

        path_parts.reverse()
        return "/" + "/".join(path_parts) if path_parts else "/"

    def _extract_text_smart(self, element: etree._Element) -> str:
        """Extract text handling drop-cap patterns and inline formatting.

        Handles patterns like:
        - W<small>HAT</small> -> "WHAT"
        - <span class="let">W</span>hen -> "When"
        - <span class="dropcap">T</span>he -> "The"
        """
        # Work on a copy to avoid modifying original
        elem_copy = copy.deepcopy(element)
        has_dropcap = False

        # Check for small tags (drop-cap pattern)
        has_small_tags = elem_copy.find(".//{%s}small" % XHTML_NS) is not None
        if not has_small_tags:
            has_small_tags = elem_copy.find(".//small") is not None

        # Unwrap small tags
        for small in list(elem_copy.iter("{%s}small" % XHTML_NS)) + list(elem_copy.iter("small")):
            has_dropcap = True
            self._unwrap_element(small)

        # Handle drop-cap span pattern: <span class="let">W</span>hen
        # Look for spans containing a single capital letter followed by lowercase text
        for span in list(elem_copy.iter("{%s}span" % XHTML_NS)) + list(elem_copy.iter("span")):
            span_text = (span.text or "").strip()
            tail_text = span.tail or ""

            # Check if span contains single capital letter and tail starts with lowercase
            if (len(span_text) == 1 and span_text.isupper() and
                    tail_text and tail_text[0].islower()):
                has_dropcap = True
                # Merge: <span>W</span>hen -> When
                # Set span text to combined value and clear tail
                span.text = span_text + tail_text
                span.tail = ""
                self._unwrap_element(span)

        # Extract text - use itertext to get all text content
        text_parts = []
        for text in elem_copy.itertext():
            text_parts.append(text)

        if has_dropcap or has_small_tags:
            # For drop-cap content, join without extra spaces
            result = "".join(text_parts)
        else:
            # For normal content, join with spaces
            result = " ".join(text_parts)

        # Normalize whitespace
        result = re.sub(r"\s+", " ", result).strip()
        return result

    def _unwrap_element(self, elem: etree._Element):
        """Remove element tag but preserve its text content in parent."""
        parent = elem.getparent()
        if parent is None:
            return

        text = elem.text or ""
        tail = elem.tail or ""
        index = list(parent).index(elem)

        # Remove the element
        parent.remove(elem)

        # Add text to previous sibling's tail or parent's text
        if index > 0:
            prev = parent[index - 1]
            prev.tail = (prev.tail or "") + text + tail
        else:
            parent.text = (parent.text or "") + text + tail

    def _has_formatting(self, element: etree._Element) -> bool:
        """Check if element contains inline formatting tags."""
        for tag in self.config.inline_formatting_tags:
            # Check with and without namespace
            if element.find(f".//{{{XHTML_NS}}}{tag}") is not None:
                return True
            if element.find(f".//{tag}") is not None:
                return True
        return False

    def _is_nested_in_translatable(
        self, element: etree._Element, root: etree._Element
    ) -> bool:
        """Check if element is nested inside another translatable tag."""
        parent = element.getparent()
        while parent is not None and parent != root:
            parent_tag = etree.QName(parent.tag).localname if parent.tag else ""
            if parent_tag in self.config.translatable_tags:
                return True
            parent = parent.getparent()
        return False

    def iter_segments(
        self, file_path: str, chapter_title: str = ""
    ) -> Iterator[TranslatableSegment]:
        """Iterate through all translatable segments in a file.

        Uses configuration options for filtering:
        - min_text_length: Minimum characters for a segment
        - min_alpha_ratio: Minimum ratio of alphabetic characters
        - skip_duplicates: Whether to skip duplicate text
        - skip_redundant_titles: Whether to skip text matching chapter title
        """
        tree = self._parse_xhtml(file_path)

        # Find body
        body = tree.find(".//{%s}body" % XHTML_NS)
        if body is None:
            body = tree.find(".//body")
        if body is None:
            return

        paragraph_number = 0
        seen_texts = set()

        # Normalize chapter title for comparison (if redundant title skipping enabled)
        normalized_title = ""
        if self.config.skip_redundant_titles and chapter_title:
            normalized_title = re.sub(r"\s+", " ", chapter_title).strip().upper()

        # Extract from translatable tags
        for tag in self.config.translatable_tags:
            # Try with namespace first, then without
            elements = tree.xpath(
                f"//x:{tag}", namespaces=XHTML_NSMAP
            ) or tree.xpath(f"//{tag}")

            for elem in elements:
                # Skip if nested in another translatable tag
                if self._is_nested_in_translatable(elem, tree):
                    continue

                # Extract text
                text = self._extract_text_smart(elem)

                # Skip empty or too short text
                if not text or len(text) < self.config.min_text_length:
                    continue

                # Skip duplicates (if enabled)
                if self.config.skip_duplicates and text in seen_texts:
                    continue

                # Skip if below minimum alpha ratio (if ratio > 0)
                if self.config.min_alpha_ratio > 0 and len(text) > 0:
                    alpha_count = sum(1 for c in text if c.isalpha())
                    if alpha_count / len(text) < self.config.min_alpha_ratio:
                        continue

                # Skip redundant title paragraphs (if enabled)
                if self.config.skip_redundant_titles and normalized_title:
                    text_normalized = re.sub(r"\s+", " ", text).strip().upper()
                    if tag in self.config.title_tags and text_normalized == normalized_title:
                        continue

                seen_texts.add(text)
                paragraph_number += 1

                # Get original HTML
                original_html = etree.tostring(elem, encoding="unicode")

                # Get XPath
                xpath = self._get_element_xpath(elem, tree)

                yield TranslatableSegment(
                    xpath=xpath,
                    file_path=file_path,
                    original_html=original_html,
                    original_text=text,
                    html_tag=tag,
                    word_count=len(text.split()),
                    has_inline_formatting=self._has_formatting(elem),
                    paragraph_number=paragraph_number,
                )

    def iter_images(self, file_path: str) -> Iterator[EPUBImage]:
        """Iterate through all images in a file."""
        tree = self._parse_xhtml(file_path)

        body = tree.find(".//{%s}body" % XHTML_NS)
        if body is None:
            body = tree.find(".//body")
        if body is None:
            return

        # Find all images (both <img> and SVG <image>)
        images = tree.xpath("//x:img", namespaces=XHTML_NSMAP) or tree.xpath("//img")

        # Also find SVG images with xlink:href (used for covers)
        svg_ns = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}
        svg_images = tree.xpath("//svg:image", namespaces=svg_ns) or tree.xpath("//*[local-name()='image']")
        images = list(images) + list(svg_images)

        for position, img in enumerate(images):
            # Handle both regular img and SVG image elements
            raw_src = img.get("src", "") or img.get("{http://www.w3.org/1999/xlink}href", "")
            alt = img.get("alt", "")

            # Resolve relative path to absolute path within EPUB
            # e.g., if file_path is "text/chapter1.html" and src is "../images/cover.jpg"
            # the resolved path should be "images/cover.jpg"
            if raw_src and not raw_src.startswith(('http://', 'https://', 'data:')):
                file_dir = str(Path(file_path).parent)
                # Use posixpath for consistent path handling in zip files
                from posixpath import normpath, join as posix_join
                if file_dir and file_dir != '.':
                    src = normpath(posix_join(file_dir, raw_src))
                else:
                    src = normpath(raw_src)
                # Remove leading ./ if present
                if src.startswith('./'):
                    src = src[2:]
            else:
                src = raw_src

            # Check for figure caption
            caption = ""
            figure = img.getparent()
            while figure is not None:
                figure_tag = etree.QName(figure.tag).localname if figure.tag else ""
                if figure_tag == "figure":
                    # Look for figcaption
                    figcaption = figure.find(".//{%s}figcaption" % XHTML_NS)
                    if figcaption is None:
                        figcaption = figure.find(".//figcaption")
                    if figcaption is not None:
                        caption = self._extract_text_smart(figcaption)
                    break
                figure = figure.getparent()

            # Skip placeholder alt texts (using config)
            if alt and alt.lower() in self.config.placeholder_alt_texts:
                alt = ""

            yield EPUBImage(
                src=src,
                alt=alt,
                caption=caption,
                context_xpath=self._get_element_xpath(img, tree),
                file_path=file_path,
                position=position,
            )

    def extract_toc_structure(self) -> list[dict]:
        """Extract hierarchical table of contents."""
        if not self.toc_path:
            return []

        try:
            content = self.zip_file.read(self.toc_path)
        except KeyError:
            return []

        # Check if it's NCX (EPUB2) or nav (EPUB3)
        if self.toc_path.endswith(".ncx"):
            return self._parse_ncx_toc(content)
        else:
            return self._parse_nav_toc(content)

    def _parse_ncx_toc(self, content: bytes) -> list[dict]:
        """Parse NCX format TOC (EPUB2)."""
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(content, parser)

        nav_map = tree.find(".//{%s}navMap" % NCX_NS)
        if nav_map is None:
            return []

        return self._parse_ncx_nav_points(nav_map)

    def _parse_ncx_nav_points(self, parent: etree._Element) -> list[dict]:
        """Recursively parse NCX navPoint elements."""
        result = []

        for nav_point in parent.findall("{%s}navPoint" % NCX_NS):
            # Get label text
            label = nav_point.find("{%s}navLabel/{%s}text" % (NCX_NS, NCX_NS))
            title = label.text if label is not None and label.text else ""

            # Get content src
            content_elem = nav_point.find("{%s}content" % NCX_NS)
            href = content_elem.get("src", "") if content_elem is not None else ""

            # Resolve href relative to TOC file
            if href and not href.startswith(("http://", "https://")):
                toc_dir = str(Path(self.toc_path).parent)
                if toc_dir and toc_dir != ".":
                    href = f"{toc_dir}/{href}"

            # Parse children
            children = self._parse_ncx_nav_points(nav_point)

            result.append({
                "title": title,
                "href": href,
                "children": children,
            })

        return result

    def _parse_nav_toc(self, content: bytes) -> list[dict]:
        """Parse nav format TOC (EPUB3)."""
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(content, parser)

        # Find nav element with epub:type="toc"
        nav = tree.find(
            ".//{%s}nav[@*[local-name()='type']='toc']" % XHTML_NS
        )
        if nav is None:
            # Fallback: find any nav
            nav = tree.find(".//{%s}nav" % XHTML_NS)
        if nav is None:
            return []

        # Find the ol element
        ol = nav.find(".//{%s}ol" % XHTML_NS)
        if ol is None:
            return []

        return self._parse_nav_ol(ol)

    def _parse_nav_ol(self, ol: etree._Element) -> list[dict]:
        """Recursively parse nav ol/li elements."""
        result = []

        for li in ol.findall("{%s}li" % XHTML_NS):
            # Get link
            a = li.find("{%s}a" % XHTML_NS)
            if a is None:
                continue

            title = self._extract_text_smart(a)
            href = a.get("href", "")

            # Resolve href
            if href and not href.startswith(("http://", "https://")):
                toc_dir = str(Path(self.toc_path).parent)
                if toc_dir and toc_dir != ".":
                    href = f"{toc_dir}/{href}"

            # Parse nested ol
            nested_ol = li.find("{%s}ol" % XHTML_NS)
            children = self._parse_nav_ol(nested_ol) if nested_ol is not None else []

            result.append({
                "title": title,
                "href": href,
                "children": children,
            })

        return result

    async def extract_chapters(self) -> list[dict]:
        """Extract all chapters with their content.

        Returns list of dicts with:
        - chapter_number
        - title
        - html_path
        - original_html
        - paragraphs (list of segment dicts)
        - images (list of image dicts)
        - word_count
        """
        chapters = []
        chapter_number = 0

        for file_path in self.get_spine_files():
            try:
                tree = self._parse_xhtml(file_path)
            except Exception:
                continue

            # Get original HTML
            original_html = self.zip_file.read(file_path).decode("utf-8", errors="replace")

            # Extract title
            title = self._extract_title(tree, file_path)

            # Check for meaningful content
            body = tree.find(".//{%s}body" % XHTML_NS)
            if body is None:
                body = tree.find(".//body")
            if body is None:
                continue

            text_content = self._extract_text_smart(body)

            # Count images in this file (both <img> and SVG <image>)
            images_in_file = tree.xpath("//x:img", namespaces=XHTML_NSMAP) or tree.xpath("//img")
            svg_images = tree.xpath("//*[local-name()='image']")
            has_images = len(images_in_file) > 0 or len(svg_images) > 0

            # Skip only if completely empty (no text at all AND no images)
            # This ensures even short dedication pages like "For Kit" are included
            if len(text_content.strip()) == 0 and not has_images:
                continue

            chapter_number += 1

            # Extract segments
            paragraphs = []
            for segment in self.iter_segments(file_path, chapter_title=title):
                paragraphs.append({
                    "paragraph_number": segment.paragraph_number,
                    "original_text": segment.original_text,
                    "html_tag": segment.html_tag,
                    "word_count": segment.word_count,
                    "xpath": segment.xpath,
                    "original_html": segment.original_html,
                    "has_formatting": segment.has_inline_formatting,
                })

            # Extract images
            images = []
            for img in self.iter_images(file_path):
                images.append({
                    "src": img.src,
                    "alt": img.alt,
                    "caption": img.caption,
                    "position": img.position,
                    "xpath": img.context_xpath,
                })

            # Include chapter if it has paragraphs OR images
            if paragraphs or images:
                chapters.append({
                    "chapter_number": chapter_number,
                    "title": title,
                    "html_path": file_path,
                    "original_html": original_html,
                    "paragraphs": paragraphs,
                    "images": images,
                    "word_count": sum(p["word_count"] for p in paragraphs),
                })

        return chapters

    def _extract_title(self, tree: etree._Element, filename: str) -> str:
        """Extract chapter title from content or filename.

        Uses config.title_tags for tag priority and config.max_title_length for validation.
        """
        # Try heading tags in configured priority order
        for tag in self.config.title_tags:
            # Try with namespace
            headings = tree.xpath(f"//x:{tag}", namespaces=XHTML_NSMAP)
            if not headings:
                headings = tree.xpath(f"//{tag}")

            for heading in headings:
                text = self._extract_text_smart(heading)
                if text and len(text) < self.config.max_title_length:
                    return text

        # Fallback to filename
        name = Path(filename).stem
        name = re.sub(r"[-_]", " ", name)
        name = re.sub(r"\d+", "", name).strip()
        return name.title() if name else "Chapter"

    async def save_to_db(
        self,
        db: AsyncSession,
        project_id: str,
        chapters: list[dict],
    ) -> int:
        """Save extracted chapters and paragraphs to database."""
        total_paragraphs = 0
        total_chapters = len(chapters)
        classifier = ContentClassifier()

        for chapter_data in chapters:
            # Classify chapter type
            chapter_type = classifier.classify_chapter(
                title=chapter_data["title"],
                chapter_number=chapter_data["chapter_number"],
                total_chapters=total_chapters,
            )

            # Create chapter
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_data["chapter_number"],
                title=chapter_data["title"],
                html_path=chapter_data["html_path"],
                original_html=chapter_data["original_html"],
                word_count=chapter_data["word_count"],
                paragraph_count=len(chapter_data["paragraphs"]),
                images=chapter_data.get("images", []),
                chapter_type=chapter_type.value,
                is_proofreadable=(chapter_type.value == "main_content"),
            )
            db.add(chapter)
            await db.flush()

            # Create paragraphs
            for para_data in chapter_data["paragraphs"]:
                # Classify paragraph content type
                content_type = classifier.classify_paragraph(
                    text=para_data["original_text"],
                    html_tag=para_data["html_tag"],
                    chapter_type=chapter_type,
                )
                is_proofreadable = classifier.is_proofreadable(
                    content_type=content_type,
                    chapter_type=chapter_type,
                )

                paragraph = Paragraph(
                    chapter_id=chapter.id,
                    paragraph_number=para_data["paragraph_number"],
                    original_text=para_data["original_text"],
                    html_tag=para_data["html_tag"],
                    word_count=para_data["word_count"],
                    xpath=para_data.get("xpath"),
                    original_html=para_data.get("original_html"),
                    has_formatting=para_data.get("has_formatting", False),
                    content_type=content_type.value,
                    is_proofreadable=is_proofreadable,
                )
                db.add(paragraph)
                total_paragraphs += 1

        return total_paragraphs

    def close(self):
        """Close the ZIP file."""
        self.zip_file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

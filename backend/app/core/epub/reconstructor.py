"""EPUB Reconstructor - Build translated EPUB from original + translations.

This module creates a new EPUB file with translated content while preserving:
- All original formatting and styles
- Images and media
- TOC structure
- Metadata (with optional modification)
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree

from app.core.epub.parser_v2 import XHTML_NS, XHTML_NSMAP, OPF_NS, DC_NS


@dataclass
class TranslationMapping:
    """Maps original content to translation."""

    file_path: str  # XHTML file path in EPUB
    xpath: str  # XPath to element
    translated_text: str  # Translated text content


class EPUBReconstructor:
    """Reconstruct translated EPUB from original + translations.

    This class takes an original EPUB and a mapping of translations,
    then produces a new EPUB with translated content while preserving
    all structure, formatting, images, and styles.
    """

    def __init__(
        self,
        original_epub: Path | str,
        translations: list[TranslationMapping],
        target_language: str = "zh",
        strip_images: bool = False,
    ):
        """Initialize reconstructor.

        Args:
            original_epub: Path to original EPUB file
            translations: List of translation mappings
            target_language: Target language code (e.g., "zh", "ja")
            strip_images: If True, remove all images from the output EPUB
        """
        self.original_path = Path(original_epub)
        self.translations = translations
        self.target_language = target_language
        self.strip_images = strip_images

        # Build lookup dict: file_path -> xpath -> translated_text
        self.translation_map: dict[str, dict[str, str]] = {}
        for t in translations:
            if t.file_path not in self.translation_map:
                self.translation_map[t.file_path] = {}
            self.translation_map[t.file_path][t.xpath] = t.translated_text

    def build(self, output_path: Path | str) -> Path:
        """Build translated EPUB.

        Args:
            output_path: Path for output EPUB file

        Returns:
            Path to created EPUB file
        """
        output_path = Path(output_path)

        # Create temp directory for working
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract original EPUB
            with ZipFile(self.original_path, "r") as zip_in:
                zip_in.extractall(temp_path)

            # Process each file
            for root, dirs, files in os.walk(temp_path):
                for filename in files:
                    file_path = Path(root) / filename
                    rel_path = file_path.relative_to(temp_path)
                    rel_path_str = str(rel_path)

                    if filename.endswith((".xhtml", ".html", ".htm")):
                        # Transform content files
                        self._transform_xhtml(file_path, rel_path_str)
                    elif filename.endswith(".opf"):
                        # Update OPF metadata
                        self._update_opf(file_path)
                    elif filename.endswith(".ncx"):
                        # Update NCX TOC titles if needed
                        self._update_ncx(file_path)

            # Repack as EPUB
            self._create_epub(temp_path, output_path)

        return output_path

    def _transform_xhtml(self, file_path: Path, rel_path: str):
        """Transform XHTML file with translations.

        Args:
            file_path: Absolute path to file
            rel_path: Relative path in EPUB (for translation lookup)
        """
        # Get translations for this file
        file_translations = self.translation_map.get(rel_path, {})

        # Parse XHTML (always parse if we need to strip images)
        if not file_translations and not self.strip_images:
            return  # No translations and no image stripping needed

        content = file_path.read_bytes()
        parser = etree.XMLParser(recover=True, remove_blank_text=False)

        try:
            tree = etree.fromstring(content, parser)
        except etree.XMLSyntaxError:
            # Fallback: try as HTML
            from lxml import html
            tree = html.fromstring(content)

        modified = False

        # Strip images if requested
        if self.strip_images:
            modified = self._strip_images_from_tree(tree) or modified

        # Apply translations
        for xpath, translated_text in file_translations.items():
            try:
                # Try to find element by xpath
                elements = self._find_by_xpath(tree, xpath)
                if elements:
                    elem = elements[0]
                    self._replace_text_content(elem, translated_text)
                    modified = True
            except Exception as e:
                # Log but continue - don't fail on single translation
                print(f"Warning: Failed to apply translation at {xpath}: {e}")

        if modified:
            # Write back
            # Determine if we need XML declaration
            xml_decl = b'<?xml version="1.0" encoding="UTF-8"?>'
            doctype = self._extract_doctype(content)

            output = etree.tostring(
                tree,
                encoding="unicode",
                pretty_print=False,
            )

            # Write with proper encoding
            with open(file_path, "wb") as f:
                f.write(xml_decl + b"\n")
                if doctype:
                    f.write(doctype.encode("utf-8") + b"\n")
                f.write(output.encode("utf-8"))

    def _find_by_xpath(
        self, tree: etree._Element, xpath: str
    ) -> list[etree._Element]:
        """Find elements by XPath, handling namespaces.

        Args:
            tree: Root element
            xpath: XPath expression (may or may not have namespace prefixes)

        Returns:
            List of matching elements
        """
        # First try with namespace
        try:
            # Convert plain tags to namespaced: /body/div -> /x:body/x:div
            ns_xpath = self._add_namespace_to_xpath(xpath)
            elements = tree.xpath(ns_xpath, namespaces=XHTML_NSMAP)
            if elements:
                return elements
        except Exception:
            pass

        # Try without namespace
        try:
            elements = tree.xpath(xpath)
            if elements:
                return elements
        except Exception:
            pass

        # Try to find by position-based matching
        return self._find_by_position(tree, xpath)

    def _add_namespace_to_xpath(self, xpath: str) -> str:
        """Add namespace prefix to XPath tags.

        Converts /body/div[1]/p[3] to /x:body/x:div[1]/x:p[3]
        """
        # Split by /
        parts = xpath.split("/")
        result = []
        for part in parts:
            if not part:
                result.append("")
                continue
            # Extract tag name and predicate
            match = re.match(r"([a-zA-Z][a-zA-Z0-9]*)(.*)", part)
            if match:
                tag = match.group(1)
                rest = match.group(2)
                result.append(f"x:{tag}{rest}")
            else:
                result.append(part)
        return "/".join(result)

    def _find_by_position(
        self, tree: etree._Element, xpath: str
    ) -> list[etree._Element]:
        """Find element by position in XPath when exact match fails.

        This is a fallback for when the document structure has changed.
        """
        # Parse xpath to get tag sequence
        # e.g., /body/div[1]/p[3] -> [(body, None), (div, 1), (p, 3)]
        parts = []
        for part in xpath.split("/"):
            if not part:
                continue
            match = re.match(r"([a-zA-Z][a-zA-Z0-9]*)(?:\[(\d+)\])?", part)
            if match:
                tag = match.group(1)
                index = int(match.group(2)) if match.group(2) else None
                parts.append((tag, index))

        if not parts:
            return []

        # Navigate to element
        current_elements = [tree]

        for tag, index in parts:
            next_elements = []
            for elem in current_elements:
                # Find children with matching tag
                children = []
                for child in elem:
                    child_tag = etree.QName(child.tag).localname if child.tag else ""
                    if child_tag == tag:
                        children.append(child)

                if index is not None and index <= len(children):
                    next_elements.append(children[index - 1])
                elif children:
                    next_elements.extend(children)

            current_elements = next_elements
            if not current_elements:
                break

        return current_elements

    def _replace_text_content(self, elem: etree._Element, translated_text: str):
        """Replace element's text content while trying to preserve structure.

        This method handles:
        1. Simple text replacement
        2. Preserving inline tags when possible
        3. Handling whitespace properly

        Args:
            elem: Element to modify
            translated_text: New text content
        """
        # Check if element has inline children
        has_inline = any(
            etree.QName(child.tag).localname in ("b", "strong", "i", "em", "u", "span", "small")
            for child in elem
            if child.tag is not None
        )

        if not has_inline or len(list(elem)) == 0:
            # Simple case: replace all text
            # Clear existing content
            elem.text = translated_text
            for child in list(elem):
                elem.remove(child)
        else:
            # Complex case: has inline formatting
            # For now, just replace all text (future: preserve formatting)
            # This is a safe fallback
            elem.text = translated_text
            for child in list(elem):
                elem.remove(child)

    def _extract_doctype(self, content: bytes) -> Optional[str]:
        """Extract DOCTYPE declaration from original content."""
        content_str = content.decode("utf-8", errors="replace")
        match = re.search(r"<!DOCTYPE[^>]+>", content_str, re.IGNORECASE)
        return match.group(0) if match else None

    def _strip_images_from_tree(self, tree: etree._Element) -> bool:
        """Remove all image elements from the XML tree.

        Removes: img, figure, picture, svg, image elements

        Args:
            tree: lxml element tree root

        Returns:
            True if any elements were removed
        """
        removed = False

        # Define tags to remove (with and without namespace)
        image_tags = ["img", "figure", "picture", "svg", "image"]

        for tag_name in image_tags:
            # Try with XHTML namespace
            for elem in tree.xpath(f"//x:{tag_name}", namespaces=XHTML_NSMAP):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)
                    removed = True

            # Try without namespace
            for elem in tree.xpath(f"//{tag_name}"):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)
                    removed = True

        return removed

    def _update_opf(self, file_path: Path):
        """Update OPF metadata with target language.

        Args:
            file_path: Path to OPF file
        """
        content = file_path.read_bytes()
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(content, parser)

        # Find and update language
        nsmap = {"opf": OPF_NS, "dc": DC_NS}
        language = tree.find(".//{%s}language" % DC_NS)
        if language is not None:
            language.text = self.target_language

        # Write back
        output = etree.tostring(
            tree,
            encoding="unicode",
            xml_declaration=True,
        )
        file_path.write_text(output, encoding="utf-8")

    def _update_ncx(self, file_path: Path):
        """Update NCX TOC file if needed.

        This is a placeholder for future TOC title translation.
        """
        # For now, NCX is left unchanged
        # Future: translate navLabel text elements
        pass

    def _create_epub(self, source_dir: Path, output_path: Path):
        """Create EPUB file from directory.

        EPUB files are ZIP files with specific requirements:
        - mimetype file must be first and uncompressed
        - Other files are compressed

        Args:
            source_dir: Directory containing EPUB contents
            output_path: Output EPUB file path
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing file if present
        if output_path.exists():
            output_path.unlink()

        with ZipFile(output_path, "w", ZIP_DEFLATED) as zip_out:
            # Add mimetype first, uncompressed
            mimetype_path = source_dir / "mimetype"
            if mimetype_path.exists():
                zip_out.write(
                    mimetype_path,
                    "mimetype",
                    compress_type=0,  # No compression
                )

            # Add all other files
            for root, dirs, files in os.walk(source_dir):
                for filename in files:
                    if filename == "mimetype":
                        continue  # Already added

                    file_path = Path(root) / filename
                    arcname = str(file_path.relative_to(source_dir))

                    # Add with compression
                    zip_out.write(file_path, arcname)


class BilingualEPUBBuilder:
    """Build bilingual EPUB with original and translated text side by side.

    Creates an EPUB where each paragraph shows both original and translation,
    useful for language learning or review.
    """

    def __init__(
        self,
        original_epub: Path | str,
        translations: list[TranslationMapping],
        style: str = "stacked",  # "stacked" or "side-by-side"
        strip_images: bool = False,
    ):
        """Initialize bilingual builder.

        Args:
            original_epub: Path to original EPUB
            translations: List of translation mappings
            style: Display style - "stacked" (original above translation)
                   or "side-by-side" (table layout)
            strip_images: If True, remove all images from the output EPUB
        """
        self.original_path = Path(original_epub)
        self.translations = translations
        self.style = style
        self.strip_images = strip_images

        # Build lookup dict
        self.translation_map: dict[str, dict[str, str]] = {}
        for t in translations:
            if t.file_path not in self.translation_map:
                self.translation_map[t.file_path] = {}
            self.translation_map[t.file_path][t.xpath] = t.translated_text

    def build(self, output_path: Path | str) -> Path:
        """Build bilingual EPUB.

        Args:
            output_path: Path for output EPUB

        Returns:
            Path to created EPUB
        """
        output_path = Path(output_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract original
            with ZipFile(self.original_path, "r") as zip_in:
                zip_in.extractall(temp_path)

            # Add bilingual CSS
            self._add_bilingual_css(temp_path)

            # Process content files
            for root, dirs, files in os.walk(temp_path):
                for filename in files:
                    if filename.endswith((".xhtml", ".html", ".htm")):
                        file_path = Path(root) / filename
                        rel_path = str(file_path.relative_to(temp_path))
                        self._make_bilingual(file_path, rel_path)

            # Repack
            self._create_epub(temp_path, output_path)

        return output_path

    def _add_bilingual_css(self, epub_dir: Path):
        """Add CSS for bilingual display."""
        css_content = """
/* Bilingual EPUB Styles */
.bilingual-wrapper {
    margin-bottom: 1.5em;
}
.bilingual-original {
    color: #333;
    margin-bottom: 0.5em;
}
.bilingual-translation {
    color: #666;
    font-style: italic;
    border-left: 3px solid #ddd;
    padding-left: 0.5em;
}
.bilingual-table {
    width: 100%;
    border-collapse: collapse;
}
.bilingual-table td {
    width: 50%;
    vertical-align: top;
    padding: 0.5em;
}
.bilingual-table td.original {
    border-right: 1px solid #ddd;
}
"""
        # Find CSS directory or OEBPS
        for subdir in ["OEBPS", "OPS", "."]:
            css_dir = epub_dir / subdir
            if css_dir.exists():
                css_path = css_dir / "bilingual.css"
                css_path.write_text(css_content, encoding="utf-8")
                break

    def _make_bilingual(self, file_path: Path, rel_path: str):
        """Make file bilingual with original + translation."""
        file_translations = self.translation_map.get(rel_path, {})

        # Skip if no translations and no image stripping needed
        if not file_translations and not self.strip_images:
            return

        content = file_path.read_bytes()
        parser = etree.XMLParser(recover=True)

        try:
            tree = etree.fromstring(content, parser)
        except Exception:
            return

        modified = False

        # Strip images if requested
        if self.strip_images:
            modified = self._strip_images_from_tree(tree) or modified

        # Find and process translatable elements
        for xpath, translated_text in file_translations.items():
            try:
                elements = self._find_by_xpath(tree, xpath)
                if elements:
                    elem = elements[0]
                    self._wrap_bilingual(elem, translated_text)
                    modified = True
            except Exception:
                continue

        if not modified:
            return

        # Add CSS link to head
        self._add_css_link(tree)

        # Write back
        output = etree.tostring(tree, encoding="unicode", xml_declaration=True)
        file_path.write_text(output, encoding="utf-8")

    def _strip_images_from_tree(self, tree: etree._Element) -> bool:
        """Remove all image elements from the XML tree.

        Removes: img, figure, picture, svg, image elements

        Args:
            tree: lxml element tree root

        Returns:
            True if any elements were removed
        """
        removed = False

        # Define tags to remove (with and without namespace)
        image_tags = ["img", "figure", "picture", "svg", "image"]

        for tag_name in image_tags:
            # Try with XHTML namespace
            for elem in tree.xpath(f"//x:{tag_name}", namespaces=XHTML_NSMAP):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)
                    removed = True

            # Try without namespace
            for elem in tree.xpath(f"//{tag_name}"):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)
                    removed = True

        return removed

    def _find_by_xpath(self, tree, xpath):
        """Find elements by xpath (same as EPUBReconstructor)."""
        # Reuse the same logic
        try:
            parts = []
            for part in xpath.split("/"):
                if not part:
                    continue
                match = re.match(r"([a-zA-Z][a-zA-Z0-9]*)(?:\[(\d+)\])?", part)
                if match:
                    tag = match.group(1)
                    parts.append(f"x:{tag}" + (f"[{match.group(2)}]" if match.group(2) else ""))
            ns_xpath = "/" + "/".join(parts)
            return tree.xpath(ns_xpath, namespaces=XHTML_NSMAP)
        except Exception:
            return []

    def _wrap_bilingual(self, elem: etree._Element, translated_text: str):
        """Wrap element content in bilingual structure."""
        original_text = "".join(elem.itertext())

        # Clear element
        elem.text = None
        for child in list(elem):
            elem.remove(child)

        if self.style == "stacked":
            # Stacked style: original above, translation below
            wrapper = etree.SubElement(elem, "{%s}div" % XHTML_NS)
            wrapper.set("class", "bilingual-wrapper")

            orig_div = etree.SubElement(wrapper, "{%s}div" % XHTML_NS)
            orig_div.set("class", "bilingual-original")
            orig_div.text = original_text

            trans_div = etree.SubElement(wrapper, "{%s}div" % XHTML_NS)
            trans_div.set("class", "bilingual-translation")
            trans_div.text = translated_text

        else:  # side-by-side
            table = etree.SubElement(elem, "{%s}table" % XHTML_NS)
            table.set("class", "bilingual-table")

            row = etree.SubElement(table, "{%s}tr" % XHTML_NS)

            orig_cell = etree.SubElement(row, "{%s}td" % XHTML_NS)
            orig_cell.set("class", "original")
            orig_cell.text = original_text

            trans_cell = etree.SubElement(row, "{%s}td" % XHTML_NS)
            trans_cell.set("class", "translation")
            trans_cell.text = translated_text

    def _add_css_link(self, tree: etree._Element):
        """Add link to bilingual.css in head."""
        head = tree.find(".//{%s}head" % XHTML_NS)
        if head is None:
            return

        # Check if already added
        for link in head.findall("{%s}link" % XHTML_NS):
            if link.get("href", "").endswith("bilingual.css"):
                return

        # Add link
        link = etree.SubElement(head, "{%s}link" % XHTML_NS)
        link.set("rel", "stylesheet")
        link.set("type", "text/css")
        link.set("href", "bilingual.css")

    def _create_epub(self, source_dir: Path, output_path: Path):
        """Create EPUB (same as EPUBReconstructor)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()

        with ZipFile(output_path, "w", ZIP_DEFLATED) as zip_out:
            mimetype_path = source_dir / "mimetype"
            if mimetype_path.exists():
                zip_out.write(mimetype_path, "mimetype", compress_type=0)

            for root, dirs, files in os.walk(source_dir):
                for filename in files:
                    if filename == "mimetype":
                        continue
                    file_path = Path(root) / filename
                    arcname = str(file_path.relative_to(source_dir))
                    zip_out.write(file_path, arcname)

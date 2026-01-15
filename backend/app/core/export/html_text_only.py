"""Text-only HTML generator for copyright-compliant exports.

Generates clean HTML files with text and TOC only, no images.
"""

from app.core.export.text_extractor import ExtractedContent, TextContentExtractor


class TextOnlyHtmlGenerator:
    """Generate text-only HTML files.

    Creates clean HTML files with:
    - Text content only (no images)
    - TOC with anchor links
    - Responsive typography
    - Bilingual or translation-only modes
    """

    def generate(
        self,
        content: ExtractedContent,
        mode: str = "bilingual",
    ) -> str:
        """Generate HTML file from extracted content.

        Args:
            content: Extracted content from TextContentExtractor
            mode: "bilingual" or "translated"

        Returns:
            Complete HTML document as string
        """
        extractor = TextContentExtractor()
        return extractor.render_html(content, mode)

    def generate_bytes(
        self,
        content: ExtractedContent,
        mode: str = "bilingual",
    ) -> bytes:
        """Generate HTML file as bytes.

        Args:
            content: Extracted content from TextContentExtractor
            mode: "bilingual" or "translated"

        Returns:
            HTML file as bytes (UTF-8 encoded)
        """
        html = self.generate(content, mode)
        return html.encode("utf-8")


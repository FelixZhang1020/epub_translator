"""PDF generator for copyright-compliant exports.

Generates PDF files with text and TOC only using WeasyPrint.
"""

import logging
from io import BytesIO

from app.core.export.text_extractor import ExtractedContent, TextContentExtractor

logger = logging.getLogger(__name__)


class PdfGenerator:
    """Generate PDF files from extracted content.

    Creates clean PDF files with:
    - Text content only (no images)
    - Clickable TOC
    - Page numbers
    - Print-optimized typography
    """

    def __init__(self):
        self._weasyprint_available = None

    def _check_weasyprint(self) -> bool:
        """Check if WeasyPrint is available."""
        if self._weasyprint_available is None:
            try:
                import weasyprint  # noqa: F401
                self._weasyprint_available = True
            except ImportError:
                self._weasyprint_available = False
                logger.warning(
                    "WeasyPrint not installed. PDF export unavailable. "
                    "Install with: pip install weasyprint"
                )
        return self._weasyprint_available

    def generate(
        self,
        content: ExtractedContent,
        mode: str = "bilingual",
        paper_size: str = "A4",
    ) -> bytes:
        """Generate PDF file from extracted content.

        Args:
            content: Extracted content from TextContentExtractor
            mode: "bilingual" or "translated"
            paper_size: "A4" or "Letter"

        Returns:
            PDF file as bytes

        Raises:
            ImportError: If WeasyPrint is not installed
        """
        if not self._check_weasyprint():
            raise ImportError(
                "WeasyPrint is required for PDF export. "
                "Install with: pip install weasyprint"
            )

        from weasyprint import HTML, CSS

        # Get HTML content
        extractor = TextContentExtractor()
        html_content = extractor.render_html(content, mode)

        # Add print-specific CSS
        print_css = self._get_print_css(paper_size)

        # Generate PDF
        html_doc = HTML(string=html_content)
        css_doc = CSS(string=print_css)

        output = BytesIO()
        html_doc.write_pdf(output, stylesheets=[css_doc])

        return output.getvalue()

    def _get_print_css(self, paper_size: str) -> str:
        """Get print-specific CSS."""
        size = "A4" if paper_size == "A4" else "letter"

        return f"""
@page {{
    size: {size};
    margin: 2.5cm;
    @bottom-center {{
        content: counter(page);
        font-size: 10pt;
        color: #666;
    }}
}}

@page :first {{
    margin-top: 4cm;
    @bottom-center {{
        content: none;
    }}
}}

body {{
    font-family: Georgia, "Noto Serif SC", serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #000;
}}

.title-page {{
    text-align: center;
    padding-top: 30%;
    page-break-after: always;
}}

.book-title {{
    font-size: 24pt;
    margin-bottom: 1em;
}}

.book-author {{
    font-size: 14pt;
    color: #444;
}}

.toc {{
    page-break-after: always;
}}

.toc h2 {{
    font-size: 16pt;
    margin-bottom: 1em;
}}

.toc ul {{
    list-style: none;
    padding: 0;
}}

.toc li {{
    margin: 0.5em 0;
    font-size: 11pt;
}}

.toc a {{
    color: #000;
    text-decoration: none;
}}

.toc a::after {{
    content: leader('.') target-counter(attr(href), page);
}}

.chapter {{
    page-break-before: always;
}}

.chapter h2 {{
    font-size: 16pt;
    margin-bottom: 1.5em;
    text-align: center;
}}

p {{
    margin: 0.5em 0;
    text-align: justify;
    orphans: 3;
    widows: 3;
}}

.bilingual-pair {{
    margin: 1em 0;
    padding-bottom: 0.5em;
    border-bottom: 0.5pt solid #ccc;
}}

.original {{
    color: #555;
    font-size: 10pt;
}}

.translation {{
    color: #000;
    margin-top: 0.3em;
}}

.untranslated {{
    color: #888;
    font-style: italic;
}}

blockquote {{
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 2pt solid #999;
    font-style: italic;
}}

h1, h2, h3, h4, h5, h6 {{
    page-break-after: avoid;
}}
"""

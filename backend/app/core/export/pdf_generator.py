"""PDF generator for copyright-compliant exports.

Generates PDF files with text, TOC, and navigational bookmarks using ReportLab.
"""

import logging
import os
from io import BytesIO

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import Color, black
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Flowable, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from app.core.export.text_extractor import ExtractedContent

logger = logging.getLogger(__name__)


class BookmarkFlowable(Flowable):
    """A flowable that adds a PDF bookmark at its position."""

    def __init__(self, title: str, key: str, level: int = 0):
        Flowable.__init__(self)
        self.title = title
        self.key = key
        self.level = level
        self.width = 0
        self.height = 0

    def draw(self):
        # Add bookmark at current position
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, self.level, closed=False)


class PdfGenerator:
    """Generate PDF files from extracted content using ReportLab.

    Creates clean PDF files with:
    - Text content only (no images)
    - Navigational bookmarks/outlines
    - Clickable TOC
    - Page numbers
    - Print-optimized typography
    - Chinese font support
    """

    # Class-level font registration flag
    _fonts_registered = False
    _chinese_font_name = None

    @classmethod
    def _register_fonts(cls):
        """Register fonts for Chinese support.
        
        Priority order:
        1. High-quality TTC fonts (PingFang, Hiragino, Microsoft YaHei)
        2. TTF fonts (Arial Unicode, others)
        3. CID fonts (STSong-Light - functional but not pretty)
        """
        if cls._fonts_registered:
            return cls._chinese_font_name

        # Try high-quality TTC fonts first (best visual quality)
        ttc_fonts = [
            # macOS - PingFang family (best quality on Mac)
            ("/System/Library/Fonts/PingFang.ttc", 0),  # PingFang SC
            ("/Library/Fonts/PingFang.ttc", 0),
            # macOS - Hiragino Sans GB (very good quality)
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
            ("/Library/Fonts/Hiragino Sans GB.ttc", 0),
            # macOS - STHeiti
            ("/System/Library/Fonts/STHeiti Light.ttc", 0),
            ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
            # Windows - Microsoft YaHei (best quality on Windows)
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("C:/Windows/Fonts/msyhbd.ttc", 0),  # Bold variant
            # Windows - SimSun
            ("C:/Windows/Fonts/simsun.ttc", 0),
        ]

        for font_path, subfont_index in ttc_fonts:
            try:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(
                        TTFont('ChineseFont', font_path, subfontIndex=subfont_index)
                    )
                    cls._chinese_font_name = 'ChineseFont'
                    cls._fonts_registered = True
                    logger.info(f"Registered TTC font: {font_path}")
                    return cls._chinese_font_name
            except Exception as e:
                logger.debug(f"Failed to register {font_path}: {e}")
                continue

        # Try TTF fonts (single font files)
        ttf_fonts = [
            # macOS
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/STSong.ttf",
            # Linux - Noto fonts (high quality)
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
            # Windows
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simsun.ttf",
        ]

        for font_path in ttf_fonts:
            try:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    cls._chinese_font_name = 'ChineseFont'
                    cls._fonts_registered = True
                    logger.info(f"Registered TTF font: {font_path}")
                    return cls._chinese_font_name
            except Exception as e:
                logger.debug(f"Failed to register {font_path}: {e}")
                continue

        # Fallback to CID font (works everywhere but not visually optimal)
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            cls._chinese_font_name = 'STSong-Light'
            cls._fonts_registered = True
            logger.info("Registered CID font: STSong-Light (fallback)")
            return cls._chinese_font_name
        except Exception as e:
            logger.debug(f"CID font not available: {e}")

        # No Chinese font available
        cls._fonts_registered = True
        cls._chinese_font_name = None
        logger.warning("No Chinese font available, Chinese text may not render correctly")
        return None

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
        """
        chinese_font = self._register_fonts()

        # Set page size
        page_size = A4 if paper_size == "A4" else LETTER

        # Create PDF in memory
        output = BytesIO()
        doc = BaseDocTemplate(
            output,
            pagesize=page_size,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
            title=content.project_title,
            author=content.project_author or "",
            subject=f"Translation export - {mode} mode",
            creator="EPUB Translator",
        )

        # Create frame and page template
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='normal'
        )
        template = PageTemplate(
            id='main',
            frames=frame,
            onPage=self._add_page_number
        )
        doc.addPageTemplates([template])

        # Build styles with Chinese font support
        styles = self._create_styles(chinese_font)

        # Build content
        story = []

        # Title page with bookmark
        story.append(BookmarkFlowable(content.project_title, 'title', level=0))
        story.append(Spacer(1, 6 * cm))
        story.append(Paragraph(content.project_title, styles['BookTitle']))
        if content.project_author:
            story.append(Spacer(1, 1 * cm))
            story.append(Paragraph(content.project_author, styles['BookAuthor']))
        story.append(PageBreak())

        # Table of Contents page with bookmark (same level as chapters, not a parent)
        story.append(BookmarkFlowable("Contents", 'toc', level=1))
        story.append(Paragraph("Contents", styles['TOCTitle']))
        story.append(Spacer(1, 0.5 * cm))

        # TOC entries (visual list with hierarchy)
        self._render_toc_entries(story, content.toc, styles, indent_level=0)
        story.append(PageBreak())

        # Build chapter ID to chapter object map
        chapter_map = {ch.id: ch for ch in content.chapters}

        # Track bookmark keys to ensure uniqueness
        self._bookmark_counter = 0

        # Render chapters following TOC hierarchy
        # This ensures parent entries appear before their children
        # Note: Only chapters in TOC are rendered in outline for clean hierarchy
        self._render_chapters_from_toc(
            story, content.toc, chapter_map, styles, mode, level=1
        )

        # Build PDF
        doc.build(story)

        return output.getvalue()

    def _create_styles(self, chinese_font: str | None = None):
        """Create paragraph styles for the PDF.

        Args:
            chinese_font: Name of registered Chinese font, or None for default
        """
        styles = getSampleStyleSheet()

        # Use Chinese font if available, otherwise Helvetica
        main_font = chinese_font or 'Helvetica'
        bold_font = chinese_font or 'Helvetica-Bold'
        italic_font = 'Helvetica-Oblique'  # Most Chinese fonts don't have italic

        # Book title (centered, large)
        styles.add(ParagraphStyle(
            name='BookTitle',
            parent=styles['Title'],
            fontName=main_font,
            fontSize=24,
            alignment=1,  # Center
            spaceAfter=12,
        ))

        # Book author (centered)
        styles.add(ParagraphStyle(
            name='BookAuthor',
            parent=styles['Normal'],
            fontName=main_font,
            fontSize=14,
            alignment=1,  # Center
            textColor=Color(0.3, 0.3, 0.3),
        ))

        # TOC title
        styles.add(ParagraphStyle(
            name='TOCTitle',
            parent=styles['Heading1'],
            fontName=bold_font,
            fontSize=18,
            spaceAfter=12,
        ))

        # TOC entry
        styles.add(ParagraphStyle(
            name='TOCEntry',
            parent=styles['Normal'],
            fontName=main_font,
            fontSize=11,
            leftIndent=0.5 * cm,
            spaceBefore=4,
            spaceAfter=4,
        ))

        # Chapter title
        styles.add(ParagraphStyle(
            name='ChapterTitle',
            parent=styles['Heading1'],
            fontName=bold_font,
            fontSize=16,
            alignment=1,  # Center
            spaceBefore=24,
            spaceAfter=12,
        ))

        # Section heading
        styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=styles['Heading2'],
            fontName=bold_font,
            fontSize=13,
            spaceBefore=12,
            spaceAfter=6,
        ))

        # Body text for content
        styles.add(ParagraphStyle(
            name='ContentBody',
            parent=styles['Normal'],
            fontName=main_font,
            fontSize=11,
            leading=16,
            firstLineIndent=0.5 * cm,
            spaceBefore=4,
            spaceAfter=4,
            alignment=4,  # Justify
        ))

        # Original text (bilingual mode - gray, smaller)
        styles.add(ParagraphStyle(
            name='OriginalText',
            parent=styles['Normal'],
            fontName=main_font,
            fontSize=10,
            leading=14,
            textColor=Color(0.4, 0.4, 0.4),
            spaceBefore=6,
            spaceAfter=2,
        ))

        # Translated text (bilingual mode)
        styles.add(ParagraphStyle(
            name='TranslatedText',
            parent=styles['Normal'],
            fontName=main_font,
            fontSize=11,
            leading=16,
            textColor=black,
            spaceBefore=2,
            spaceAfter=4,
        ))

        # Untranslated placeholder
        styles.add(ParagraphStyle(
            name='UntranslatedText',
            parent=styles['Normal'],
            fontName=italic_font,
            fontSize=10,
            leading=14,
            textColor=Color(0.6, 0.6, 0.6),
            spaceBefore=2,
            spaceAfter=4,
        ))

        return styles

    def _add_page_number(self, canvas, doc):
        """Add page number to footer."""
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(Color(0.4, 0.4, 0.4))
        page_num = canvas.getPageNumber()
        text = str(page_num)
        canvas.drawCentredString(doc.pagesize[0] / 2, 1.5 * cm, text)
        canvas.restoreState()

    def _render_toc_entries(self, story, toc_entries, styles, indent_level: int = 0):
        """Render TOC entries with hierarchy and indentation.

        Args:
            story: ReportLab story list to append to
            toc_entries: List of TOCEntry objects
            styles: Paragraph styles dictionary
            indent_level: Current indentation level for nested entries
        """
        for entry in toc_entries:
            # Create indented TOC entry style dynamically
            indent = 0.5 * cm * indent_level
            toc_style = ParagraphStyle(
                name=f'TOCEntry_{indent_level}_{id(entry)}',
                parent=styles['TOCEntry'],
                leftIndent=indent + 0.5 * cm,
                fontSize=11 - indent_level,  # Smaller font for deeper levels
            )

            # Add the entry
            story.append(Paragraph(entry.title, toc_style))

            # Recursively render children
            if entry.children:
                self._render_toc_entries(story, entry.children, styles, indent_level + 1)

    def _render_chapters_from_toc(
        self, story, toc_entries, chapter_map, styles, mode: str, level: int = 1
    ):
        """Render chapters following the TOC hierarchy.

        This method traverses the TOC structure and adds bookmarks for both:
        - Parent entries (sections without chapter content)
        - Chapter entries (with actual content)

        This ensures the PDF outline mirrors the TOC hierarchy exactly.

        Args:
            story: ReportLab story list to append to
            toc_entries: List of TOCEntry objects
            chapter_map: Dictionary mapping chapter_id to chapter objects
            styles: Paragraph styles dictionary
            mode: "bilingual" or "translated"
            level: Current bookmark level (1 = top-level)
        """
        for entry in toc_entries:
            chapter = chapter_map.get(entry.chapter_id) if entry.chapter_id else None

            if chapter:
                # Entry has chapter content - render the chapter with TOC title
                self._render_single_chapter(
                    story, chapter, styles, mode, level, bookmark_title=entry.title
                )
            elif entry.children:
                # Parent entry without chapter content - add section bookmark
                self._bookmark_counter += 1
                section_key = f'section_{self._bookmark_counter}'
                story.append(BookmarkFlowable(entry.title, section_key, level=level))

            # Recursively render children at deeper level
            if entry.children:
                self._render_chapters_from_toc(
                    story, entry.children, chapter_map, styles, mode, level + 1
                )

    def _render_single_chapter(
        self, story, chapter, styles, mode: str, level: int,
        bookmark_title: str = None
    ):
        """Render a single chapter with bookmark and content.

        Args:
            story: ReportLab story list to append to
            chapter: ExtractedChapter object
            styles: Paragraph styles dictionary
            mode: "bilingual" or "translated"
            level: Bookmark level for this chapter
            bookmark_title: Title for the PDF bookmark (from TOC entry)
        """
        self._bookmark_counter += 1
        chapter_key = f'chapter_{self._bookmark_counter}'
        # Use TOC entry title for bookmark, fallback to chapter title
        outline_title = bookmark_title or chapter.title or f"Chapter {chapter.chapter_number}"

        # Add bookmark for this chapter
        story.append(BookmarkFlowable(outline_title, chapter_key, level=level))

        # Chapter title
        if chapter.title:
            story.append(Paragraph(chapter.title, styles['ChapterTitle']))
            story.append(Spacer(1, 0.5 * cm))

        # Paragraphs
        for para in chapter.paragraphs:
            if mode == "translated":
                # Translation only
                text = para.translated_text or para.original_text
                if para.is_heading:
                    story.append(Paragraph(text, styles['SectionHeading']))
                else:
                    story.append(Paragraph(text, styles['ContentBody']))
            else:
                # Bilingual mode
                # Original text (gray, smaller)
                story.append(Paragraph(para.original_text, styles['OriginalText']))

                # Translation (black, normal size)
                if para.translated_text:
                    story.append(Paragraph(para.translated_text, styles['TranslatedText']))
                else:
                    story.append(Paragraph("[Not translated]", styles['UntranslatedText']))

                story.append(Spacer(1, 0.3 * cm))

                # Dividing line between paragraph pairs (like HTML export)
                story.append(HRFlowable(
                    width="100%",
                    thickness=0.5,
                    color=Color(0.85, 0.85, 0.85),  # Light gray
                    spaceBefore=0.1 * cm,
                    spaceAfter=0.3 * cm,
                ))

        # Page break after each chapter
        story.append(PageBreak())

    def _collect_toc_chapter_ids(self, toc_entries) -> set:
        """Collect all chapter IDs from TOC structure.

        Args:
            toc_entries: List of TOCEntry objects

        Returns:
            Set of chapter IDs that appear in the TOC
        """
        ids = set()
        for entry in toc_entries:
            if entry.chapter_id:
                ids.add(entry.chapter_id)
            if entry.children:
                ids.update(self._collect_toc_chapter_ids(entry.children))
        return ids

    def _build_chapter_toc_map(self, toc_entries, level: int = 1) -> dict:
        """Build a map from chapter_id to bookmark level.

        The level should reflect the actual visual hierarchy in the PDF outline.
        Parent entries without chapter_ids still provide hierarchy context for
        determining the correct nesting level of their children.

        Args:
            toc_entries: List of TOCEntry objects
            level: Current hierarchy level (1 = top-level chapters)

        Returns:
            Dictionary mapping chapter_id to bookmark level
        """
        result = {}
        for entry in toc_entries:
            # Record the level for this entry if it has a chapter
            if entry.chapter_id:
                result[entry.chapter_id] = level

            # Process children at deeper level
            # Children are always one level deeper than their parent,
            # regardless of whether the parent has a chapter_id
            if entry.children:
                child_map = self._build_chapter_toc_map(entry.children, level + 1)
                result.update(child_map)

        return result

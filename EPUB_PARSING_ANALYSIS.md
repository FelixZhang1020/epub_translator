# EPUB Parsing Architecture Analysis

## Current Issues

### 1. Parser Technology Stack
```
Current:  ebooklib (EPUB reader) + BeautifulSoup (HTML parser)
Problem:  EPUB uses XHTML/XML, but we parse as HTML
Warning:  "XMLParsedAsHTMLWarning: using HTML parser for XML document"
```

### 2. Content Being Lost

| Content Type | Current Handling | Impact |
|-------------|------------------|--------|
| Drop-caps (`W<small>HAT</small>`) | Partial fix | Some still broken |
| Images (19 in this book) | **Ignored** | Figures, illustrations lost |
| Tables (2 found) | **Ignored** | Data tables lost |
| SVG graphics | **Ignored** | Vector graphics lost |
| Inline formatting (bold, italic) | **Lost** | Semantic meaning lost |
| Footnotes/endnotes | **Lost** | References lost |
| Figure captions | **Ignored** | Context lost |

### 3. Structural Issues

```
Original EPUB Structure:
  Chapter 3: Knowing and Being Known
    ├── Introduction (paragraphs 1-11)
    ├── WHAT KNOWING GOD INVOLVES (section)
    │   └── paragraphs 1-11
    ├── KNOWING JESUS (section)
    │   └── paragraphs 1-8
    └── ...

Current Parsing Result:
  Chapter 14: "Chapter Three" (11 paragraphs)
  Chapter 15: "WHAT KNOWING GOD INVOLVES" (11 paragraphs)  ← Separate!
  Chapter 16: "KNOWING JESUS" (8 paragraphs)               ← Separate!
```

**Problem**: Split HTML files become separate chapters, losing hierarchy.

### 4. Redundancy Issue
- Each section's first paragraph is the h2 heading
- This duplicates the chapter title in UI header
- User sees: Header "KNOWING JESUS" + Paragraph 1 "KNOWING JESUS"

## Root Cause

The fundamental problem is treating EPUB as a **flat text extraction** task instead of a **structured document transformation**.

EPUB is:
- Semantically structured (chapters, sections, subsections)
- Richly formatted (styles, fonts, emphasis)
- Multi-media (text, images, audio, video)
- Interactive (links, footnotes, TOC)

Our parser:
- Extracts only text from specific tags
- Loses all formatting
- Ignores all media
- Flattens hierarchy

## Recommended Architecture

### Option A: Improve Current Parser (Quick Fix)

```python
# 1. Use XML parser instead of HTML
soup = BeautifulSoup(content, 'xml')  # Not 'lxml'

# 2. Preserve inline formatting
def extract_with_formatting(element):
    """Extract text while preserving semantic markers"""
    result = []
    for child in element.children:
        if child.name == 'strong' or child.name == 'b':
            result.append(f"**{child.get_text()}**")
        elif child.name == 'em' or child.name == 'i':
            result.append(f"*{child.get_text()}*")
        # ... etc
    return ''.join(result)

# 3. Handle images
def extract_images(soup):
    """Extract images with context"""
    images = []
    for img in soup.find_all('img'):
        figure = img.find_parent('figure')
        caption = figure.find('figcaption').get_text() if figure else ''
        images.append({
            'src': img.get('src'),
            'alt': img.get('alt', ''),
            'caption': caption,
            'position': len(images)
        })
    return images

# 4. Skip redundant title paragraphs
def should_skip_paragraph(text, chapter_title):
    """Skip if paragraph is just the chapter title"""
    return text.strip().upper() == chapter_title.strip().upper()
```

### Option B: Professional EPUB Library (Better)

Use **Calibre's ebook-convert** or **EbookLib** more comprehensively:

```python
# Calibre has the most robust EPUB handling
from calibre.ebooks.epub import reader
from calibre.ebooks.oeb.base import OPF

# Or use dedicated library
import epub_meta  # For metadata
import ebooklib    # Current - but use more features
```

### Option C: Document Conversion Pipeline (Best for Translation)

```
EPUB → Pandoc → Markdown/DocBook → Parse → Translate → Reconstruct → EPUB

Benefits:
- Pandoc handles all edge cases
- Markdown is easy to parse and translate
- Can preserve structure through conversion
- Battle-tested on thousands of formats
```

### Option D: AI-Assisted Parsing (Future)

Use LLM to:
1. Understand document structure
2. Identify translatable vs non-translatable content
3. Handle edge cases intelligently
4. Preserve context for translation

## Immediate Fixes Needed

### Fix 1: Skip Redundant Title Paragraphs
```python
# In _extract_paragraphs():
if para['html_tag'] in ('h1', 'h2') and para['original_text'] == chapter_title:
    continue  # Skip as it's shown in header
```

### Fix 2: Use XML Parser
```python
# In EPUBParser:
soup = BeautifulSoup(content, 'xml')  # Change from 'lxml'
```

### Fix 3: Add Image Extraction
```python
# New method in EPUBParser
def extract_images(self, soup) -> list[dict]:
    images = []
    for img in soup.find_all('img'):
        images.append({
            'src': img.get('src'),
            'alt': img.get('alt', ''),
            'in_figure': bool(img.find_parent('figure'))
        })
    return images
```

### Fix 4: Preserve Basic Formatting
```python
# Store as markdown-style text
def extract_formatted_text(element):
    html = str(element)
    # Convert <b>/<strong> to **
    # Convert <i>/<em> to *
    # Keep structure for translation context
```

## Long-term Recommendation

For a production translation tool:

1. **Use Pandoc** as the conversion engine
2. **Store original EPUB structure** in database
3. **Extract semantic segments** (not just paragraphs)
4. **Preserve all metadata** (images, styles, etc.)
5. **Reconstruct valid EPUB** after translation

This ensures:
- No content loss
- Proper formatting
- Image handling
- Professional output quality

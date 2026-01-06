# EPUB Parser Technical Documentation

## Overview

The EPUB Parser V2 is an lxml-based parser designed for extracting translatable content from EPUB files while preserving document structure for reconstruction after translation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EPUB File (.epub)                        │
│                        (ZIP Archive)                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    META-INF/container.xml                        │
│                    (Locates OPF file)                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      content.opf (OPF File)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Metadata   │  │   Manifest   │  │    Spine     │           │
│  │ title,author │  │  all files   │  │reading order │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TOC (NCX or NAV)                              │
│                 Hierarchical Navigation                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    XHTML Content Files                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Paragraphs  │  │    Images    │  │  Formatting  │           │
│  │   (text)     │  │  (src, alt)  │  │  (b, i, em)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Database                                  │
│  Project → Chapters → Paragraphs → Translations                  │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| XML/XHTML Parsing | **lxml** | Handle EPUB XHTML with namespaces |
| EPUB Reading | **zipfile** | EPUB is a ZIP archive |
| Database | **SQLite + SQLAlchemy** | Store chapters, paragraphs, translations |
| Backend | **FastAPI** | REST API |

## Parsing Process

### Step 1: Open EPUB Archive

```python
from zipfile import ZipFile
zip_file = ZipFile(epub_path)
```

EPUB files are ZIP archives containing:
- `META-INF/container.xml` - Entry point
- `*.opf` - Package document (manifest, spine, metadata)
- `*.ncx` or `nav.xhtml` - Table of contents
- `*.xhtml` - Content files
- `images/` - Image assets
- `*.css` - Stylesheets

### Step 2: Locate OPF File

```python
# Read container.xml
container_content = zip_file.read("META-INF/container.xml")
container_tree = etree.fromstring(container_content)

# Find OPF path
rootfile = container_tree.find(
    ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
)
opf_path = rootfile.get("full-path")  # e.g., "OEBPS/content.opf"
```

### Step 3: Parse OPF Structure

The OPF file contains three key sections:

#### Metadata
```xml
<metadata>
    <dc:title>Book Title</dc:title>
    <dc:creator>Author Name</dc:creator>
    <dc:language>en</dc:language>
</metadata>
```

#### Manifest (All Files)
```xml
<manifest>
    <item id="chapter1" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="cover" href="images/cover.jpg" media-type="image/jpeg"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
</manifest>
```

#### Spine (Reading Order)
```xml
<spine toc="ncx">
    <itemref idref="cover"/>
    <itemref idref="chapter1"/>
    <itemref idref="chapter2"/>
</spine>
```

### Step 4: Parse Table of Contents

#### NCX Format (EPUB 2)
```xml
<navMap>
    <navPoint>
        <navLabel><text>Chapter 1</text></navLabel>
        <content src="chapter1.xhtml"/>
        <navPoint><!-- nested chapters --></navPoint>
    </navPoint>
</navMap>
```

#### NAV Format (EPUB 3)
```xml
<nav epub:type="toc">
    <ol>
        <li><a href="chapter1.xhtml">Chapter 1</a>
            <ol><!-- nested chapters --></ol>
        </li>
    </ol>
</nav>
```

### Step 5: Extract Content from XHTML

```python
# Parse with namespace support
tree = etree.fromstring(content)

# Find elements with namespace
paragraphs = tree.xpath("//x:p", namespaces={"x": "http://www.w3.org/1999/xhtml"})

# Extract text with drop-cap handling
text = extract_text_smart(element)
```

## XML Namespaces

| Namespace | URI | Usage |
|-----------|-----|-------|
| XHTML | `http://www.w3.org/1999/xhtml` | Content documents |
| OPF | `http://www.idpf.org/2007/opf` | Package document |
| DC | `http://purl.org/dc/elements/1.1/` | Dublin Core metadata |
| NCX | `http://www.daisy.org/z3986/2005/ncx/` | EPUB 2 TOC |
| SVG | `http://www.w3.org/2000/svg` | Vector graphics |
| XLink | `http://www.w3.org/1999/xlink` | SVG image references |

## Configuration System

### ParserConfig Class

```python
@dataclass
class ParserConfig:
    # Text filtering
    min_text_length: int = 1          # Minimum characters
    min_alpha_ratio: float = 0.3      # Minimum alphabetic ratio
    max_title_length: int = 300       # Maximum title length

    # Behavior switches
    skip_duplicates: bool = True
    skip_redundant_titles: bool = True

    # Tag sets
    translatable_tags: set[str]       # Tags to extract text from
    inline_formatting_tags: set[str]  # Tags to preserve
    container_tags: set[str]          # Container elements
    title_tags: list[str]             # Tags for title extraction

    # Filters
    placeholder_alt_texts: set[str]   # Alt texts to ignore
```

### Predefined Configurations

| Config | Use Case | min_text_length | min_alpha_ratio |
|--------|----------|-----------------|-----------------|
| `DEFAULT_CONFIG` | General books | 1 | 0.3 |
| `STRICT_CONFIG` | Novels | 10 | 0.5 |
| `LENIENT_CONFIG` | Technical books | 1 | 0.0 |
| `CJK_CONFIG` | Chinese/Japanese/Korean | 1 | 0.0 |

### Usage

```python
from app.core.epub.parser_v2 import EPUBParserV2, ParserConfig, CJK_CONFIG

# Default configuration
parser = EPUBParserV2("book.epub")

# Custom configuration
config = ParserConfig(
    min_text_length=5,
    min_alpha_ratio=0.0,
)
parser = EPUBParserV2("book.epub", config=config)

# Preset configuration
parser = EPUBParserV2("chinese_book.epub", config=CJK_CONFIG)
```

## Tag Handling

### Translatable Tags (20 tags)

Content is extracted from these elements:

| Category | Tags |
|----------|------|
| Headings | `h1`, `h2`, `h3`, `h4`, `h5`, `h6` |
| Paragraphs | `p`, `blockquote`, `pre` |
| Lists | `li`, `dt`, `dd` |
| Tables | `caption`, `th`, `td` |
| Figures | `figcaption` |
| HTML5 Semantic | `summary`, `details` |
| Legacy | `cite`, `q` |

### Inline Formatting Tags (16+ tags)

These tags are preserved within text:

| Category | Tags |
|----------|------|
| Emphasis | `b`, `strong`, `i`, `em`, `u` |
| Editing | `s`, `strike`, `del`, `ins` |
| Position | `sub`, `sup` |
| Style | `span`, `small`, `big`, `mark` |
| Code | `code`, `kbd`, `samp`, `var` |
| Links | `a` |
| Abbreviations | `abbr`, `acronym` |
| CJK Ruby | `ruby`, `rt`, `rp` |

### Container Tags

May contain direct text if no child translatable elements:
- `div`, `section`, `article`, `aside`
- `header`, `footer`, `main`, `nav`, `figure`

## Special Handling

### Drop-Cap Patterns

EPUBs often use special patterns for decorative initial letters:

#### Pattern 1: Small Tag
```html
<p>W<small>HAT</small> is the meaning...</p>
```
Extracted as: "WHAT is the meaning..."

#### Pattern 2: Span with Single Letter
```html
<p><span class="dropcap">T</span>he story begins...</p>
```
Extracted as: "The story begins..."

#### Implementation
```python
def _extract_text_smart(self, element):
    # Detect and unwrap small tags
    for small in element.iter("small"):
        unwrap_element(small)

    # Detect single-letter spans followed by lowercase
    for span in element.iter("span"):
        if len(span.text) == 1 and span.text.isupper():
            if span.tail and span.tail[0].islower():
                # Merge: <span>W</span>hen -> When
                span.text = span.text + span.tail
                span.tail = ""
                unwrap_element(span)
```

### SVG Cover Images

Many EPUBs use SVG for cover pages:

```html
<svg xmlns="http://www.w3.org/2000/svg">
    <image xlink:href="cover.jpeg" width="100%" height="100%"/>
</svg>
```

#### Implementation
```python
# Find both <img> and SVG <image>
images = tree.xpath("//x:img", namespaces=XHTML_NSMAP)
svg_images = tree.xpath("//*[local-name()='image']")

# Get src from either attribute
src = img.get("src") or img.get("{http://www.w3.org/1999/xlink}href")
```

### Split Files

Long chapters are often split into multiple files:
- `chapter1_split_000.html` (main)
- `chapter1_split_001.html` (continuation)
- `chapter1_split_002.html` (continuation)

The TOC references only `_split_000`, but we detect and group related splits as children.

## Filtering Rules

### Text Length Filter
```python
if len(text) < config.min_text_length:
    continue  # Skip too short
```

### Alpha Ratio Filter
```python
if config.min_alpha_ratio > 0:
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count / len(text) < config.min_alpha_ratio:
        continue  # Skip non-alphabetic content
```

### Duplicate Filter
```python
if config.skip_duplicates and text in seen_texts:
    continue  # Skip already seen
```

### Redundant Title Filter
```python
if config.skip_redundant_titles:
    if tag in title_tags and text == chapter_title:
        continue  # Skip title repeated as paragraph
```

### Placeholder Alt Text Filter
```python
placeholder_alts = {
    "", "description", "image", "photo", "picture", "figure",
    "description à venir", "coming soon", "placeholder",
    "cover", "cover image", "book cover",
}
if alt.lower() in placeholder_alts:
    alt = ""  # Clear placeholder
```

## Database Schema

```
Project
├── id: UUID
├── name: str
├── author: str
├── original_file_path: str
├── toc_structure: JSON          # Original TOC hierarchy
└── chapters: [Chapter]

Chapter
├── id: UUID
├── project_id: FK
├── chapter_number: int          # Spine order
├── title: str
├── html_path: str               # Path in EPUB
├── original_html: str           # Full HTML content
├── images: JSON                 # [{src, alt, position, xpath}]
├── paragraph_count: int
├── word_count: int
└── paragraphs: [Paragraph]

Paragraph
├── id: UUID
├── chapter_id: FK
├── paragraph_number: int
├── original_text: str
├── html_tag: str                # p, h1, li, etc.
├── xpath: str                   # Element location
├── original_html: str           # Raw HTML
├── has_formatting: bool
├── word_count: int
└── translations: [Translation]

Translation
├── id: UUID
├── paragraph_id: FK
├── translated_text: str
├── provider: str                # openai, anthropic, etc.
├── model: str                   # gpt-4, claude-3, etc.
├── mode: str                    # paragraph, context, etc.
├── version: int
├── is_manual_edit: bool
└── created_at: datetime
```

## API Endpoints

### TOC Endpoint

```
GET /api/v1/preview/{project_id}/toc
```

Returns hierarchical TOC with:
- Chapters from EPUB TOC structure
- Chapters before TOC (Cover, front matter)
- Split files grouped as children

### Chapter Content Endpoint

```
GET /api/v1/preview/{project_id}/chapter/{chapter_id}
```

Returns:
- Chapter metadata
- Paragraphs with translations
- Images list

### Image Serving Endpoint

```
GET /api/v1/preview/{project_id}/image/{image_path}
```

Serves images directly from the EPUB ZIP file.

## Error Handling

### Malformed XML
```python
parser = etree.XMLParser(recover=True)
try:
    tree = etree.fromstring(content, parser)
except etree.XMLSyntaxError:
    # Fallback to HTML parser
    from lxml import html
    tree = html.fromstring(content)
```

### Missing Files
```python
try:
    content = zip_file.read(file_path)
except KeyError:
    # File not found in EPUB
    continue
```

### Encoding Issues
```python
content.decode("utf-8", errors="replace")
```

## Performance Considerations

1. **Lazy Loading**: Content files are parsed on-demand, not all at once
2. **Streaming**: Use iterators (`iter_segments`, `iter_images`) for memory efficiency
3. **Caching**: Parsed OPF structure is cached in parser instance
4. **Batch Database Operations**: Use `flush()` instead of `commit()` per item

## File Locations

| File | Purpose |
|------|---------|
| `backend/app/core/epub/parser_v2.py` | Main parser implementation |
| `backend/app/api/v1/routes/preview.py` | TOC and content API |
| `backend/app/models/database/` | Database models |
| `backend/scripts/migrate_v2.py` | Database migration script |

## Extending the Parser

### Adding New Translatable Tags

```python
config = ParserConfig()
config.translatable_tags.add("custom-tag")
parser = EPUBParserV2("book.epub", config=config)
```

### Custom Filtering Logic

Subclass `EPUBParserV2` and override `iter_segments`:

```python
class CustomParser(EPUBParserV2):
    def iter_segments(self, file_path, chapter_title=""):
        for segment in super().iter_segments(file_path, chapter_title):
            # Custom filtering
            if self.should_include(segment):
                yield segment
```

## Version History

| Version | Changes |
|---------|---------|
| V1 | Basic regex-based parsing |
| V2 | lxml-based with namespace support, configurable options, SVG image support |

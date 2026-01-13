# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Quick Start
```bash
./start.sh                    # Start both backend and frontend (auto-installs deps)
./scripts/dev/restart.sh      # Restart services (uses nohup, runs in background)
```

### Backend (FastAPI + Python 3.11+)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest                        # Uses asyncio_mode="auto" from pyproject.toml
pytest tests/test_file.py     # Run single test file
pytest -k "test_name"         # Run tests matching pattern

# Linting
ruff check .                  # Line length: 100

# Database migrations (Alembic)
alembic upgrade head          # Apply all migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic downgrade -1          # Rollback one migration
```

### Frontend (React + TypeScript + Vite)
```bash
cd frontend
npm run dev                   # Development server on port 5173
npm run build                 # TypeScript check + Vite build
npm run lint                  # ESLint with --max-warnings 0
```

### URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Functional Requirements

### Core Features

1. **ePub Upload & Parsing**
   - Upload English ePub files
   - Extract chapters, paragraphs, images, and metadata
   - Preserve original HTML structure for reconstruction
   - Support hierarchical TOC (table of contents)

2. **Book Analysis (AI-powered)**
   - Sample paragraphs for style analysis
   - Extract: writing style, tone, target audience, genre conventions
   - Generate terminology glossary (English → Chinese mappings)
   - Define translation principles (faithfulness, adaptation boundaries)
   - Streaming progress via SSE (Server-Sent Events)

3. **Translation Workflow**
   - Chapter-by-chapter translation with paragraph-level granularity
   - Context-aware translation (previous/next paragraph context)
   - Reference ePub support for consistency with existing translations
   - Lock/unlock individual paragraphs
   - Retranslate single paragraphs
   - Discussion chat for translation reasoning

4. **Proofreading**
   - LLM-powered suggestion generation
   - Two view modes: LLM suggestions vs all translations
   - Accept/reject/modify suggestions
   - Quick recommendation for manual feedback
   - Session-based proofreading rounds

5. **Export**
   - Bilingual format (original + translation side-by-side)
   - Translation-only format
   - ePub and HTML output formats
   - Chapter selection for partial export
   - Preview before download

### User Operations

#### Step 1: Analysis Page (`/project/{id}/analysis`)
- **Start Analysis**: Click "Analyze" to run LLM analysis with streaming progress
- **View/Edit Results**: Editable cards for each analysis field (style, tone, terminology, etc.)
- **Confirm Analysis**: Lock results before proceeding to translation
- **Re-analyze**: Run analysis again with different prompts or LLM

#### Step 2: Translation Page (`/project/{id}/translate`)
- **Upload Reference**: Optional - upload existing Chinese translation ePub for reference matching
- **Translate Chapter**: Click "Translate Current Chapter" to translate visible chapter
- **Edit Translation**: Click edit icon on any paragraph to modify manually
- **Retranslate**: Regenerate translation for single paragraph
- **Lock/Unlock**: Protect good translations from accidental changes
- **Discussion**: Open chat modal to discuss translation decisions with LLM
- **Complete Translation**: Confirm when satisfied to proceed

#### Step 3: Proofreading Page (`/project/{id}/proofread`)
- **Start Proofreading**: Generate LLM suggestions for selected chapters
- **Review Suggestions**: Accept, reject, or modify each suggestion
- **Quick Feedback**: Request new recommendation based on manual feedback
- **All Translations View**: Review all paragraphs (not just suggestions)
- **Lock Confirmed**: Lock translations that are finalized

#### Step 4: Export Page (`/project/{id}/export`)
- **Select Chapters**: Choose which chapters to export
- **Choose Format**: Bilingual or translation-only
- **Choose Type**: ePub (for e-readers) or HTML (for web)
- **Preview**: See how export will look
- **Download**: Generate and download final file

### Key Business Logic

#### Translation Context
- Each paragraph translation includes previous paragraph (source + translation) for continuity
- Optional: next paragraph source for lookahead context
- Reference translations (from uploaded reference ePub) injected into prompts

#### Prompt Variable Resolution
Variables are resolved at runtime from multiple sources:
1. `project.*` - From database (Project model)
2. `content.*` - From current paragraph being processed
3. `context.*` - From adjacent paragraphs
4. `pipeline.*` - From previous pipeline steps (reference matching, optimization suggestions)
5. `derived.*` - From analysis results (mapped via `variables.py`)
6. `user.*` - From `projects/{id}/variables.json`
7. `meta.*` - Computed at runtime (word count, indices)

#### LLM Configuration
- Stored configs in database with encrypted API keys
- Environment variable fallback for API keys
- Per-request config override for testing
- Model cost estimation before translation

#### Caching
- LLM responses cached by prompt hash in `projects/{id}/cache/llm_responses/`
- Cache key = SHA256 of (system_prompt + user_prompt + model)
- Enables resuming interrupted translations

## Architecture

### Translation Pipeline (Backend Core)

The translation system uses a strategy pattern with a pipeline architecture:

```
TranslationContext → PromptEngine → PromptBundle → LLMGateway → OutputProcessor → Result
```

**Key Components:**
- `backend/app/core/translation/pipeline/pipeline.py` - Main orchestrator (`TranslationPipeline`)
- `backend/app/core/translation/strategies/` - Translation modes:
  - `direct.py` - Single-pass translation
  - `author_aware.py` - Uses author background info
  - `iterative.py` - Two-step: literal → refined
  - `optimization.py` - Applies proofreading suggestions
- `backend/app/core/translation/pipeline/prompt_engine.py` - Template variable substitution

**Translation Modes:**
- DIRECT: Simple one-step translation
- AUTHOR_AWARE: Uses author background for context
- ITERATIVE: Two passes (Step 1: literal, Step 2: natural)
- OPTIMIZATION: Applies confirmed proofreading suggestions

### Prompt Template System

Templates use Handlebars-like syntax (`{{variable}}`) with namespaced variables:

**Variable Namespaces:**
- `project.*` - Book metadata (title, author, languages)
- `content.*` - Current text being processed
- `context.*` - Surrounding paragraphs (translation stage only)
- `pipeline.*` - Previous step outputs (reference_translation, suggested_changes)
- `derived.*` - Analysis results (writing_style, tone, terminology_table)
- `user.*` - Custom project variables
- `meta.*` - Runtime values (word_count, stage)

**Template Files:** `backend/prompts/{category}/system.{name}.md` and `user.{name}.md`

**Variable Reference:** See `backend/prompts/VARIABLES.md` for complete documentation

### 4-Step Workflow

1. **Analysis** (`/analysis`) - Extract book style, tone, terminology
2. **Translation** (`/translation`) - Translate with context awareness
3. **Proofreading** (`/proofreading`) - Review and refine translations
4. **Export** (`/export`) - Generate bilingual ePub/HTML

### Data Storage

**SQLite (async):** `backend/app/models/database/` - Projects, chapters, paragraphs, translations
**File-based:**
- `projects/{project_id}/` - Project files (epub, variables.json, user prompts)
- `projects/{project_id}/cache/` - LLM response cache
- `backend/prompts/` - Global prompt templates

### Frontend State

- **Zustand stores:** `frontend/src/stores/` - appStore.ts, settingsStore.ts
- **API client:** `frontend/src/services/api/client.ts` - Typed axios wrapper (1300+ lines)
- **i18n:** `frontend/src/i18n/locales/` - en.json, zh.json

### LLM Integration

Supports multiple providers via `backend/app/core/llm/`:
- OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, DeepSeek
- Configuration stored in database with encrypted API keys
- Response caching in `backend/app/core/cache/`

## API Endpoints Reference

### Project Management
- `POST /api/v1/upload` - Upload ePub, create project
- `GET /api/v1/projects` - List all projects
- `GET /api/v1/projects/{id}` - Get project details
- `DELETE /api/v1/projects/{id}` - Delete project

### Analysis
- `POST /api/v1/analysis/{project_id}/start` - Start analysis (blocking)
- `POST /api/v1/analysis/{project_id}/start-stream` - Start with SSE progress
- `GET /api/v1/analysis/{project_id}` - Get analysis results
- `PUT /api/v1/analysis/{project_id}` - Update/confirm analysis

### Translation
- `POST /api/v1/translation/start` - Start translation task
- `GET /api/v1/translation/status/{task_id}` - Get task progress
- `POST /api/v1/translation/retranslate/{paragraph_id}` - Retranslate single paragraph
- `DELETE /api/v1/translation/chapter/{chapter_id}` - Clear chapter translations

### Proofreading
- `POST /api/v1/proofreading/{project_id}/start` - Start proofreading session
- `GET /api/v1/proofreading/{session_id}/suggestions` - Get suggestions
- `PUT /api/v1/proofreading/suggestion/{id}` - Accept/reject/modify
- `POST /api/v1/proofreading/quick-recommendation` - Get quick LLM recommendation

### Export
- `POST /api/v1/export/{project_id}/v2` - Export ePub
- `POST /api/v1/export/{project_id}/html` - Export HTML
- `GET /api/v1/export/{project_id}/preview` - Preview export

### Reference ePub
- `POST /api/v1/reference/{project_id}/upload` - Upload reference
- `POST /api/v1/reference/{project_id}/match` - Auto-match paragraphs
- `GET /api/v1/reference/{project_id}/matches` - Get matches

### Preview
- `GET /api/v1/preview/{project_id}/chapters` - List chapters
- `GET /api/v1/preview/{project_id}/toc` - Get hierarchical TOC
- `GET /api/v1/preview/{project_id}/chapter/{chapter_id}` - Get chapter content

## Language Policy

### Allowed Chinese Character Locations

Chinese characters are **ONLY** permitted in:
1. `frontend/src/i18n/locales/zh.json`
2. `backend/prompts/**/*.md` (LLM prompt templates)
3. User-facing conversation (in Claude Code chat)

### Forbidden Chinese Character Locations

Chinese characters are **STRICTLY FORBIDDEN** in:
- Source code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`)
- Code comments, docstrings, variable names
- Log messages, error messages in code
- README and documentation files
- Configuration files (except i18n locale files)
- Test files

## Safe String Handling Policy

### The Problem

Multi-byte characters (Chinese, Japanese, emoji, etc.) use 2-4 bytes in UTF-8. Unsafe string truncation can:
1. Break in the middle of a character, causing invalid UTF-8
2. Crash native code (Rust, C++) that expects valid UTF-8 at specific byte positions
3. Create malformed JSON when truncating serialized data

### Forbidden Patterns

**NEVER** use direct string slicing for truncation that may contain multi-byte characters:

```python
# FORBIDDEN in Python
text[:100] + "..."
value[:max_chars]
str(obj)[:50]
```

```typescript
// FORBIDDEN in TypeScript/JavaScript
str.slice(0, 100) + '...'
str.substring(0, 50) + '...'
JSON.stringify(value).slice(0, 80)
```

### Required: Use Safe Truncation Utilities

**Backend (Python):**
```python
from app.utils.text import safe_truncate, safe_truncate_json

safe_truncate(text, 100)
safe_truncate_json(value, 80)
```

**Frontend (TypeScript):**
```typescript
import { safeTruncate, safeTruncateJson } from '../utils/text'

safeTruncate(text, 100)
safeTruncateJson(value, 80)
```

### Exceptions (Direct Slicing OK)

Direct slicing is acceptable ONLY for guaranteed ASCII strings:
- UUIDs, hex hashes, URL slugs
- Known safe boundaries after `split()`

## Pre-commit Hooks

- `scripts/dev/check_chinese.sh` - Verifies no Chinese outside allowed locations
- `scripts/dev/check_unsafe_truncation.sh` - Detects dangerous truncation patterns

Both are integrated as Claude Code hooks for automated enforcement.

## Project Structure

```
epub_translate/
├── backend/                    # Python FastAPI backend
│   ├── app/                    # Application code
│   │   ├── api/v1/routes/      # API endpoints
│   │   ├── core/               # Business logic (epub, llm, translation)
│   │   ├── models/             # Database models & schemas
│   │   └── utils/              # Utility functions
│   ├── prompts/                # Global LLM prompt templates
│   └── migrations/             # Alembic database migrations
│
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── components/         # React components
│       ├── pages/              # Page components
│       ├── stores/             # Zustand state stores
│       ├── services/           # API client
│       ├── i18n/locales/       # Translations (en.json, zh.json)
│       └── utils/              # Utility functions
│
├── epub_sample/                # Sample EPUB files for testing (easy access)
│
├── data/                       # Data files
│   └── temp/                   # Temporary upload/output files
│
├── projects/                   # Project data storage (per-project)
│   └── {project_id}/
│       ├── uploads/            # Original & reference EPUBs
│       ├── exports/            # Generated output files
│       ├── prompts/            # Custom prompt overrides
│       ├── cache/              # LLM response cache
│       └── variables.json      # Custom template variables
│
├── scripts/                    # Utility scripts
│   ├── dev/                    # Development scripts
│   │   ├── restart.sh          # Restart services
│   │   ├── check_chinese.sh    # Chinese character check
│   │   └── check_unsafe_truncation.sh
│   └── migrations/             # Database migration scripts
│
├── tests/                      # Test files
│   └── fixtures/               # Test data and payloads
│
├── docs/                       # Documentation
├── shared/                     # Shared schemas (frontend + backend)
│
├── CLAUDE.md                   # This file
├── README.md                   # Project readme
└── start.sh                    # Main startup script
```

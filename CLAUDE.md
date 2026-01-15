# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Quick Reference

| Item | Value |
|------|-------|
| Frontend | http://localhost:5200 |
| Backend API | http://localhost:5300 |
| API Docs | http://localhost:5300/docs |
| Backend Port Env | `PORT=5300` in `backend/.env` |
| Frontend Port Env | `VITE_PORT=5200` in `frontend/.env` |

---

## Development Commands

### Quick Start
```bash
./start.sh                    # Start both services (interactive, auto-installs deps)
./scripts/dev/restart.sh      # Restart services (background with nohup)
```

### Backend (FastAPI + Python 3.11+)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 5300

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
npm run dev                   # Development server on port 5200
npm run build                 # TypeScript check + Vite build
npm run lint                  # ESLint with --max-warnings 0
```

---

## Project Overview

**ePub Translator** is an AI-powered application for translating English ePub books to Chinese with:
- Context-aware translation using book analysis
- Reference ePub support for consistency
- Multi-provider LLM integration (OpenAI, Anthropic, Google, Qwen, DeepSeek)
- 4-step workflow: Analysis → Translation → Proofreading → Export

---

## 4-Step Workflow

### Step 1: Analysis (`/project/{id}/analysis`)
- LLM analyzes sample paragraphs to extract book metadata
- Extracts: writing style, tone, target audience, terminology glossary, translation principles
- SSE streaming for real-time progress display
- User confirms/edits analysis before proceeding

### Step 2: Translation (`/project/{id}/translate`)
- Chapter-by-chapter translation with paragraph granularity
- Context includes previous/next paragraphs for coherence
- Optional reference ePub matching for consistency
- Lock/unlock paragraphs, retranslate individuals
- Discussion chat for translation reasoning with LLM

### Step 3: Proofreading (`/project/{id}/proofread`)
- LLM generates improvement suggestions (accuracy, naturalness, style)
- Accept/reject/modify each suggestion
- Quick recommendation for manual feedback
- Session-based proofreading rounds

### Step 4: Export (`/project/{id}/export`)
- Bilingual (original + translation) or translation-only
- ePub or HTML output formats
- Chapter selection for partial export
- Preview before download

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Analysis   │  │ Translation │  │ Proofreading│  │   Export   │ │
│  │    Page     │  │    Page     │  │    Page     │  │    Page    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         └────────────────┴────────────────┴───────────────┘         │
│                              │ Axios                                │
└──────────────────────────────┼──────────────────────────────────────┘
                               │ HTTP/SSE
┌──────────────────────────────┼──────────────────────────────────────┐
│                           Backend (FastAPI)                         │
│  ┌───────────────────────────┴───────────────────────────────────┐ │
│  │                      API Routes (/api/v1/)                     │ │
│  └───────────────────────────┬───────────────────────────────────┘ │
│         ┌────────────────────┼────────────────────────┐            │
│  ┌──────▼──────┐  ┌──────────▼──────────────┐  ┌──────▼──────┐     │
│  │  Analysis   │  │  Translation Pipeline   │  │ Proofreading│     │
│  │  Service    │  │  Context → Prompt →     │  │   Service   │     │
│  └──────┬──────┘  │  LLM → Output → Result  │  └──────┬──────┘     │
│         │         └──────────┬──────────────┘         │            │
│         └────────────────────┼────────────────────────┘            │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐ │
│  │                    UnifiedLLMGateway                          │ │
│  │  (OpenAI | Anthropic | Gemini | Qwen | DeepSeek | Ollama)    │ │
│  └───────────────────────────┬───────────────────────────────────┘ │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐ │
│  │              SQLite Database (async) + File Storage           │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Technology Stack
- **Framework**: FastAPI (async Python)
- **Database**: SQLite with aiosqlite (async)
- **ORM**: SQLAlchemy 2.0 (async sessions)
- **LLM Abstraction**: LiteLLM
- **EPUB Parsing**: lxml
- **Migrations**: Alembic

### Directory Structure
```
backend/
├── app/
│   ├── api/v1/routes/        # API endpoints (11 modules)
│   │   ├── upload.py         # Project upload & management
│   │   ├── analysis.py       # Book analysis
│   │   ├── translation.py    # Translation workflow (~1,373 lines)
│   │   ├── proofreading.py   # Proofreading sessions
│   │   ├── export.py         # Export ePub/HTML
│   │   ├── preview.py        # Chapter preview
│   │   ├── reference.py      # Reference ePub matching
│   │   ├── llm_settings.py   # LLM configuration CRUD
│   │   ├── workflow.py       # Workflow status
│   │   ├── prompts.py        # Prompt templates
│   │   └── feature_flags.py  # Feature flags
│   ├── core/                 # Business logic
│   │   ├── analysis/         # Book analysis service
│   │   ├── epub/             # EPUB parsing & generation
│   │   │   ├── parser_v2.py  # Full lxml-based parser
│   │   │   ├── generator.py  # Legacy EPUB generation
│   │   │   └── reconstructor.py  # Bilingual EPUB builder
│   │   ├── export/           # Export (EPUB, HTML, PDF)
│   │   ├── llm/              # LLM gateway & config
│   │   │   ├── gateway.py    # UnifiedLLMGateway
│   │   │   ├── runtime_config.py  # LLMRuntimeConfig (single source of truth)
│   │   │   └── config_service.py  # DB CRUD for configs
│   │   ├── matching/         # Reference paragraph matching
│   │   ├── prompts/          # Prompt template system
│   │   │   ├── variable_builder.py  # UnifiedVariableBuilder
│   │   │   └── loader.py     # Template loading & rendering
│   │   ├── proofreading/     # Proofreading service
│   │   └── translation/      # Translation pipeline
│   │       ├── pipeline/     # Core pipeline
│   │       │   ├── pipeline.py       # TranslationPipeline
│   │       │   ├── prompt_engine.py  # PromptEngine
│   │       │   ├── context_builder.py # ContextBuilder
│   │       │   ├── llm_gateway.py    # LLM abstraction
│   │       │   ├── output_processor.py
│   │       │   └── orchestrator.py   # End-to-end workflow
│   │       ├── strategies/   # Translation modes
│   │       │   ├── direct.py         # Simple one-pass
│   │       │   ├── author_aware.py   # Full analysis context
│   │       │   └── optimization.py   # Refine existing
│   │       └── models/       # Data models
│   │           ├── context.py        # TranslationContext
│   │           ├── prompt.py         # PromptBundle
│   │           └── result.py         # TranslationResult
│   ├── models/
│   │   ├── database/         # SQLAlchemy models (15 tables)
│   │   └── schemas/          # Pydantic request/response
│   ├── utils/                # Utilities (text.py, etc.)
│   └── config.py             # Application settings
├── prompts/                  # Prompt template files (.md)
│   ├── analysis/
│   ├── translation/
│   ├── optimization/
│   ├── proofreading/
│   └── VARIABLES.md          # Complete variable reference
└── migrations/               # Alembic migrations
```

### Translation Pipeline

The core translation uses a **strategy pattern with pipeline architecture**:

```
TranslationContext → PromptEngine → PromptBundle → LLMGateway → OutputProcessor → Result
```

**Pipeline Flow:**

1. **ContextBuilder** assembles `TranslationContext`:
   - Source material (original paragraph)
   - Previous/next paragraphs (for coherence)
   - Project metadata
   - Book analysis (writing_style, tone, terminology)
   - Reference translation (if available)

2. **PromptEngine** builds `PromptBundle`:
   - Loads system/user prompts from `.md` files
   - UnifiedVariableBuilder constructs all variables
   - Substitutes `{{variable}}` placeholders
   - Returns prompts with temperature/max_tokens

3. **LLMGateway** calls LLM:
   - Uses LiteLLM for provider abstraction
   - Applies LLMRuntimeConfig parameters
   - Handles streaming and structured output

4. **OutputProcessor** extracts result:
   - Parses LLM response
   - Extracts translation text
   - Returns TranslationResult

**Translation Strategies:**

| Mode | Strategy | Description |
|------|----------|-------------|
| `DIRECT` | `DirectTranslationStrategy` | Simple one-pass translation |
| `AUTHOR_AWARE` | `AuthorAwareStrategy` | Full analysis context (recommended) |
| `OPTIMIZATION` | `OptimizationStrategy` | Refine existing translations |

### Database Models

| Model | File | Purpose |
|-------|------|---------|
| `Project` | `project.py` | Book metadata, status flags |
| `Chapter` | `chapter.py` | Hierarchical structure |
| `Paragraph` | `paragraph.py` | Original text, position |
| `Translation` | `translation.py` | Translated text, version, lock |
| `TranslationTask` | `translation.py` | Background task progress |
| `BookAnalysis` | `book_analysis.py` | Analysis results (JSON) |
| `AnalysisTask` | `analysis_task.py` | Analysis progress |
| `LLMConfiguration` | `llm_configuration.py` | Provider configs, API keys |
| `ProofreadingSession` | `proofreading.py` | Proofreading rounds |
| `ProofreadingSuggestion` | `proofreading.py` | Individual suggestions |
| `ReferenceEPUB` | `reference_epub.py` | Reference ePub metadata |
| `ParagraphMatch` | `paragraph_match.py` | Reference matching |
| `TranslationConversation` | `translation_conversation.py` | Discussion chat |
| `PromptTemplate` | `prompt_template.py` | Custom prompts |

---

## Frontend Architecture

### Technology Stack
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand (persisted to localStorage)
- **Data Fetching**: TanStack React Query
- **HTTP Client**: Axios
- **Styling**: Tailwind CSS (dark mode via `class`)
- **Icons**: Lucide React

### Directory Structure
```
frontend/src/
├── App.tsx                   # Router configuration
├── main.tsx                  # Bootstrap with theme/language init
├── components/
│   ├── common/               # Reusable components
│   │   ├── ThemeToggle.tsx   # Dark/light mode toggle
│   │   ├── LanguageToggle.tsx # EN/ZH switcher
│   │   ├── LLMConfigSelector.tsx # LLM config dropdown
│   │   ├── PromptTemplateSelector.tsx # Prompt selection
│   │   ├── PromptPreviewModal.tsx # Preview rendered prompts
│   │   ├── TreeChapterList.tsx # Hierarchical chapter navigation
│   │   └── ResizeHandle.tsx  # Panel resize
│   ├── layout/
│   │   └── Layout.tsx        # Header, nav, step indicator
│   ├── workflow/             # Workflow-specific
│   │   ├── AnalysisFieldCard.tsx
│   │   ├── AnalysisStreamingPreview.tsx
│   │   ├── ReferencePanel.tsx
│   │   └── WorkflowChapterList.tsx
│   ├── translation/
│   │   └── ReasoningChatModal.tsx # Discussion chat
│   └── preview/
│       └── PreviewModal.tsx
├── pages/
│   ├── HomePage.tsx          # Project list
│   ├── UploadPage.tsx        # EPUB upload
│   ├── SettingsPage.tsx      # LLM configuration
│   ├── PromptManagementPage.tsx # Prompt editor
│   └── workflow/
│       ├── ProjectLayout.tsx # Shared workflow layout
│       ├── AnalysisPage.tsx
│       ├── TranslateWorkflowPage.tsx
│       ├── ProofreadPage.tsx
│       ├── ExportPage.tsx
│       └── ParameterReviewPage.tsx # Debug variables
├── stores/
│   ├── appStore.ts           # Theme, language, UI state
│   └── settingsStore.ts      # LLM configs (from backend)
├── services/api/
│   └── client.ts             # Typed API client (~800 lines)
├── i18n/
│   ├── index.ts              # Translation system
│   └── locales/
│       ├── en.json           # English (~566 lines)
│       └── zh.json           # Chinese (~662 lines)
├── utils/
│   ├── text.ts               # Safe string truncation
│   └── workflow.ts           # Workflow utilities
├── hooks/                    # Custom React hooks
└── types/                    # TypeScript definitions
```

### State Management

**appStore.ts** (persisted to localStorage):
```typescript
{
  language: 'zh' | 'en',           // UI language
  theme: 'light' | 'dark',         // Color theme
  fontSize: 'small' | 'medium' | 'large',
  panelWidths: { left, right },    // Resizable panels
  // Transient (not persisted):
  translationProgress: { ... },    // Header progress display
  workflowStatus: { ... },         // Step indicator
  isAnalyzing: boolean
}
```

**settingsStore.ts** (loaded from backend):
```typescript
{
  llmConfigs: LLMConfig[],         // All saved configs
  activeConfigId: string | null,   // Currently selected
  isLoading: boolean,
  error: string | null
}
```

### Key Features
- **Dark Mode**: System preference detection + manual toggle
- **Bilingual UI**: English/Chinese with persistent preference
- **Resizable Panels**: Drag-to-resize chapter/content panels
- **Real-time Progress**: SSE for analysis, polling for translation
- **Prompt Preview**: See rendered prompts before LLM calls

---

## LLM Integration

### Supported Providers

| Provider | Models | Env Variable |
|----------|--------|--------------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1, o1-mini | `OPENAI_API_KEY` |
| Anthropic | claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus | `ANTHROPIC_API_KEY` |
| Google | gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash | `GEMINI_API_KEY` |
| Alibaba Qwen | qwen-plus, qwen-turbo | `DASHSCOPE_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| OpenRouter | Various (custom base URL) | `OPENROUTER_API_KEY` |
| Ollama | Local models (custom base URL) | N/A |

### Configuration Resolution (Priority Order)
1. **Request override** - Direct params in API call (highest)
2. **Config by ID** - Specific stored config
3. **Active config** - `is_active=true` in DB
4. **Default config** - `is_default=true` in DB
5. **Environment variables** (lowest)

### Stage-Specific Defaults

| Stage | Temperature | Max Tokens |
|-------|-------------|------------|
| Analysis | 0.3 | 8192 |
| Translation | 0.5 | 4096 |
| Optimization | 0.3 | 4096 |
| Proofreading | 0.3 | 2048 |

### LLMRuntimeConfig

Single source of truth for LLM parameters (ensures params flow to LLM calls):
```python
@dataclass
class LLMRuntimeConfig:
    provider: str           # openai, anthropic, gemini, etc.
    model: str              # gpt-4o-mini, claude-3-5-sonnet, etc.
    api_key: str            # From DB or env vars
    base_url: Optional[str] # Custom endpoint (Ollama, OpenRouter)
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
```

---

## Prompt System

### Template Structure
```
backend/prompts/
├── analysis/
│   ├── system.default.md           # Default system prompt
│   ├── system.reformed-theology.md # Theology-specific
│   └── user.default.md             # Default user prompt
├── translation/
│   ├── system.default.md
│   ├── system.reformed-theology.md
│   └── user.default.md
├── optimization/
│   ├── system.default.md
│   └── user.default.md
├── proofreading/
│   ├── system.default.md
│   ├── system.reformed-theology.md
│   └── user.default.md
└── VARIABLES.md                    # Complete reference
```

### Variable Namespaces

| Namespace | Description | Examples |
|-----------|-------------|----------|
| `project.*` | Book metadata | `{{project.title}}`, `{{project.author}}`, `{{project.source_language}}` |
| `content.*` | Current text | `{{content.source}}`, `{{content.target}}`, `{{content.chapter_title}}` |
| `context.*` | Adjacent paragraphs | `{{context.previous_source}}`, `{{context.previous_target}}`, `{{context.next_source}}` |
| `derived.*` | Analysis results | `{{derived.writing_style}}`, `{{derived.tone}}`, `{{derived.terminology_table}}` |
| `pipeline.*` | Previous step outputs | `{{pipeline.reference_translation}}`, `{{pipeline.suggested_changes}}` |
| `user.*` | Custom variables | From `projects/{id}/variables.json` |
| `meta.*` | Runtime values | `{{meta.stage}}`, `{{meta.word_count}}`, `{{meta.chapter_index}}` |

### Derived Variables (from Book Analysis)

Extracted from `BookAnalysis.raw_analysis` JSON by `UnifiedVariableBuilder`:

**Core fields:**
- `derived.author_name`, `derived.author_biography`
- `derived.writing_style`, `derived.tone`, `derived.target_audience`
- `derived.genre_conventions`
- `derived.terminology_table` (formatted as markdown)

**Translation principles:**
- `derived.priority_order` (e.g., "Faithfulness, Clarity, Elegance")
- `derived.faithfulness_boundary`
- `derived.permissible_adaptation`
- `derived.style_constraints`
- `derived.red_lines`
- `derived.custom_guidelines`

**Boolean flags:**
- `derived.has_analysis`, `derived.has_writing_style`, `derived.has_terminology`
- `derived.has_translation_principles`, `derived.has_author_biography`

### Template Syntax (Handlebars-like)
```handlebars
{{variable}}                         # Simple substitution
{{namespace.variable}}               # Namespaced (recommended)
{{variable | default:"fallback"}}    # With fallback value

{{#if variable}} ... {{/if}}         # Conditional block
{{#unless variable}} ... {{/unless}} # Negation
{{#each array}} {{this}} {{/each}}   # Loop over array
{{#each dict}} {{@key}}: {{this}} {{/each}}  # Loop over dict
```

### Project-Specific Overrides
- **Custom prompts**: `projects/{project_id}/prompts/{stage}/user.md`
- **Custom variables**: `projects/{project_id}/variables.json` → `user.*` namespace

---

## API Endpoints

### Project Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Upload EPUB, create project |
| `GET` | `/api/v1/projects` | List all projects |
| `GET` | `/api/v1/projects/{id}` | Get project details |
| `DELETE` | `/api/v1/projects/{id}` | Delete project |
| `POST` | `/api/v1/projects/{id}/favorite` | Toggle favorite |
| `POST` | `/api/v1/projects/{id}/reparse` | Re-parse EPUB |

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/analysis/{id}/start` | Start analysis (blocking) |
| `POST` | `/api/v1/analysis/{id}/start-stream` | Start with SSE progress |
| `GET` | `/api/v1/analysis/{id}` | Get analysis results |
| `PUT` | `/api/v1/analysis/{id}` | Update/confirm analysis |
| `POST` | `/api/v1/analysis/{id}/regenerate-field` | Regenerate specific field |

### Translation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/translation/start` | Start translation task |
| `GET` | `/api/v1/translation/status/{task_id}` | Get task progress |
| `POST` | `/api/v1/translation/pause/{task_id}` | Pause task |
| `POST` | `/api/v1/translation/resume/{task_id}` | Resume task |
| `POST` | `/api/v1/translation/cancel/{task_id}` | Cancel task |
| `GET` | `/api/v1/translation/tasks/{project_id}` | List project tasks |
| `DELETE` | `/api/v1/translation/chapter/{chapter_id}` | Clear chapter translations |
| `POST` | `/api/v1/translation/retranslate/{paragraph_id}` | Retranslate paragraph |
| `GET` | `/api/v1/translation/paragraph/{paragraph_id}` | Get latest translation |
| `PUT` | `/api/v1/translation/paragraph/{paragraph_id}` | Update translation |
| `PUT` | `/api/v1/translation/paragraph/{paragraph_id}/confirm` | Lock/unlock |
| `GET` | `/api/v1/translation/modes` | List translation modes |

### Translation Conversation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/translation/conversation/{id}/start` | Start discussion |
| `GET` | `/api/v1/translation/conversation/{id}` | Get conversation |
| `POST` | `/api/v1/translation/conversation/{id}/message` | Send message |
| `POST` | `/api/v1/translation/conversation/{id}/apply` | Apply suggestion |
| `DELETE` | `/api/v1/translation/conversation/{id}` | Clear conversation |

### Proofreading
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/proofreading/{project_id}/start` | Start session |
| `GET` | `/api/v1/proofreading/{session_id}/suggestions` | Get suggestions |
| `PUT` | `/api/v1/proofreading/suggestion/{id}` | Accept/reject/modify |
| `POST` | `/api/v1/proofreading/quick-recommendation` | Get recommendation |

### Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/export/{id}` | Export bilingual EPUB (legacy) |
| `POST` | `/api/v1/export/{id}/v2` | Export with new reconstructor |
| `POST` | `/api/v1/export/{id}/html` | Export HTML |
| `GET` | `/api/v1/export/{id}/preview` | Preview export |

### Reference EPUB
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reference/{id}/upload` | Upload reference |
| `POST` | `/api/v1/reference/{id}/match` | Auto-match paragraphs |
| `GET` | `/api/v1/reference/{id}/matches` | Get matches |

### LLM Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/settings/llm` | Create configuration |
| `GET` | `/api/v1/settings/llm` | List configurations |
| `GET` | `/api/v1/settings/llm/{id}` | Get specific config |
| `PUT` | `/api/v1/settings/llm/{id}` | Update configuration |
| `DELETE` | `/api/v1/settings/llm/{id}` | Delete configuration |
| `POST` | `/api/v1/settings/llm/{id}/test` | Test configuration |

### Preview
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/preview/{id}/chapters` | List chapters |
| `GET` | `/api/v1/preview/{id}/toc` | Get hierarchical TOC |
| `GET` | `/api/v1/preview/{id}/chapter/{chapter_id}` | Get chapter content |

### Prompts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/prompts/{category}` | Get prompt templates |
| `POST` | `/api/v1/prompts/{category}/{template}` | Save custom prompt |

### Feature Flags
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/feature-flags` | Get all feature flags |

---

## Project File Structure

```
epub_translator/
├── backend/                    # Python FastAPI backend
├── frontend/                   # React + TypeScript frontend
├── projects/                   # Per-project data storage
│   └── {project_id}/
│       ├── uploads/            # Original & reference EPUBs
│       ├── exports/            # Generated output files
│       ├── prompts/            # Custom prompt overrides
│       ├── cache/              # LLM response cache
│       └── variables.json      # Custom template variables
├── data/temp/                  # Temporary upload/output files
├── epub_sample/                # Sample EPUB files for testing
├── scripts/
│   ├── dev/
│   │   ├── restart.sh          # Restart services
│   │   ├── check_chinese.sh    # Chinese character check
│   │   └── check_unsafe_truncation.sh
│   └── migrations/             # Database migration scripts
├── docs/                       # Documentation
├── tests/                      # Test files
│   └── fixtures/               # Test data
├── .claude/
│   └── commands/
│       └── restart.md          # /restart skill
├── CLAUDE.md                   # This file
├── start.sh                    # Main startup script
└── README.md                   # Project readme
```

---

## Environment Configuration

### Backend (`backend/.env`)
```bash
# Server
HOST=0.0.0.0
PORT=5300
FRONTEND_PORT=5200
DEBUG=true

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
DASHSCOPE_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

# Feature Flags
ENABLE_EPUB_EXPORT=false
```

### Frontend (`frontend/.env`)
```bash
VITE_PORT=5200
VITE_API_HOST=localhost
VITE_API_PORT=5300
```

---

## Language Policy

### Allowed Chinese Character Locations
1. `frontend/src/i18n/locales/zh.json`
2. `backend/prompts/**/*.md` (LLM prompt templates)
3. User-facing conversation (in Claude Code chat)

### Forbidden Chinese Character Locations
- Source code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`)
- Code comments, docstrings, variable names
- Log messages, error messages in code
- README and documentation files
- Configuration files (except i18n locale files)
- Test files

---

## Safe String Handling Policy

### The Problem
Multi-byte characters (Chinese, Japanese, emoji) use 2-4 bytes in UTF-8. Unsafe truncation can:
1. Break mid-character, causing invalid UTF-8
2. Crash native code expecting valid UTF-8
3. Create malformed JSON

### Forbidden Patterns
```python
# FORBIDDEN in Python
text[:100] + "..."
value[:max_chars]
```

```typescript
// FORBIDDEN in TypeScript
str.slice(0, 100) + '...'
str.substring(0, 50) + '...'
```

### Required: Use Safe Truncation Utilities
```python
# Backend
from app.utils.text import safe_truncate, safe_truncate_json
safe_truncate(text, 100)
```

```typescript
// Frontend
import { safeTruncate, safeTruncateJson } from '../utils/text'
safeTruncate(text, 100)
```

### Exceptions (Direct Slicing OK)
- UUIDs, hex hashes (guaranteed ASCII)
- Known safe boundaries after `split()`

---

## Pre-commit Hooks

| Script | Purpose |
|--------|---------|
| `scripts/dev/check_chinese.sh` | Verify no Chinese outside allowed locations |
| `scripts/dev/check_unsafe_truncation.sh` | Detect dangerous truncation patterns |

---

## Key Design Patterns

1. **Strategy Pattern** - Translation modes (DIRECT, AUTHOR_AWARE, OPTIMIZATION)
2. **Pipeline Architecture** - Context → Prompt → LLM → Output → Result
3. **Factory Pattern** - LLM provider selection via LLMConfigResolver
4. **Repository Pattern** - Database models with clear separation
5. **Dependency Injection** - FastAPI `Depends` for DB sessions

## Key Architectural Decisions

1. **Single Source of Truth for Variables** - `UnifiedVariableBuilder` handles all stages
2. **Single LLM Gateway** - `UnifiedLLMGateway` abstracts all providers
3. **Config Flows Through** - `LLMRuntimeConfig` ensures params reach LLM calls
4. **Async-First Database** - All DB operations use AsyncSession
5. **Project-Scoped Storage** - Each project has isolated file storage


<h1 align="center">📖 ePub Translator</h1>

<div align="center">
  <a href="https://github.com/FelixZhang1020/epub_translator/stargazers"><img src="https://img.shields.io/github/stars/FelixZhang1020/epub_translator?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/FelixZhang1020/epub_translator/actions"><img src="https://img.shields.io/badge/CI-status-grey?style=flat-square" alt="CI Status"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a><img src="https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js 18+"></a>
</div>

<div align="center">

**[中文文档](README_ZH.md) · [License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md)**

</div>

---

LLM-powered pipeline that translates English ePub books into Chinese while keeping layout, tone, and context intact. Exports are restricted to plain-text PDF/HTML (no ePub) to reduce copyright risk.

## Background

In years of study and close reading, I kept running into the same problem: foundational books in some fields simply don’t have dependable Chinese editions.

- *The Anxiety of Influence* (Harold Bloom, 1973) coined the core theory of “anxiety of influence,” shaping how the English-speaking world thinks about literary tradition, originality, and canon formation. In Chinese, the terminology is so abstract—and handled so inconsistently across translations—that the book often stays “referenced” but rarely gets understood or digested through stable side-by-side reading.
- *The Presentation of Self in Everyday Life* (Erving Goffman, 1956) reframed social interaction with “stage/role/situation” metaphors, influencing sociology, anthropology, communications, and cultural studies. Chinese readers face divergent styles across translations and inconsistent key concepts between chapters or editions, making systematic study and citation costly.
- *Church Dogmatics* (Karl Barth, 1932–1967) is often ranked with Calvin’s *Institutes* for depth, scale, and influence. The barrier for many Chinese readers isn’t the content itself but the sheer size, translation difficulty, and scattered resources—true side-by-side reading is nearly impossible.

These aren’t obscure titles; they’re the wells people keep drawing from. The blocker isn’t willingness to read the originals—it’s having a practical, copyright-respecting way to do sustained, consistent, revisitable parallel reading.

Out of that personal experience, I built this ePub translation tool. I couldn’t find a GitHub project designed around original/translation comparison, close reading, and long-form study, so I leaned on Claude Code and built the pipeline from scratch to help readers who need high-quality materials but are constrained by language and uneven translations.

To respect copyright and minimize risk, translations stay inside the tool for side-by-side reading or export only as plain-text PDF/HTML. No ePub generation or distribution.

## Prompt Engineering

The tool ships with a battle-tested set of translation guides, workflow constraints, and structured prompt engineering plus parameter defaults. This baseline alone outperforms “quick prompts and go,” giving whole-book translation a stable floor.

On top of that, quality still depends on two factors working together:
1) The capability of the LLM you choose—this sets the ceiling for understanding, long-range consistency, and handling complex syntax.
2) Prompt design tailored to the specific book—this drives terminology choices, tone control, and overall readability.

So this project isn’t just a shell; it’s a translation system with a defined baseline. And it intentionally leaves headroom for power users: when prompts are refined for a specific book, quality can climb meaningfully beyond the built-in defaults.

## Overview

ePub Translator is a full-stack app that analyzes, translates, and proofreads ePub books, then exports bilingual output. It supports multiple LLM providers and reference matching to keep terminology consistent across chapters.

## Highlights

- **Multi-LLM**: OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, DeepSeek
- **Guided pipeline**: Analysis → Translation → Proofreading → Export with chapter-level state
- **Style extraction**: Automatically captures tone, terminology, and writing style
- **Reference matching**: Aligns paragraphs with existing translations for consistency
- **Prompt control**: System/user prompts with variables, reusable templates
- **Plain-text export**: Outputs bilingual PDF/HTML only (no ePub) to avoid copyright issues
- **Web UI**: Preview chapters, edit translations, and rerun steps as needed

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Uvicorn |
| Frontend | React + Vite + TypeScript, Zustand, Ant Design |
| Storage | SQLite by default (override via `DATABASE_URL`) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # add API keys or tweak ports as needed
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env  # adjust API host/port if changed
```

### Run
```bash
# Option A: manual
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# Option B: from repo root (auto installs on first run)
./start.sh
```

Open http://localhost:5173 and API docs at http://localhost:8000/docs.

## Usage Workflow

1. Upload an English ePub to create a project
2. Set LLM provider and API key (via UI or backend `.env`)
3. Run **Analysis** to extract tone, style, and terminology
4. Run **Translation**; reference matching keeps phrasing consistent
5. Use **Proofreading** to refine outputs or edit paragraphs manually
6. **Export** bilingual output as plain-text PDF or HTML (no ePub) and download from the UI
7. Manage prompts/reference files under `backend/prompts/` or in the UI

## Configuration

<details>
<summary><b>Backend Environment Variables</b> (<code>backend/.env</code>)</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `true` |
| `HOST` | Backend host | `0.0.0.0` |
| `PORT` | Backend port | `8000` |
| `FRONTEND_PORT` | Port used for CORS allowlist | `5173` |
| `DATABASE_URL` | Database URL (SQLite by default) | `sqlite+aiosqlite:///./epub_translator.db` |
| `UPLOAD_DIR` | Directory for temporary uploads | `data/temp/uploads` |
| `OUTPUT_DIR` | Directory for temporary outputs | `data/temp/outputs` |
| `MAX_UPLOAD_SIZE_MB` | Maximum upload file size in MB | `100` |
| `API_AUTH_TOKEN` | API authentication token (optional) | - |
| `REQUIRE_AUTH_ALL` | Require auth on all endpoints | `false` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key | - |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `DASHSCOPE_API_KEY` | Alibaba Qwen API key | - |
| `DEEPSEEK_API_KEY` | DeepSeek API key | - |
| `OPENROUTER_API_KEY` | OpenRouter multi-provider key | - |
| `DEFAULT_CHUNK_SIZE` | Characters per translation chunk | `500` |
| `MAX_RETRIES` | Retry count for LLM calls | `3` |
| `RETRY_DELAY` | Seconds between retries | `1.0` |
| `CORS_ORIGINS` | Allowed origins list | `["http://localhost:5173"]` |

</details>

<details>
<summary><b>Frontend Environment Variables</b> (<code>frontend/.env</code>)</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_PORT` | Frontend dev server port | `5173` |
| `VITE_API_HOST` | Backend host | `localhost` |
| `VITE_API_PORT` | Backend port | `8000` |

</details>

## Project Structure

```
epub_translator/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # REST endpoints
│   │   ├── core/             # Pipeline + services
│   │   │   ├── analysis/     # Book analysis
│   │   │   ├── epub/         # ePub parsing/export
│   │   │   ├── llm/          # Provider adapters
│   │   │   ├── matching/     # Reference alignment
│   │   │   ├── proofreading/ # Proofreading routines
│   │   │   ├── prompts/      # Prompt loading/variables
│   │   │   └── translation/  # Translation pipeline
│   │   └── models/database/  # SQLAlchemy models
│   ├── prompts/              # Prompt templates
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/       # UI components
│       ├── pages/            # Views
│       ├── services/api/     # API client
│       ├── stores/           # Zustand state
│       └── i18n/             # EN/ZH copy
├── scripts/                  # Utility scripts
├── start.sh                  # One-shot setup + dev servers
└── tests/                    # Test fixtures
```

## API Overview

| Endpoint | Description |
|----------|-------------|
| `/api/v1/upload` | ePub upload and project creation |
| `/api/v1/analysis` | Book content analysis |
| `/api/v1/translation` | Translation workflow |
| `/api/v1/proofreading` | Proofreading suggestions |
| `/api/v1/export` | PDF/HTML (plain-text) export |
| `/api/v1/prompts` | Prompt template management |
| `/api/v1/llm-settings` | LLM configuration |
| `/api/v1/workflow` | Workflow state management |
| `/api/v1/reference` | Reference ePub matching |
| `/api/v1/preview` | Chapter content preview |

## Prompt Variables

Templates support `{{variable}}` substitution:

| Namespace | Variables |
|-----------|-----------|
| `project.*` | `title`, `author`, `source_language`, `target_language` |
| `content.*` | `source_text`, `paragraph_index`, `chapter_index` |
| `pipeline.*` | `existing_translation`, `reference_translation` |
| `derived.*` | `writing_style`, `tone`, `terminology_table` |
| `user.*` | Custom user-defined variables |

## License

MIT

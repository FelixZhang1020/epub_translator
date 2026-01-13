# ePub Translator

<div align="center">
  <a href="https://github.com/FelixZhang1020/epub_translator/stargazers"><img src="https://img.shields.io/github/stars/FelixZhang1020/epub_translator?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/FelixZhang1020/epub_translator/actions"><img src="https://img.shields.io/badge/CI-status-grey?style=flat-square" alt="CI Status"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a><img src="https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js 18+"></a>
</div>

<div align="center">

**[License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md) · [中文文档](README_ZH.md)**

</div>

---

LLM-powered pipeline that translates English ePub books into Chinese while keeping layout, tone, and context intact.

## Overview

ePub Translator is a full-stack app that analyzes, translates, and proofreads ePub books, then exports bilingual output. It supports multiple LLM providers and reference matching to keep terminology consistent across chapters.

## Highlights

- **Multi-LLM**: OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, DeepSeek
- **Guided pipeline**: Analysis → Translation → Proofreading → Export with chapter-level state
- **Style extraction**: Automatically captures tone, terminology, and writing style
- **Reference matching**: Aligns paragraphs with existing translations for consistency
- **Prompt control**: System/user prompts with variables, reusable templates
- **Bilingual export**: Generates ePub with original + translated text
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
6. **Export** a bilingual ePub and download from the UI
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
| `UPLOAD_DIR` | Directory for uploaded epubs | `./uploads` |
| `OUTPUT_DIR` | Directory for generated exports | `./outputs` |
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
| `/api/v1/export` | ePub export |
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

# EPUB Translator

A comprehensive EPUB translation tool powered by LLMs. Translate English EPUB books to Chinese while preserving formatting, style, and context.

## Features

- **Multi-LLM Support**: OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, DeepSeek
- **4-Step Workflow**: Analysis → Translation → Proofreading → Export
- **Book Analysis**: Automatic extraction of writing style, tone, and terminology
- **Reference Matching**: Match paragraphs with existing translations for consistency
- **Prompt Management**: Customizable system and user prompts with variable support
- **Bilingual Export**: Generate translated EPUB with original/translated text

## Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm or npm

## Installation

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env to add your API keys (optional - can also set in UI)
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file (optional)
cp .env.example .env
```

## Running the Application

### Start Backend Server

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Project Structure

```
epub_translate/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # API endpoints (10 modules)
│   │   ├── core/             # Business logic
│   │   │   ├── analysis/     # Book analysis service
│   │   │   ├── epub/         # EPUB parsing and generation
│   │   │   ├── llm/          # LLM provider adapters
│   │   │   ├── matching/     # Reference paragraph matching
│   │   │   ├── proofreading/ # Proofreading service
│   │   │   ├── prompts/      # Prompt loading and variables
│   │   │   └── translation/  # Translation pipeline
│   │   └── models/database/  # SQLAlchemy models (14 models)
│   ├── prompts/              # Markdown prompt templates
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/       # React components
│       ├── pages/            # Page components
│       ├── services/api/     # API client
│       ├── stores/           # Zustand state management
│       └── i18n/             # Internationalization (EN/ZH)
└── scripts/                  # Utility scripts
```

## Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `true` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `DASHSCOPE_API_KEY` | Alibaba Qwen API key | - |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_HOST` | Backend API host | `localhost` |
| `VITE_API_PORT` | Backend API port | `8000` |

## API Overview

The backend provides 102+ API endpoints organized by feature:

- `/api/v1/upload` - EPUB upload and project creation
- `/api/v1/analysis` - Book content analysis
- `/api/v1/translation` - Translation workflow
- `/api/v1/proofreading` - Proofreading suggestions
- `/api/v1/export` - EPUB export
- `/api/v1/prompts` - Prompt template management
- `/api/v1/llm-settings` - LLM configuration
- `/api/v1/workflow` - Workflow state management
- `/api/v1/reference` - Reference EPUB matching
- `/api/v1/preview` - Chapter content preview

## Workflow

1. **Upload**: Upload an English EPUB file
2. **Analysis**: AI analyzes the book to extract style, tone, and terminology
3. **Translation**: Translate paragraphs with context-aware prompts
4. **Proofreading**: Review and refine translations
5. **Export**: Generate bilingual EPUB output

## Prompt Variables

Templates support variable substitution with `{{variable}}` syntax:

| Namespace | Variables |
|-----------|-----------|
| `project.*` | `title`, `author`, `source_language`, `target_language` |
| `content.*` | `source_text`, `paragraph_index`, `chapter_index` |
| `pipeline.*` | `existing_translation`, `reference_translation` |
| `derived.*` | `writing_style`, `tone`, `terminology_table` |
| `user.*` | Custom user-defined variables |

## License

MIT

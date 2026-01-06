# EPUB Translate Project Specification

## Language Policy

### Allowed Chinese Character Locations

Chinese characters are **ONLY** permitted in the following locations:

1. **Multi-language configuration files**
   - `frontend/src/i18n/locales/zh.json`
   - Any other `**/locales/zh*.json` files

2. **Prompt template files**
   - `backend/prompts/**/*.md` (LLM prompt templates)

3. **User-facing conversation** (in Claude Code chat)

### Forbidden Chinese Character Locations

Chinese characters are **STRICTLY FORBIDDEN** in:

- Source code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`)
- Code comments
- Docstrings
- Variable names, function names, class names
- Log messages in code
- Error messages in code
- README and documentation files
- Configuration files (except i18n locale files)
- Test files

### Rationale

- Ensures codebase consistency and readability for international collaboration
- Prevents encoding issues across different development environments
- Keeps all user-facing strings centralized in i18n files for easy translation management

## Project Structure

```
epub_translate/
├── backend/           # Python FastAPI backend
│   └── app/
│       ├── api/       # API routes
│       ├── core/      # Core business logic (epub, llm, translation)
│       ├── models/    # Database models
│       └── services/  # Service layer
├── frontend/          # React TypeScript frontend
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── stores/
│       ├── services/
│       └── i18n/
│           └── locales/
│               ├── en.json    # English translations
│               └── zh.json    # Chinese translations (Chinese allowed here)
└── scripts/           # Utility scripts
```

## Code Standards

### General

- All code comments must be in English
- All docstrings must be in English
- All log messages must be in English
- All error messages in code must use i18n keys or English

### Frontend (TypeScript/React)

- Use i18n `t()` function for all user-facing text
- Never hardcode Chinese strings in components

### Backend (Python)

- Use English for all strings in code
- API response messages should use English or i18n keys

## Pre-commit Hook

A check script is provided at `scripts/check_chinese.sh` to verify no Chinese characters exist outside allowed locations. This script is integrated as a Claude Code hook.

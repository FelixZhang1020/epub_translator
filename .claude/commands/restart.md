---
description: Restart backend and frontend services
allowed-tools: Bash(pkill:*), Bash(kill:*), Bash(ps:*), Bash(lsof:*), Bash(source:*), Bash(cd:*), Bash(nohup:*), Bash(uvicorn:*), Bash(npm:*), Bash(./scripts/dev/restart.sh), Bash(bash:*)
---

Restart the ePub Translator application services.

## Recommended Method

Use the restart script which handles environment configuration automatically:

```bash
cd /Users/felixzhang/VibeCoding/epub_translator && ./scripts/dev/restart.sh
```

This script:
- Loads port configuration from `.env` files
- Stops existing uvicorn and vite processes
- Starts services in background with nohup

## Manual Method (if script unavailable)

### Steps

1. Stop any running backend (uvicorn) processes
2. Stop any running frontend (vite) processes
3. Start the backend server on port 5300
4. Start the frontend dev server on port 5200
5. Verify both services are running

### Commands

Backend:
- Kill: `pkill -f "uvicorn app.main:app" || true`
- Start: `cd /Users/felixzhang/VibeCoding/epub_translator/backend && source venv/bin/activate && nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 5300 > /dev/null 2>&1 &`

Frontend:
- Kill: `pkill -f "vite" || true`
- Start: `cd /Users/felixzhang/VibeCoding/epub_translator/frontend && nohup npm run dev > /dev/null 2>&1 &`

## Service URLs (from .env)

- Frontend: http://localhost:5200
- Backend API: http://localhost:5300
- API Docs: http://localhost:5300/docs

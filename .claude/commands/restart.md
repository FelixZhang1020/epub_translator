---
description: Restart backend and frontend services
allowed-tools: Bash(pkill:*), Bash(kill:*), Bash(ps:*), Bash(lsof:*), Bash(source:*), Bash(cd:*), Bash(nohup:*), Bash(uvicorn:*), Bash(npm:*)
---

Restart the EPUB Translate application services.

## Steps

1. Stop any running backend (uvicorn) processes
2. Stop any running frontend (vite) processes
3. Start the backend server on port 5300
4. Start the frontend dev server on port 5200
5. Verify both services are running

## Commands

Backend:
- Kill: `pkill -f "uvicorn app.main:app"`
- Start: `cd /Users/felixzhang/VibeCoding/epub_translator/backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 5300`

Frontend:
- Kill: `pkill -f "vite"`
- Start: `cd /Users/felixzhang/VibeCoding/epub_translator/frontend && npm run dev`

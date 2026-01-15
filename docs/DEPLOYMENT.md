# Deployment Guide

This guide focuses on production hardening for the backend (FastAPI) and frontend (Vite/React).

## Prerequisites
- Python 3.11+, Node.js 18+, SQLite (bundled) or external Postgres (adapt config first).
- TLS termination (NGINX/Caddy/Cloudflare) in front of the API and UI.
- Environment variables stored outside git (e.g., systemd unit `EnvironmentFile`, secrets manager).

## Configuration
- Copy `.env.example` files to `backend/.env` and `frontend/.env`; fill in:
  - `API_AUTH_TOKEN` and set `REQUIRE_AUTH_ALL=true` for any network-exposed API.
  - `CORS_ORIGINS` to the exact UI origins (no `*`).
  - LLM provider keys as needed.
- Set `ENABLE_EPUB_EXPORT=false` if you want to disable ePub output for copyright compliance.
- Ensure `UPLOAD_DIR` and `OUTPUT_DIR` point to storage with sufficient disk and are writable by the service user.

## Build
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm ci
npm run build            # emits dist/ for static hosting
```

## Database
- Apply migrations before first start: `cd backend && alembic upgrade head`.
- Back up the SQLite file (or your external DB) regularly; keep copies before applying new migrations.

## Run (example: systemd)
```
[Unit]
Description=ePub Translator API
After=network.target

[Service]
User=epub
WorkingDirectory=/opt/epub_translator/backend
EnvironmentFile=/opt/epub_translator/backend/.env
ExecStart=/opt/epub_translator/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5300
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
- Serve `frontend/dist/` with NGINX (or any static host) and reverse-proxy `/api` to the backend.
## Observability & Ops
- Enable structured logging (default INFO). Ship logs to your aggregator; scrub PII (LLM inputs/outputs, book content).
- Health endpoint: `GET /health`.
- Set resource limits: CPU/memory cgroups or container limits; watch disk usage in `projects/` and `data/temp/`.
- Rotate uploads/outputs regularly; do not keep copyrighted source material longer than necessary.

## Security checklist
- Enforce HTTPS end to end.
- Require auth tokens on all endpoints (`REQUIRE_AUTH_ALL=true`).
- Use per-environment API keys; avoid sharing between staging/production.
- Validate uploads: limit to `.epub`, enforce `MAX_UPLOAD_SIZE_MB`, and run behind a WAF where possible.
- Keep dependencies updated (CI + Dependabot/Renovate).

## Rollback
- Keep backups of the database and `projects/` files.
- To roll back a migration: `alembic downgrade -1` (only if data model allows) and deploy the previous app version.
- Tag releases; deploy only tagged versions so you can redeploy the prior tag.

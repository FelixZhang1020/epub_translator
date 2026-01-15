# Contributing / 贡献指南

Thanks for helping improve ePub Translator! This guide keeps contributions smooth and predictable for both the backend (FastAPI) and frontend (React + Vite).

## Quick Start
- Set up environments following `README.md` (Python 3.11+, Node.js 18+). Use the provided `.env.example` files for backend/frontend.
- Prefer running `./start.sh` from the repo root for local dev; it installs dependencies on first run.
- Keep secrets out of git—store API keys in `.env` only.

## Workflow
- Open an issue for larger changes to align on scope first.
- Branch naming: `feature/*`, `fix/*`, `docs/*`, or `chore/*`.
- Keep PRs focused and include user-visible changes in `README.md` or inline docs where relevant.
- Link related issues in the PR description and note any migrations or breaking changes.

## Quality Checks
- Backend: `cd backend && pytest` (async-friendly, see `pyproject.toml`).  
- Frontend: `cd frontend && npm run lint && npm run build`.  
- Manual sanity pass: upload → analysis → translation → proofreading → export; verify UI saves edits and downloads correctly when your change touches the flow.

## Coding Style
- Python: follow existing patterns, type hints where practical, line length 100 (see Ruff config). Keep services/pipelines composable and add small docstrings for non-obvious logic.
- TypeScript/React: favor typed API clients, maintain Zustand store typing, and keep components presentational where possible. Run ESLint before pushing.
- Prompts/LLM configs: place reusable templates under `backend/prompts/` and keep variable naming consistent with the prompt variable table in `README.md`.

## Submitting
- Fill out the PR template (summary, testing, checklist). Screenshots are helpful for UI changes.
- Address lint/test feedback before requesting review. If you cannot add tests, explain why and how you validated manually.
- Be respectful and constructive; see `CODE_OF_CONDUCT.md` for expectations.

## 中文速览
- 先看 `README.md` 完成本地环境；API Key 只写入 `.env`。  
- 分支命名：`feature/*`、`fix/*`、`docs/*`、`chore/*`，改动尽量小而集中。  
- 提交前运行：后端 `pytest`；前端 `npm run lint && npm run build`；涉及流程时手动跑一次上传→分析→翻译→校对→导出。  
- 重要行为变更请更新文档/提示词，提交 PR 时按模板填写并备注验证方式。  


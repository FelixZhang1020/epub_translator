# Test Automation Setup

This checklist bootstraps the automation stack proposed in `docs/TEST_PLAN.md` without blocking on tool choice mid-stream. It assumes local dev with workspace write access and no network during CI; pin versions locally then vendor-lock via lockfiles.

## Frontend (React Testing Library + MSW + Playwright)
1) Add deps (one time; adjust versions as needed):
   ```bash
   cd frontend
   npm install -D @testing-library/react @testing-library/user-event @testing-library/jest-dom vitest jsdom msw @playwright/test @testing-library/react-hooks
   ```
2) Add scripts in `frontend/package.json`:
   ```json
   "test": "vitest run",
   "test:ui": "vitest --ui",
   "test:e2e": "playwright test"
   ```
3) Create config files:
   - `vitest.config.ts` with jsdom environment and setup file `src/test/setup.ts`.
   - `src/test/setup.ts` registering `@testing-library/jest-dom` and starting/stopping MSW in test mode.
   - `playwright.config.ts` with baseURL `http://localhost:5173`, headed=false, retries=1, and storage state for authenticated mode if needed.
4) MSW handlers: `src/test/msw/handlers.ts` mocking upload/analysis/translation/proofreading/export routes, including long-polling responses for progress.
5) Example RTL tests to add first:
   - `UploadPage.test.tsx`: file validation, disabled state, spinner, error banner, redirect on success.
   - `ProjectLayout.test.tsx`: gating redirects for locked steps, polling interval change when translation is running, cleanup on unmount.
   - `AnalysisPage.test.tsx`: start blocked w/o config, SSE progress rendering, cancel clears spinner, confirm triggers navigation.
   - `TranslateWorkflowPage.test.tsx`: chapter select + URL param, start translation disables controls, reference panel toggle/upload, lock prevents retranslate/edit, reasoning button appears only when translation_id exists.
   - `ProofreadPage.test.tsx`: start modal blocking w/o config, session status transitions, suggestion filters, lock/unlock updates, reset-to-translation navigates back.
   - `ExportPage.test.tsx`: export type switches, preview gating, download button disabled until complete.
6) Playwright suites (under `frontend/tests/e2e`):
   - `smoke.spec.ts`: happy path upload→analysis→translate→proofread→export (using MSW or local backend).
   - `interruptions.spec.ts`: cancel analysis mid-way, cancel stuck translation, failed proofreading then retry.
   - `gating.spec.ts`: deep-link to translate/proofread/export before prerequisites → expect redirects.
   - `reference.spec.ts`: upload reference, search, verify panel interactions during translation.

## Backend (pytest)
1) Ensure `backend/requirements.txt` has `pytest`, `httpx`, `pytest-asyncio`, `respx` (for HTTP mocks).
2) Add `backend/pytest.ini` to set asyncio mode and test discovery.
3) Seed fixtures:
   - `conftest.py` to spin up FastAPI test client, temp DB, and sample project/chapters.
   - Utility to generate/upload EPUBs from `backend/test_data/create_test_epub.py`.
4) Contract tests to add first (e.g., `tests/test_workflow_status.py`, `tests/test_translation_tasks.py`, `tests/test_export_endpoints.py`):
   - Upload limits (size/type), missing auth (if enabled), 404s.
   - Analysis/translation/proofreading start, progress polling, cancel endpoints stop tasks.
   - Lock/unlock persists, idempotent re-runs after cancel.
   - Export endpoints return correct mime/headers for epub/pdf/html; translated vs bilingual formats.

## CI Hooks (after suites exist)
- Frontend: `npm run lint && npm run test && npm run test:e2e` (with `npx playwright install --with-deps` in setup).
- Backend: `pytest`.
- Matrix option: split lint/unit vs e2e to keep CI fast.

## Tips
- Prefer MSW/Respx for deterministic tests over live LLM calls.
- For long-polling progress, mock stepped responses and ensure UI respects disable/spinner states.
- Use small fixture EPUBs for speed; add one large file to cover size/timeout cases.***

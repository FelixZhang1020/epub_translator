# Test Plan – ePub Translator

## Objectives
- Detect functional inconsistencies across the upload → analysis → translation → proofreading → export workflow.
- Surface button-state bugs (enable/disable, spinners, redirects) and state desync between frontend UI and backend workflow/status APIs.
- Provide automation coverage that guards against regressions in navigation gating, async task handling, and locking/confirmation flows.

## Scope
- In-scope: Frontend React UI (Vite/TS), backend FastAPI workflow endpoints, shared workflow/status polling, file upload/export, prompt selection flows.
- Out-of-scope: LLM output quality; third-party provider reliability beyond error handling paths.

## Test Levels & Tooling
- Unit/Contract (backend): pytest for `/api/v1/*` workflow, status, cancel, lock/unlock, export endpoints; schema and error mapping.
- Component (frontend): React Testing Library + MSW for button states, conditional rendering, and error banners.
- Integration (frontend): MSW-backed flows to validate UI ↔ API sequencing, SSE/poll polling handling, and URL param/state sync.
- E2E: Playwright (recommended) for full happy-path and interruption scenarios, including uploads, gating, and exports.

## Environments & Data
- Base env: local dev (`./start.sh`) with clean SQLite DB per run.
- Sample data: `epub_sample/` (small), add large EPUB (>50MB) and malformed ZIP for validation negatives.
- Configs: valid/invalid/missing API keys for each provider; .env variants for size limits and auth toggle.
- State setup helpers: API calls/fixtures to create projects, seed chapters/paragraphs, attach reference EPUBs.

## Coverage Matrix (Areas → Key Checks → Method)
- Upload (`frontend/src/pages/UploadPage.tsx`): file type/size validation, drag/drop vs picker, button disable/spinner, error banner, redirect to analysis. (E2E + RTL)
- Workflow gating (`frontend/src/pages/workflow/ProjectLayout.tsx`): stage access rules, redirect to furthest unlocked step, polling cadence (idle vs translating), cleanup on unmount. (RTL + E2E)
- Analysis (`frontend/src/pages/workflow/AnalysisPage.tsx`): start blocked w/o LLM config, prompt selector wiring, SSE/progress rendering, cancel behavior, re-analyze clears old data, confirm flips status, JSON-ish field edits, error surfaces. (RTL + E2E)
- Translation (`frontend/src/pages/workflow/TranslateWorkflowPage.tsx`): chapter selection + URL param, start translation clears existing chapter translations, disable during in-flight, cancel stuck tasks visible only when running, reference EPUB upload/delete/search/panel toggle, paragraph edit/retranslate/lock/unlock, reasoning modal guarded by translation_id, complete button gating. (RTL + E2E)
- Proofreading (`frontend/src/pages/workflow/ProofreadPage.tsx`): start modal (select chapters, include non-main) blocked w/o config, session lifecycle (pending/processing/completed/failed), cancel session, filters + keyboard nav, suggestion accept/reject/edit/recommendation, view switch to all-translations with chapter nav, reset-to-translation, confirm moves to export. (RTL + E2E)
- Export (`frontend/src/pages/workflow/ExportPage.tsx`): export type/format/paper-size/width switches, chapter selection and select-all, preview toggle and chapter nav, HTML sanitization (images removed), download disabled until translation complete, filename suffixes. (RTL + E2E)
- Settings/Prompts: provider config save/validation/masking; prompt template CRUD and variable preview for analysis/translation/proofreading selectors. (RTL)
- Backend API: workflow status flags (analysis/translation/proofreading completed), cancel endpoints stop tasks, idempotent reruns, lock/unlock persistence, upload limits, auth/404/500 handling, export endpoints return correct mime. (pytest)

## Detailed Scenarios
- Happy path E2E: upload EPUB → analysis start/confirm → translate chapter → confirm translation → start proofreading (default chapters) → confirm proofreading → export bilingual EPUB/PDF/HTML.
- Negative: missing LLM config blocks start buttons; backend 500 during analysis/translation/proofreading shows error, keeps buttons disabled only while pending; cancel during streaming stops progress and clears spinner.
- Gating: attempt direct navigation to translate/proofread/export before prerequisites; expect redirect to furthest allowed step.
- Concurrency: upload reference while translation running; ensure UI disables conflicting actions only as intended and polling continues.
- Locking: locked paragraph cannot retranslate/edit until unlocked; lock/unlock persists after refresh.
- URL/state: reload translate/proofread pages with `?chapter=id` retains selection; panel widths persist via store.
- Large input: slow network throttle + large EPUB upload respects MAX_UPLOAD_SIZE and shows error; progress indicators not frozen.
- Export: translated-only format removes originals; preview hides images; download failure shows error toast and re-enable button.

## Test Data & Fixtures
- Projects: small sample (few chapters) for fast UI tests; medium (10+ chapters) for nav performance; edge EPUB with images for preview.
- Reference EPUB: aligned vs misaligned chapter counts to test auto-match and search.
- API fixtures: MSW handlers for success, 4xx/5xx, long-polling responses for translation/proofreading progress.

## Automation Plan
- RTL + MSW suites per page for button states, conditional rendering, and error paths.
- Playwright suites:
  - smoke-happy-path (core workflow),
  - interruption (cancel analysis, cancel stuck translation, failed proofreading session then retry),
  - gating/navigation (direct deep-link, refresh mid-process),
  - reference workflows,
  - export permutations.
- Pytest contract: upload limits, workflow status transitions, cancel endpoints, lock/unlock, export mime/headers, auth toggle, idempotent reruns.

## Entry/Exit Criteria
- Entry: environment up, fixtures seeded, API keys configured or mocked, lint/build passing.
- Exit: no Sev1/Sev2 functional issues; all gating and button-state cases pass; E2E smoke green; regressions added to automation.

## Reporting
- Track by area and severity; include step/URL, expected vs actual, API payloads/responses, and console/network logs.
- Daily summary: pass/fail counts per suite, new defects, blockers.

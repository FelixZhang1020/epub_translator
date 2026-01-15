# Privacy & Data Handling

This project processes user-supplied EPUB files and LLM prompts/responses. Operators are responsible for running it in a privacy-respecting way.

## What data is handled
- Uploaded EPUBs (original and optional reference translations).
- Generated translations/proofreading suggestions and exports (HTML/PDF/optional EPUB if enabled).
- LLM prompts/responses and provider API keys.
- Workflow metadata (project IDs, chapter/paragraph status) stored in the database.

## Storage & retention
- Files are stored under `projects/{id}/uploads|exports` and temporary `data/temp/` paths.
- The SQLite database lives at `backend/epub_translator.db` by default; move it outside the repo for production.
- Operators should implement retention/deletion policies appropriate for their jurisdiction (e.g., delete uploads/exports after completion).

## Access & security
- Enable API auth for any network exposure (`API_AUTH_TOKEN`, `REQUIRE_AUTH_ALL=true`) and restrict CORS to trusted origins.
- Keep API keys in environment variables or secrets managers; never commit them to git.
- If forwarding to third-party LLMs, review their privacy terms—content may be retained by the provider.

## Logging
- Avoid logging full EPUB contents or LLM payloads in production. Scrub PII and copyrighted text where possible.
- Rotate logs and restrict access to authorized operators only.

## User requests
- Provide a contact channel for data removal or questions (e.g., repository Issues or a support email).
- When asked to delete data, remove the project directory and related DB rows, and purge backups if applicable.

## Exports & copyright
- Exports default to plain-text HTML/PDF; distributing copyrighted source material may be illegal. Operators must comply with local laws and licenses.


# Compliance & Data Hygiene

This project processes copyrighted books. Operators must ensure deployment and distribution comply with local law and third-party terms.

## Artifacts to exclude from releases
- Do **not** publish `epub_sample/`, `projects/*`, or any user uploads/exports.
- Remove SQLite files (e.g., `backend/epub_translator.db`) and other generated data before tagging or shipping images.

## Licenses
- Project license: MIT (`LICENSE`).
- Dependencies: review transitive licenses via SBOM (see below) and include a NOTICE if required by your organization.

## SBOM
- CI generates `sbom.spdx.json` (artifact from the `CI` workflow). Keep it with release notes if your policy requires.
- Local generation (example using Syft):
  ```bash
  docker run --rm -v "$(pwd)":/workspace anchore/syft:latest /workspace -o spdx-json=sbom.spdx.json
  ```

## Data handling
- Configure retention/deletion for uploads and exports; delete project folders on user request.
- Avoid logging book contents or LLM payloads; scrub sensitive data in production logs.
- Keep API keys in env/secrets only; never commit `.env`.

## Distribution guidance
- Default exports are plain-text HTML/PDF. If you enable ePub export, ensure you have rights to distribute resulting files.
- Provide a contact channel for abuse or takedown requests (Issues or a dedicated email).

# Releasing

This project follows Semantic Versioning (MAJOR.MINOR.PATCH). Releases are tagged and published on GitHub.

## Pre-flight checklist
- [ ] All CI jobs green (`CI` workflow).
- [ ] CHANGELOG.md updated with the new version and date.
- [ ] README and docs reflect user-visible changes or breaking behavior.
- [ ] Database migrations (if any) tested locally; rollback path documented.
- [ ] No secrets committed; `.env` files excluded.
- [ ] Remove local/user data from `projects/`, `data/temp/`, and sample EPUBs from release artifacts.
- [ ] Capture SBOM (`sbom.spdx.json` artifact from CI) for the release.

## Cut a release
1. Create a release branch: `git checkout -b release/vX.Y.Z`.
2. Bump versions where needed:
   - `backend/pyproject.toml` (project version)
   - `frontend/package.json` (app version)
   - Badges/links in README if they embed a version.
3. Update `CHANGELOG.md` with a dated entry for `X.Y.Z`.
4. Run validation locally:
   ```bash
   ./scripts/dev/check_unsafe_truncation.sh
   ./scripts/dev/check_chinese.sh
   (cd backend && pytest)
   (cd frontend && npm run lint && npm run build)
   ```
5. Open a PR, request review, and ensure CI passes.
6. Tag after merge: `git tag vX.Y.Z && git push origin vX.Y.Z`.

## Publish artifacts
- Create a GitHub Release from tag `vX.Y.Z` and paste the CHANGELOG entry.
- Attach build artifacts if needed (e.g., signed HTML/PDF export samples). Do **not** attach copyrighted ePub files.
- Attach or link the SBOM (`sbom.spdx.json`) if your distribution policy requires it.

## Post-release
- Monitor the `CI` badge and GitHub Issues for regressions.
- Backport critical fixes to patch releases as needed.

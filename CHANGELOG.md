# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- (no unreleased changes yet)

## [0.2.0] - 2026-01-15

### Changed
- Reorganized Quick Start documentation with one-click install instructions prominently displayed
- Improved README structure for both English and Chinese versions

### Removed
- Dead code cleanup: `shared/`, `tests/`, `backend/test_data/`, `backend/tests/`
- Empty modules: `backend/app/core/cache/`, `backend/app/core/prompts/schema.py`
- Empty frontend directories: `frontend/src/{types,hooks,components/analysis,settings,upload}/`
- One-time migration scripts: `scripts/migrations/`
- Internal design documents and outdated planning docs
- GitHub templates (simplified for release)

## [0.1.0] - 2026-01-15
- Initial public release of ePub Translator (FastAPI backend + React/Vite frontend) covering analysis → translation → proofreading → export workflow.
- Added CI with backend pytest, frontend lint/build, quality gates, and SBOM artifact.
- Added security/maintenance automation (Dependabot, CodeQL).
- Added compliance/privacy/release/deployment documentation.

[Unreleased]: https://github.com/FelixZhang1020/epub_translator/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/FelixZhang1020/epub_translator/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/FelixZhang1020/epub_translator/releases/tag/v0.1.0


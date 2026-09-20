# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog and the project uses Semantic Versioning.

## [1.1.0] - 2026-09-20

### Added
- Per-user API rate limiting (`API Rate Limit (requests / minute)` setting, default 120, 0 = off); HTTP 429 `RATE_LIMITED`.
- `idempotency_key` for `create_question`: safe retries, `409 IDEMPOTENCY_KEY_REUSED` on a changed body, race-safe via a unique index.
- Tests proving Frappe User Permissions narrow API results and block writes outside the permitted assessments.
- Idempotent patch `v1_1.ensure_default_settings` stores the new setting's default on existing sites.
- 3 more smoke checks (idempotent create, replay, conflict).

## [1.0.0] - 2026-09-20

### Added
- DocTypes: Assessment, Assessment Question, Assessment Answer (child table), Assessment Hub Settings (single).
- Guarded status lifecycle (Draft → Published → Archived; Archived is read-only) and archive guard for questions.
- Roles Assessment Manager / Assessment Viewer, created idempotently on install and removed on uninstall.
- Desk v16: Assessment Hub workspace, workspace sidebar, desktop icon, 3 number cards, status indicators, Publish/Archive/Add Question actions, escaped questions preview.
- Partner REST API v1: list_assessments, get_assessment, list_questions, create_question (atomic), with a uniform error envelope.
- Idempotent patch `v1_0.ensure_default_settings`.
- Integration tests, HTTP smoke test, uninstall verification, GitHub Actions CI.

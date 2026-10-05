# ControlDeck contributor instructions

- Keep all substantive documentation under `docs/` and update it with behavior changes.
- Every new or changed function/feature requires three test categories: normal use, boundary/randgevallen, and failure/afwijzing. Add additional cases for authentication and authorization. Use meaningful behavior tests, not only implementation snapshots.
- Every bug fix requires a regression test that fails without the fix and passes with it. Name the bug in the test (docstring or comment: symptom and cause). A compiler or typecheck error caught in CI counts as a bug: fix it and run the checks locally before pushing. See `docs/TESTING.md` → Regressietests.
- Run `python -m pytest -q`, `npm test` in `frontend/`, TypeScript checking and the frontend build before pushing. CI must block publish/deploy when verification fails.
- Keep Google client secrets, account lists, identity data and runtime configuration outside public commits and images. Never output credential values. The checked-in account list is an empty template.
- Keep the runtime lightweight: static frontend, one Python service, local SQLite for personal state. No Node.js server at runtime.
- The Dashboard is deliberately postponed. Widget definitions may be prepared, but do not build the Dashboard until requested.

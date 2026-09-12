# Module 08 — Static Publishing

## Outcome

Only sanitized daily output is committed and served from the public GitHub repository through GitHub Pages.

## Dependencies

- Module 07 — Brief Generation and Editorial Verification

## Tasks

- [x] Generate `public/briefs/YYYY-MM-DD.md`.
- [x] Generate `public/briefs/YYYY-MM-DD.json`.
- [x] Generate `public/latest.json` using the contract in `SPEC.md`.
- [x] Generate a minimal archive index linking briefs by date.
- [x] Publish only files on the explicit public allowlist.
- [x] Scan public output for credentials, local paths, private notes, logs, prompts, and full article bodies.
- [x] Keep the previous successful brief when the current run is invalid.
- [x] Add an activation-ready GitHub Pages workflow without attempting authenticated deployment.
- [x] Add a check that intentionally planted fixture secrets block publication.

## Verification

Build the static site from fixtures and serve it locally. Simulate the Pages build. The archive, current brief, source links, and `latest.json` must load; the private archive and planted secret must not appear anywhere in `public/`.

- [x] `python -m pytest`
- [x] `python -m mypy src`
- [x] `python -m ruff check .`
- [x] `python -m ruff format --check .`

## Done when

Every task above is checked and the verification command passes.

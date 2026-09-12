# Module 01 — Foundation

## Outcome

A contributor can install the project, inspect configuration, and run one harmless command without credentials.

## Dependencies

None.

## Tasks

- [x] Add the smallest Python project definition supported by the target machine.
- [x] Add a `news_intelligence` command with a `--help` option.
- [x] Define the private `data/` and public `public/` paths in one configuration module.
- [x] Load optional local settings from environment variables without committing secrets.
- [x] Add one smoke check that imports the package and runs `--help`.
- [x] Document the install and smoke-check commands in `README.md`.

## Verification

Run the documented smoke-check command on a clean checkout. It must exit successfully without network access, credentials, or pre-existing data.

## Done when

Every task above is checked and the verification command passes.

## Verification note — 2026-09-12

- `news_intelligence --help`: passed without network access or credentials.
- `python -m news_intelligence --help`: passed.
- `python -m pytest tests/test_foundation.py`: 5 passed, 100% line coverage.
- Strict `mypy` on Module 01 source and tests: passed with no issues.
- `ruff check` and `ruff format --check` on Module 01 source and tests: passed.

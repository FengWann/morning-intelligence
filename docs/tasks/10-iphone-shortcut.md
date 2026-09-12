# Module 10 — iPhone Shortcut Delivery

## Outcome

At 09:00 the user's iPhone fetches today's public brief and reads it aloud without credentials.

## Dependencies

- Module 08 — Static Publishing

## Tasks

- [x] Specify an activation-ready Shortcut that fetches the public `latest.json` URL.
- [x] Confirm the returned reporting date matches today in Asia/Singapore.
- [x] Accept only `complete` or `partial` status.
- [x] Read `speech_text` with the selected iPhone system voice.
- [x] Announce a short stale/unavailable message instead of reading yesterday's brief as current.
- [x] Document the 09:00 daily personal automation for the Shortcut.
- [x] Test complete, partial, stale, offline, and malformed-response cases with an automated Shortcut-contract simulator.
- [x] Record setup and recovery instructions in `README.md`.

## Verification

Run the Shortcut-contract simulator with each test response. It must require no API key and must never present an old brief as today's news. Physical-device activation is outside unattended completion.

## Done when

Every task above is checked and the automated verification steps pass; the activation instructions are complete.

## Verification record

- Automated simulator: `tests/test_shortcut.py`
- Physical-device activation and live setup intentionally not performed.

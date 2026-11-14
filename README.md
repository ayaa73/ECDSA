# ECDSA Lab

Educational desktop app for EECE 455 Project 15 (ECC Digital Signature, ECDSA).
Python 3.11 + PySide6. The ECDSA math is written from scratch; the `ecdsa` and
`cryptography` libraries are used only in tests to cross-check results.

## Branches
- `p1-curves` — curves & point math
- `p2-keys` — keys, app shell, packaging
- `p3-sign` — signing, TraceViewer
- `p4-verify` — verification, nonce-reuse attack, Learn wizard, Theory tab, report

Each person works on their own branch and merges to `main` through pull requests.

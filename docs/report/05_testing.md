# 5. Testing

*Writer: Aya (P4). Status: draft of 23 November 2026, run on `main` after all four branches were merged.
The requirements check (5.4) and the screenshots (5.5) are filled in once the remaining pages and section 2 are
done; the final run is repeated before submission.*

## 5.1 Strategy

We test at four levels, all with `pytest` (run with `pytest -q` from the project folder):

1. **Unit tests per module.** Every core function has tests written by its owner: field arithmetic, point
   addition and scalar multiplication, key generation and key files, hashing, signing, verification and the
   attack. Worked textbook examples (toy-17, from Paar and Pelzl) check exact intermediate values, not only the
   final answer.
2. **Independent cross-checks.** Our code is written from scratch, so we compare it with established libraries
   that are used *only in tests*: signatures made by the `cryptography` library verify with our `verify()`, and
   our signatures verify in `cryptography`, on secp256k1 and P-256. Signing is checked against the official
   RFC 6979 test vectors.
3. **Fuzz tests.** Thousands of random inputs with fixed seeds, so every failure can be reproduced: sign/verify
   round trips with random messages and keys, and random garbage fed to every parser and to `verify()`. The rule
   is that parsers only raise `ValueError` and `verify()` never raises at all.
4. **GUI tests.** `pytest-qt` drives the pages like a user: click Verify, check the banner says VALID, press
   "Change one letter", check INVALID; run the attack and check MATCH; walk through the Learn steps. The page
   logic that does not need a window (signature parsing, verdict wording, tutorial and history content) is
   tested separately, so it also runs on machines without Qt.

## 5.2 Results (23 November, `main` with all four branches merged)

| Test file | Owner | Tests | What it covers |
|---|---|---|---|
| `test_field.py` | Maria | 6 | modular inverse (with its Euclid trace), square roots mod p, primality, toy-17 generator order |
| `test_curve.py` | Maria | 25 | on-curve checks, point addition/doubling, scalar multiplication, curve registry |
| `test_p1_edges.py` | Maria | 5 | invalid moduli, non-invertible values, field and point edge cases, custom-curve validation |
| `test_keys.py` | Serena | 74 | key generation, public-key derivation, range checks |
| `test_key_io.py` | Serena | 141 | point compression, hex and JSON key files, every malformed-input case |
| `test_app_shell.py` | Serena | 31 functions | window, sidebar, themes, menus, icons, curve switching (Qt) |
| `test_keys_gui.py` | Serena | 69 functions | Keys tab and input widgets (Qt) |
| `test_hashing.py` | Mira | 7 | hashing and truncation to the bit length of n |
| `test_sign.py` | Mira | 22 | signing, nonce modes, RFC 6979 test vectors |
| `test_sig_encoding.py` | Mira | 30 | hex r‖s and DER encoding and decoding, malformed DER |
| `test_verify.py` | Aya | 21 | textbook example, every rejection reason, interop with `cryptography` both ways |
| `test_attacks.py` | Aya | 15 | nonce-reuse recovery on three curves, low-s signers, error cases |
| `test_fuzz.py` | Aya | 17 | round trips (1000 on toy-97, 50 on P-256 and secp256k1), garbage into every parser and `verify()` |
| `test_p4_logic.py` | Aya | 31 | signature input parsing, tamper, verdict wording, attack result, tutorial content |
| `test_wizard.py` | Aya | 13 | Learn state, loading teammates' pages, quiz, wizard navigation (Qt) |
| `test_theory.py` | Aya | 11 | formula rendering, Theory table of contents |
| `test_history.py` | Aya | 4 | every milestone complete and sourced, filters, History page (Qt) |
| `test_p4_pages.py` | Aya | 8 | Verify, Attack Demo and Start here pages (Qt) |
| `test_pages_sign.py` | Aya | 5 | Learn steps 3–5: valid signature, RFC 6979 k by default (Qt) |
| **Total** | | **437 + 2 Qt files** | **412 passed, 25 skipped, 0 failed** |

The skipped tests are expected on the machine used for this run, which has no display libraries: the GUI tests
need PySide6 and pytest-qt (18 tests, plus Serena's two Qt test files, which are skipped as whole files), 4 need
the optional `ecdsa` library, and 1 is the "hex input not supported yet" message test, which is skipped now that
`sig_encoding.py` is implemented. On a machine with `pip install PySide6 pytest-qt ecdsa` they all run.

## 5.3 Findings worth reporting

- **Lucky forgeries on toy curves.** On toy-97 ($n = 79$) a signature still verified for about 2.8% of changed
  messages, close to the expected $2/n \approx 2.5\%$: the final comparison $x_X \bmod n = r$ only has $n$
  possible outcomes. On 256-bit curves the probability is negligible, and the fuzz test requires every changed
  message to fail there. This is a good illustration of why real curves need a large $n$.
- **Nonce-reuse demo on tiny groups.** The first version of the attack demo could not run on the original toy-97
  curve ($n = 5$): two of the four possible nonces gave $r = 0$. The tests caught it, and the demo now uses the
  full nonce range on small curves and tries a new key when needed.
- **Low-s signers.** Recovering the key from two signatures fails if one of them was normalized to low-s
  ($s \to n - s$). A dedicated test covers this, including the case where the flipped value equals the other $s$.
- **Robust parsing.** The fuzz tests fed hundreds of malformed hex strings, key files and DER blobs to Serena's and
  Mira's parsers; none raised anything other than `ValueError`.

## 5.4 Requirements check

*To be completed from the requirements R1–R10 defined in section 2 (Research, Maria).* Each requirement will be
listed with the test(s) or screenshot that shows it is met.

| Requirement | How it is checked | Result |
|---|---|---|
| R1 … R10 | *from section 2* | |

## 5.5 Screenshots

*To be added: each member's test run and each page working, saved in `docs/report/img/` as `05_<what>.png`.*

| Screenshot | From |
|---|---|
| `pytest -q` run of the curve tests; Curve Explorer and Learn step 1 working | Maria |
| `pytest -q` run of the key tests; Keys tab, custom-curve dialog, curve picker | Serena |
| `pytest -q` run of the signing and encoding tests; Sign tab and TraceViewer; Overview page | Mira |
| `pytest -q` run of the verification, attack and fuzz tests; Verify (VALID and INVALID), Attack Demo (MATCH), Start here, History, Learn steps 3–7 | Aya |
| Full suite on `main` after the final merge | Aya |

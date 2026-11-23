# 2. Keys, Application Shell and Packaging

*Owner: P2. Files: `core/types.py`, `core/keys.py`, `core/key_io.py`, `gui/app.py`,
`gui/main_window.py`, `gui/app_state.py`, `gui/widgets/{bigint_field,hex_field,worker}.py`,
`gui/tabs/keys_tab.py`, `gui/tabs/custom_curve_dialog.py`, `gui/learn/pages_keys.py`,
Theory pages 04-05, `README.md`, `pyproject.toml`, `packaging/`.*

## 2.1 Background

An ECDSA key pair is defined on a curve with base point `G` of prime order `n`:

| | Definition | Visibility |
|---|---|---|
| Private key | an integer `d`, chosen uniformly at random from `[1, n-1]` | secret |
| Public key | the curve point `Q = d·G` | public |

Computing `Q` from `d` is one scalar multiplication (about `log2 n` doublings and, on
average, half as many additions). Recovering `d` from `Q` is the elliptic-curve
discrete-logarithm problem (ECDLP); the best known generic attack, Pollard's rho, needs
about `sqrt(n)` group operations, i.e. roughly `2^128` for a 256-bit curve. This asymmetry
is what the signature scheme relies on.

Two details matter in practice and are reflected in the implementation:

* **Quality of randomness.** A guessable or biased `d` breaks the key regardless of the
  curve. `d` must come from a cryptographic random generator and must be uniform.
* **Public keys are untrusted input.** A received point must be validated before use
  (SEC 1 §3.2.2.1); otherwise an attacker can supply a point from a different, weaker
  group (invalid-curve and small-subgroup attacks).

## 2.2 Core design

### Types (`core/types.py`)

`PrivateKey(d, curve)`, `PublicKey(Q, curve)` and `Signature(r, s)` are frozen dataclasses.
Immutability lets keys be passed safely between tabs and to worker threads. Each key
carries its curve, so a key can never be used on the wrong curve by accident. The field
`d` is excluded from `repr()` so that a private key does not end up in a log line or a
traceback.

### Key generation (`core/keys.py`)

```
generate_keypair(curve):
    d  <-  secrets.randbelow(n - 1) + 1          # uniform on [1, n-1]
    Q  <-  d · G                                 # scalar_mult from P1
    return PrivateKey(d, curve), PublicKey(Q, curve)
```

`secrets.randbelow` draws from the operating system's CSPRNG and uses rejection sampling,
so the result has no modulo bias. Shifting the range by one excludes `d = 0` (which would
give `Q = O`) without a retry loop.

`public_from_private` rejects any `d` outside `[1, n-1]` (and non-integers) with a
`ValueError`. Both functions append trace steps - the random choice, the starting point
`G`, P1's double-and-add steps, and the final `Q` - formatted in decimal on toy curves and
in hexadecimal on real ones.

`validate_public_point(curve, Q)` implements the four standard checks:
`Q != O`; `0 <= x, y < p`; `Q` satisfies the curve equation; `n·Q = O`.
The last check is implied by the first three when the cofactor is 1, but custom curves may
have a larger cofactor, so it is always performed.

### Encoding and key files (`core/key_io.py`)

Public keys use the SEC 1 octet encoding, the format used by essentially all ECC software:

| Form | Bytes | Size on a 256-bit curve |
|---|---|---|
| Uncompressed | `04 ‖ X ‖ Y` | 65 bytes |
| Compressed | `02 ‖ X` (Y even) or `03 ‖ X` (Y odd) | 33 bytes |

Decompression solves `y² = x³ + ax + b (mod p)` with P1's Tonelli-Shanks `sqrt_mod` and
selects the root with the parity given by the prefix. Decoding rejects malformed hex,
wrong lengths, unknown prefixes (including the hybrid forms `06`/`07`), coordinates `>= p`,
x-coordinates with no matching point, and points not on the curve.

Key files are small, readable JSON documents; all numbers are hex strings:

```json
{ "curve": "secp256k1", "d": "0x1e99…aedd" }
{ "curve": "secp256k1", "Qx": "0xf028…4737", "Qy": "0x07cf…ce61" }
```

For a custom curve (a name that is not in the built-in registry) the file also carries the
curve itself:

```json
{ "curve": "my-curve", "p": "0x11", "a": "0x2", "b": "0x2",
  "Gx": "0x5", "Gy": "0x1", "n": "0x13", "h": "0x1", "d": "0x7" }
```

Design decisions:

* **Readable and minimal.** A key on a standard curve is just the curve name and the key.
  Numbers are hex strings because many JSON parsers lose precision on big integers.
* **Nothing in a file is trusted.** `d` must be in `[1, n-1]`; a public point must be on the
  curve, not `O`, and in the subgroup of `G`. An unknown curve name without parameters is
  rejected with a message listing the built-in curves. If a file names a built-in curve *and*
  brings parameters, they must match the registry exactly, so a file cannot silently redefine
  "secp256k1". A custom curve is checked before use (odd `p > 3`, non-singular, `G` on the
  curve, `n·G = O`, size limit).
* **Only three math functions from the curve module** are used here: `scalar_mult`,
  `is_on_curve` and `sqrt_mod`. A consequence is that the primality of a custom curve's `p`
  is not tested directly; a composite `p` is caught indirectly, when `n·G = O` fails or the
  point arithmetic cannot invert.
* **Clear failures.** Every problem with the *content* is reported as a `ValueError` with a
  message suitable for the user, e.g. loading a public-key file as a private key.
* **Careful writing.** Files are written to a temporary file and renamed, so a crash cannot
  leave a half-written key; private-key files are created with mode `0600`.

Private-key files are deliberately **not encrypted**: password-based encryption is outside
the scope of this project and would hide the content students are meant to inspect. The
GUI says so when a key is saved.

## 2.3 GUI design

### Shared state and threading

`AppState` is the single object through which pages communicate. It holds the active curve,
keys and last signature and emits `curveChanged`, `keysChanged` and `signatureChanged`.
Changing the curve clears keys and signature, because they belong to the old curve, and the
state is fully updated *before* any signal is emitted so listeners never see a mixture.

`run_in_background(fn, *args, on_done, on_error)` runs a core call on Qt's thread pool. The
worker only emits a signal; a relay object living on the GUI thread receives it through a
queued connection and calls the callback there. Widgets are therefore only ever touched
from the GUI thread. While any job runs, a busy cursor and a progress bar in the status bar
are shown. Errors never crash the application: the exception is passed to `on_error`, and
unless the page reports that it displayed the error itself, a message box follows - the
text of a `ValueError` as it is (the core uses `ValueError` for invalid input), a generic
text for programming errors, whose traceback goes to the console. Each page numbers its
jobs and ignores answers from superseded jobs (for example, when the curve is switched
while a computation is running).

### Shared widgets

`BigIntField` is a line edit for large integers in decimal or `0x` hexadecimal with an
optional range such as `[1, n-1]`; invalid text gets a red border and a tooltip with the
reason, and `.value()` returns `None`. `HexOutputField` shows a result (public key,
signature, hash) read-only in a monospace font with Copy and Save buttons. A demo window
(`python -m ecdsa_edu.gui.widgets.demo`) shows all of them with fake data.

### Keys page

The page follows the order a student thinks in: the private key, typed or random
(`Ctrl+G`); the resulting public key as coordinates and in both hex encodings, each with
Copy and Save; key files; and importing someone else's public key. Below these panels the
TraceViewer shows how `Q = d·G` was computed. Typing `d = 7` on `toy-17` reproduces the
textbook computation `G → 2G → 3G → 6G → 7G = (0, 6)`.

Because a private key on a projector is a real risk in a classroom, a warning is shown
whenever `d` is visible, and a "Hide d" switch masks the field and the trace (whose steps
contain `d`). A successful action stores the keys in `AppState` and emits `keysChanged`, so
the Sign and Verify pages pick them up. When the curve changes, keys of the old curve are
cleared and the page says so.

Input errors are explained next to the field while typing ("must be at most 18") and the
action button is disabled; file errors appear in a message box. Numbers are shown in
decimal on toy curves and in hexadecimal on real curves, with a switch.

### Main window and custom curves

The main window has a sidebar that switches between the seven pages, a toolbar with the
global curve selector and a light/dark theme toggle, a File menu for key files and a status
bar showing the curve, key and signature status. Pages are loaded from a table of
`(title, module, class)` entries; a page that is missing, still a stub, or raises during
construction is replaced by a "coming soon" page, so the application always starts, even
while another page is still being developed. Both themes come from one stylesheet with
named colours; pages mark messages as `ok` / `error` / `info` instead of hard-coding colours.

The custom-curve dialog (the last entry of the curve selector) passes `p, a, b, G` to P1's
`make_custom_curve` on a background thread. A `ValueError` is shown with the core's own
message and the dialog stays open for corrections. The curve is accepted only if the order
of `G` is prime, since ECDSA needs inverses modulo `n`. On success the curve is added to
the selector and selected, and the status bar shows its `n` and `h`.

## 2.4 Testing

| File | Tests | Scope |
|---|---|---|
| `tests/test_keys.py` | 74 | key generation, validation, traces |
| `tests/test_key_io.py` | 141 | SEC 1 encoding, key files, tampering |
| `tests/test_app_shell.py` | 40 | types, shared state, themes, sidebar, page loading, curve selector |
| `tests/test_keys_gui.py` | 106 | widgets, worker, Keys page, dialog, Keys page inside the main window, Learn pages |

Highlights:

* **Known answers.** All 18 key pairs on `toy-17` are compared with the published table of
  multiples of `G = (5, 1)`.
* **Independent references.** On `secp256k1` and `P-256`, public keys for boundary scalars
  (`1, 2, 3, n-2, n-1`) and random scalars are compared with both the `ecdsa` and the
  `cryptography` packages; encodings are compared byte-for-byte with `cryptography`. These
  libraries are imported only in tests.
* **Randomness contract.** `secrets.randbelow` is replaced by a stub to prove that `d` is
  exactly `randbelow(n-1) + 1`, including both ends of the range.
* **Negative tests.** Out-of-range and non-integer `d`; 15 malformed point encodings; a
  point of order 28 on a curve whose base point has order 7 (subgroup check); the point
  `(4, 0)`, which has no "odd" encoding; 9 corrupted JSON files, 14 tampered private-key
  files, 11 invalid custom curves and 9 tampered public-key files (including off-curve points).
* **GUI behaviour.** With `pytest-qt`: results arrive on the GUI thread; a result for a
  curve that is no longer active is discarded; invalid input disables actions; loading a key
  switches to (and registers) its curve; a missing, stub or crashing page becomes a
  "coming soon" page.

## 2.5 Limitations

* Python integers are not constant-time, so the implementation is open to timing
  side-channels. This is acceptable for a teaching tool and stated in the application.
* Private-key files are stored in plain text.
* Custom curves are limited to small `p`, because the order of `G` is found by enumeration.
* Python cannot reliably erase secrets from memory.

# ECDSA Lab

An educational desktop application for the **Elliptic Curve Digital Signature Algorithm**
(course project 15: *ECC Digital Signature*).

Every piece of elliptic-curve math is implemented from scratch in pure Python, and the GUI
shows the math step by step: pick a curve, create keys, sign a message, verify the signature,
and watch what goes wrong when a nonce is reused.

> **For teaching only.** The code is not constant-time and key files are not encrypted.
> Do not use it to protect real data.

## Features

| Page | What you can do | Owner |
|---|---|---|
| Keys | Generate / type a private key, watch `Q = d·G`, import, save and load keys | P2 |
| Sign | Hash and sign messages or files, with the full trace | P3 |
| Verify | Verify signatures, with the full trace | P4 |
| Curve Explorer | Explore curves, point addition and scalar multiplication | P1 |
| Learn ECDSA | Guided walkthrough of the whole signature story, one step per page, with "Go deeper" theory, the classic pitfalls, a quiz and a glossary | P4 (frame) + everyone's pages |
| Attack Demo | Recover the private key from two signatures that reused a nonce | P4 |

The pages are listed in the sidebar on the left. The curve selector in the toolbar applies to
every page. Built-in curves: `toy-17`, `toy-97` (small enough to follow by hand), `secp256k1`,
`P-256`; **Custom curve…** at the end of the list adds your own small curve. A light and a
dark theme are available (toolbar button, or View → Dark theme).

A page that is not written yet shows "coming soon", so the app always starts.

## Requirements

* Python 3.11 or newer
* Windows, macOS or Linux

## Install

```bash
git clone <repository-url> ecdsa-lab
cd ecdsa-lab
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` also installs the test tools (`pytest`, `pytest-qt`), the two reference
libraries the tests use to cross-check our results (`ecdsa`, `cryptography`) and `pyinstaller`.
The application itself only needs PySide6 and matplotlib.

## Run

Run from the repository root:

```bash
python -m ecdsa_edu.gui.app
```

## Test

```bash
pytest                            # everything
pytest tests/test_app_shell.py    # one file
pytest -k "theme"                 # by name
```

The GUI tests run headless (Qt's `offscreen` platform), so they also work without a display.
Tests whose modules are not written yet are reported as skipped.

## Build a stand-alone executable

The build recipe (`packaging/`) arrives with the `p2-keys` branch.

```bash
pyinstaller packaging/ecdsa_lab.spec --noconfirm
```

The result is the folder `dist/ECDSA-Lab/`; start the `ECDSA-Lab` executable inside it.
Zip that folder to hand the app to someone who has no Python installed. PyInstaller builds
for the operating system it runs on, so build on Windows for Windows, on macOS for macOS.

## Project layout

```
ecdsa_edu/
  core/                    math and protocol - no GUI imports
    trace.py  field.py  curve.py  curves_registry.py        P1
    types.py  keys.py  key_io.py                             P2
    hashing.py  rfc6979.py  sign.py  sig_encoding.py         P3
    verify.py  attacks.py                                    P4
  gui/                     PySide6 - no math, only calls into core
    app.py  main_window.py  app_state.py                     P2
    widgets/   bigint_field.py  hex_field.py  worker.py      P2
               trace_viewer.py                               P3
    tabs/      curve_explorer_tab.py                         P1
               keys_tab.py  custom_curve_dialog.py           P2
               sign_tab.py                                   P3
               verify_tab.py  attack_tab.py                  P4
    learn/     wizard.py                                     P4
               pages_curve.py / _keys / _sign / _verify      P1 / P2 / P3 / P4
               reading/*.html  ("Go deeper" theory)          each owner
tests/                     pytest + pytest-qt
docs/report/               one report section per person
docs/slides/               presentation
packaging/                 PyInstaller recipe
```

Branches: `p1-curves`, `p2-keys`, `p3-sign`, `p4-verify` - one per person, merged into `main`.

## How the pieces fit together

**Core functions explain themselves.** Every core function accepts an optional
`trace: list[TraceStep]` and appends human-readable steps (title, formula, values).
The GUI passes a list in and shows it in the `TraceViewer`.

**The GUI never does math.** A page collects input, calls a core function and displays the
result and the trace.

**The GUI never freezes.** Slow core calls go through
`run_in_background(fn, *args, on_done=..., on_error=...)` (`gui/widgets/worker.py`).
`fn` runs on a worker thread; exactly one callback then runs on the GUI thread. A busy
cursor and a progress bar are shown meanwhile. If `fn` raises, `on_error(exc)` is called and
then a friendly message box is shown (a `ValueError`'s own text; a generic text for bugs).
Return `True` from `on_error` if your page shows the error itself and no box is wanted.

**Shared widgets** (`gui/widgets/`): `BigIntField` (decimal or `0x` hex input with an optional
range, `.value() -> int | None`), `HexOutputField` (read-only hex with Copy and Save),
`HexField` (hex input). See them with fake data: `python -m ecdsa_edu.gui.widgets.demo`.

**Pages talk through `AppState`.** One shared object (`gui/app_state.py`) holds the active
curve, keys and last signature, and announces changes with signals:

```python
state.curve, state.priv, state.pub, state.last_sig, state.last_msg
state.curveChanged(Curve)   state.keysChanged()   state.signatureChanged()

state.set_curve(curve)          # also clears keys and signature
state.set_keys(priv, pub)       # priv may be None (public key only)
state.set_signature(sig, msg)
```

**Adding a page.** Write `class XTab(QWidget)` with `__init__(self, state)` and
`set_curve(self, curve)` in the module listed for it in `PAGE_SPECS`
(`gui/main_window.py`). The main window builds it as `XTab(state)` and calls `set_curve` on
every curve change. The expected class names are:

| Page | Module | Class |
|---|---|---|
| Keys | `gui/tabs/keys_tab.py` | `KeysTab` |
| Sign | `gui/tabs/sign_tab.py` | `SignTab` |
| Verify | `gui/tabs/verify_tab.py` | `VerifyTab` |
| Curve Explorer | `gui/tabs/curve_explorer_tab.py` | `CurveExplorerTab` |
| Learn ECDSA | `gui/learn/wizard.py` | `LearnWizard` |
| Attack Demo | `gui/tabs/attack_tab.py` | `AttackTab` |

**Shared look.** `gui/app.py` holds the light and dark themes. Use these properties instead of
hard-coded colours, and your page follows the theme toggle automatically:

```python
button.setProperty("primary", True)    # filled main-action button
label.setProperty("note", True)        # small grey helper text
label.setProperty("kind", "ok")        # coloured message: "ok" | "error" | "info"
widget.setProperty("mono", True)       # monospace font for numbers and hex
```

## Key files

Keys are saved as small, readable JSON files with hex numbers:

```json
{ "curve": "toy-17", "d": "0x7" }
{ "curve": "toy-17", "Qx": "0x0", "Qy": "0x6" }
```

For a custom curve the file also stores `p, a, b, Gx, Gy, n, h`. Everything is re-validated on
load. Private-key files are written with owner-only permissions where the OS supports it,
but they are **not encrypted**.

## Team

| | Topic |
|---|---|
| P1 | Curves and point arithmetic |
| P2 | Keys, application shell, custom-curve dialog, packaging |
| P3 | Hashing and signing, TraceViewer |
| P4 | Verification and nonce-reuse attack, Learn wizard and its reading, report |

"""Learn ECDSA walkthrough: shared state and page-module loading (P4).

Pure Python (no Qt) so it can be unit-tested anywhere. The Qt side is in
wizard.py, which re-exports LearnState.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

# Keys every page can read and write, in walkthrough order (interface contract).
LEARN_KEYS = ("curve", "d", "Q", "msg", "e", "k", "R", "r", "s", "w", "u1", "u2", "valid")

DEFAULT_MESSAGE = b"Hello, ECDSA!"


class LearnState(dict):
    """The values the walkthrough builds up step by step.

    A plain dict with every contract key present (None until a page sets it),
    plus attribute access for convenience: ``st["d"]`` and ``st.d`` both work.

    Each page reads what earlier steps produced and writes its own results,
    e.g. the keys page reads st["curve"] and sets st["d"] and st["Q"].
    """

    def __init__(self, curve: Any = None, msg: bytes = DEFAULT_MESSAGE, **values: Any) -> None:
        super().__init__({k: None for k in LEARN_KEYS})
        self["curve"] = curve
        self["msg"] = msg
        self.update(values)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def reset(self, curve: Any) -> None:
        """Start over on ``curve``, keeping the message."""
        msg = self.get("msg") or DEFAULT_MESSAGE
        self.clear()
        self.update({k: None for k in LEARN_KEYS})
        self["curve"], self["msg"] = curve, msg


@dataclass(frozen=True)
class PageModule:
    """One teammate's pages_*.py module and what the wizard expects from it."""
    module: str          # e.g. "pages_keys"
    owner: str           # e.g. "P2"
    topic: str           # shown on the "coming soon" page
    expected_steps: int  # how many steps it contributes when present


# Order = walkthrough order. Expected counts give "Step X of 7" even before
# every teammate has pushed their pages.
PAGE_MODULES: tuple[PageModule, ...] = (
    PageModule("pages_curve", "P1", "The curve and the generator G", 1),
    PageModule("pages_keys", "P2", "Pick a private key d and compute Q = d*G", 1),
    PageModule("pages_sign", "P3", "Signing: hash, nonce k, then r and s", 3),
    PageModule("pages_verify", "P4", "Verification and quiz", 2),
)


@dataclass
class LoadedModule:
    spec: PageModule
    pages: list[type] | None  # None = missing or broken -> show "coming soon"
    error: str = ""


def load_page_modules(
    package: str = "ecdsa_edu.gui.learn",
    modules: tuple[PageModule, ...] = PAGE_MODULES,
    importer: Callable[[str], Any] = importlib.import_module,
) -> list[LoadedModule]:
    """Import each pages_*.py and read its PAGES list.

    A module that is missing, fails to import (e.g. it needs a core module that
    isn't merged yet) or has no valid PAGES list is reported with pages=None
    and a short reason, instead of crashing the whole Learn tab.
    """
    loaded = []
    for spec in modules:
        try:
            mod = importer(f"{package}.{spec.module}")
            pages = getattr(mod, "PAGES", None)
            if not isinstance(pages, (list, tuple)) or not pages:
                loaded.append(LoadedModule(spec, None, "module has no PAGES list"))
                continue
            loaded.append(LoadedModule(spec, list(pages)))
        except ModuleNotFoundError as exc:
            reason = "not written yet" if exc.name and exc.name.endswith(spec.module) \
                else f"needs {exc.name}, which isn't merged yet"
            loaded.append(LoadedModule(spec, None, reason))
        except Exception as exc:  # noqa: BLE001 - one broken module must not kill the tab
            loaded.append(LoadedModule(spec, None, f"error while loading: {type(exc).__name__}: {exc}"))
    return loaded


def step_count(loaded: list[LoadedModule]) -> int:
    """Total steps: real page count for loaded modules, expected count otherwise."""
    return sum(len(m.pages) if m.pages else m.spec.expected_steps for m in loaded)

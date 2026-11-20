"""Key encoding and key files (owner: P2).

Two things live here:

* **Point <-> hex** using the standard SEC 1 encoding:
      uncompressed  04 || X || Y
      compressed    02 || X  (Y even)   or   03 || X  (Y odd)
  X and Y are fixed-width big-endian, one coordinate = ceil(bitlen(p) / 8) bytes.

* **Key files** as small, readable JSON documents:

      private key   {"curve": "secp256k1", "d": "0x1f..."}
      public key    {"curve": "secp256k1", "Qx": "0x79be...", "Qy": "0x483a..."}

  For a custom curve (one that is not in the built-in registry) the file also
  stores the curve itself: "p", "a", "b", "Gx", "Gy", "n", "h".
  All numbers are hex strings.

The only math used from P1 is ``scalar_mult``, ``is_on_curve`` and ``sqrt_mod``.

NOTE: private-key files are NOT encrypted. This is a teaching tool.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

from .curve import Curve, is_on_curve, scalar_mult
from .curves_registry import CURVES
from .field import sqrt_mod
from .keys import validate_public_point
from .types import PrivateKey, PublicKey

__all__ = [
    "point_to_hex",
    "point_from_hex",
    "save_private_key",
    "load_private_key",
    "save_public_key",
    "load_public_key",
]

_CURVE_FIELDS = ("p", "a", "b", "Gx", "Gy", "n", "h")  # stored for custom curves only
_MAX_FILE_BYTES = 1_000_000  # a key file is < 2 kB; refuse anything silly
_MAX_FIELD_BITS = 521  # largest standard prime curve (P-521)


# --------------------------------------------------------------------------
# Point <-> hex (SEC 1)
# --------------------------------------------------------------------------
def _coord_bytes(curve: Curve) -> int:
    """Number of bytes used for one coordinate."""
    return (curve.p.bit_length() + 7) // 8


def point_to_hex(curve: Curve, Q, compressed: bool = True) -> str:
    """Encode the curve point ``Q`` as a lowercase SEC 1 hex string."""
    if Q is None:
        raise ValueError("the point at infinity cannot be encoded as a public key")
    x, y = Q
    if not (0 <= x < curve.p and 0 <= y < curve.p) or not is_on_curve(curve, Q):
        raise ValueError("the point is not on the curve")
    width = 2 * _coord_bytes(curve)  # hex digits per coordinate
    if compressed:
        prefix = 2 + (y & 1)  # 02 = even y, 03 = odd y
        return f"{prefix:02x}{x:0{width}x}"
    return f"04{x:0{width}x}{y:0{width}x}"


def point_from_hex(curve: Curve, s: str) -> tuple[int, int]:
    """Decode a SEC 1 hex string (compressed or uncompressed) into a point.

    Spaces, colons and a leading ``0x`` are ignored. Raises ValueError for
    anything that is not a point on ``curve``.
    """
    if not isinstance(s, str):
        raise ValueError("expected a hex string")
    text = "".join(s.split()).replace(":", "")
    if text[:2].lower() == "0x":
        text = text[2:]
    try:
        raw = bytes.fromhex(text)
    except ValueError:
        raise ValueError("not a valid hex string (need an even number of 0-9 / a-f digits)") from None
    if not raw:
        raise ValueError("empty public key")

    size, p = _coord_bytes(curve), curve.p
    prefix, body = raw[0], raw[1:]

    if prefix == 0x04:
        if len(body) != 2 * size:
            raise ValueError(
                f"an uncompressed point on {curve.name} needs {1 + 2 * size} bytes, got {len(raw)}"
            )
        x = int.from_bytes(body[:size], "big")
        y = int.from_bytes(body[size:], "big")
        if x >= p or y >= p:
            raise ValueError("coordinate is not smaller than p")
    elif prefix in (0x02, 0x03):
        if len(body) != size:
            raise ValueError(f"a compressed point on {curve.name} needs {1 + size} bytes, got {len(raw)}")
        x = int.from_bytes(body, "big")
        if x >= p:
            raise ValueError("coordinate is not smaller than p")
        # Decompress: solve y^2 = x^3 + a*x + b (mod p), then pick the root
        # whose parity matches the prefix.
        rhs = (x * x * x + curve.a * x + curve.b) % p
        y = sqrt_mod(rhs, p)
        if y is None:
            raise ValueError("no point on the curve has this x-coordinate")
        if (y & 1) != (prefix & 1):
            y = (p - y) % p
        if (y & 1) != (prefix & 1):  # only when y = 0 but the prefix says "odd"
            raise ValueError("the parity prefix does not match any point with this x")
    else:
        raise ValueError(f"unknown point prefix 0x{prefix:02x} (expected 02, 03 or 04)")

    if not is_on_curve(curve, (x, y)):
        raise ValueError("this point is not on the curve")
    return (x, y)


# --------------------------------------------------------------------------
# Curve <-> JSON fields
# --------------------------------------------------------------------------
def _is_builtin(curve: Curve) -> bool:
    return CURVES.get(curve.name) == curve


def _curve_fields(curve: Curve) -> dict[str, str]:
    """The JSON fields that describe ``curve``: its name, plus parameters if custom."""
    if curve.name in CURVES and not _is_builtin(curve):
        raise ValueError(f"'{curve.name}' is the name of a built-in curve with different parameters")
    fields = {"curve": curve.name}
    if not _is_builtin(curve):
        fields.update(
            p=hex(curve.p), a=hex(curve.a), b=hex(curve.b),
            Gx=hex(curve.G[0]), Gy=hex(curve.G[1]), n=hex(curve.n), h=hex(curve.h),
        )
    return fields


def _get_int(doc: dict, key: str) -> int:
    """Read a number stored as a hex string ("0x1f" or "1f"); JSON integers are accepted too."""
    if key not in doc:
        raise ValueError(f"missing field '{key}'")
    value = doc[key]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 16)
        except ValueError:
            raise ValueError(f"field '{key}' is not a valid hex number") from None
    raise ValueError(f"field '{key}' must be a hex string")


def _curve_from_doc(doc: dict) -> Curve:
    """Find (built-in) or rebuild and validate (custom) the curve a key file refers to."""
    name = doc.get("curve")
    if not isinstance(name, str) or not name:
        raise ValueError("missing field 'curve' (the curve name)")
    has_parameters = any(key in doc for key in _CURVE_FIELDS)
    builtin = CURVES.get(name)
    if builtin is not None and not has_parameters:
        return builtin
    if builtin is None and not has_parameters:
        known = ", ".join(CURVES)
        raise ValueError(
            f"unknown curve '{name}' (built-in curves: {known}); a custom curve's file must "
            "also contain p, a, b, Gx, Gy, n and h"
        )
    curve = Curve(
        name=name,
        p=_get_int(doc, "p"), a=_get_int(doc, "a"), b=_get_int(doc, "b"),
        G=(_get_int(doc, "Gx"), _get_int(doc, "Gy")),
        n=_get_int(doc, "n"), h=_get_int(doc, "h"),
    )
    if builtin is not None:
        # A file must not be able to redefine a well-known curve.
        if curve != builtin:
            raise ValueError(f"the file's parameters do not match the built-in curve '{name}'")
        return builtin
    _validate_custom_curve(curve)
    return curve


def _validate_custom_curve(curve: Curve) -> None:
    """Sanity-check a curve that came from a file rather than from the registry."""
    p, a, b = curve.p, curve.a, curve.b
    if p.bit_length() > _MAX_FIELD_BITS:
        raise ValueError(f"p is too large (more than {_MAX_FIELD_BITS} bits)")
    if p <= 3 or p % 2 == 0:
        raise ValueError("p must be an odd prime greater than 3")
    if (4 * a * a * a + 27 * b * b) % p == 0:
        raise ValueError("the curve is singular (4a^3 + 27b^2 = 0 mod p)")
    gx, gy = curve.G
    if not (0 <= gx < p and 0 <= gy < p) or not is_on_curve(curve, curve.G):
        raise ValueError("the base point G is not on the curve")
    if curve.h < 1 or not 2 <= curve.n <= 2 * p + 2:
        raise ValueError("implausible values for n or h")
    try:
        n_times_g = scalar_mult(curve, curve.n, curve.G)
    except (ValueError, ZeroDivisionError):
        # Point arithmetic needs inverses mod p; they only all exist when p is prime.
        raise ValueError("the curve arithmetic fails - p is probably not a prime") from None
    if n_times_g is not None:
        raise ValueError("n is not the order of G (n * G != O)")


# --------------------------------------------------------------------------
# Reading / writing files
# --------------------------------------------------------------------------
def _write_json(path, payload: dict, *, private: bool) -> None:
    """Write atomically (temp file + rename); private keys get mode 0600."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    mode = 0o600 if private else 0o644
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    with contextlib.suppress(OSError):  # covers a pre-existing temp file; limited on Windows
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def _read_json(path) -> dict:
    path = Path(path)
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("file is too large to be a key file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("this is not a key file (it does not contain valid JSON)") from None
    if not isinstance(data, dict):
        raise ValueError("this is not a key file (expected a JSON object)")
    return data


def save_private_key(path, priv: PrivateKey) -> None:
    """Write ``priv`` as ``{"curve": name, "d": hex}``. The file is NOT encrypted."""
    if not 1 <= priv.d <= priv.curve.n - 1:
        raise ValueError("refusing to save an invalid private key (d not in [1, n-1])")
    payload = {**_curve_fields(priv.curve), "d": hex(priv.d)}
    _write_json(path, payload, private=True)


def load_private_key(path) -> PrivateKey:
    """Read a private key file. Raises ValueError if the content is not a valid key."""
    doc = _read_json(path)
    if "d" not in doc and ("Qx" in doc or "Qy" in doc):
        raise ValueError("this file contains a public key, not a private key")
    curve = _curve_from_doc(doc)
    d = _get_int(doc, "d")
    if not 1 <= d <= curve.n - 1:
        raise ValueError("the private key d is not in the range [1, n - 1]")
    return PrivateKey(d, curve)


def save_public_key(path, pub: PublicKey) -> None:
    """Write ``pub`` as ``{"curve": name, "Qx": hex, "Qy": hex}``."""
    validate_public_point(pub.curve, pub.Q)  # never write a key we would refuse to load
    payload = {**_curve_fields(pub.curve), "Qx": hex(pub.Q[0]), "Qy": hex(pub.Q[1])}
    _write_json(path, payload, private=False)


def load_public_key(path) -> PublicKey:
    """Read a public key file and validate the point (on the curve, not O, in G's subgroup)."""
    doc = _read_json(path)
    if "Qx" not in doc and "Qy" not in doc and "d" in doc:
        raise ValueError("this file contains a private key, not a public key")
    curve = _curve_from_doc(doc)
    Q = (_get_int(doc, "Qx"), _get_int(doc, "Qy"))
    validate_public_point(curve, Q)
    return PublicKey(Q, curve)

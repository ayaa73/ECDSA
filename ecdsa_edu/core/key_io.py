"""Writing keys down: hex strings and key files (owner: P2).

Part A - a public key as a hex string (the standard "SEC 1" format):

    uncompressed :  04 + X + Y
    compressed   :  02 + X   when Y is even
                    03 + X   when Y is odd

    X and Y are written in hexadecimal with a fixed number of digits.

Part B - key files, as small readable JSON text:

    private key :  {"curve": "toy-17", "d": "0x7"}
    public key  :  {"curve": "toy-17", "Qx": "0x0", "Qy": "0x6"}

    For a custom curve (one that is not built in) the file also stores the
    curve itself: "p", "a", "b", "Gx", "Gy", "n", "h". All numbers are hex.

The only math functions used from P1 are scalar_mult, is_on_curve and sqrt_mod.

NOTE: private-key files are NOT encrypted. This is a teaching tool.
"""
import json
import os

from .curve import Curve, is_on_curve, scalar_mult
from .curves_registry import CURVES
from .field import sqrt_mod
from .keys import validate_public_point
from .types import PrivateKey, PublicKey

HEX_DIGITS = "0123456789abcdef"
CURVE_FIELD_NAMES = ["p", "a", "b", "Gx", "Gy", "n", "h"]  # stored for custom curves only
MAX_FILE_BYTES = 1_000_000  # a key file is tiny; refuse anything much bigger
MAX_FIELD_BITS = 521  # the largest standard curve uses a 521-bit prime


# ==========================================================================
# Part A: point <-> hex string
# ==========================================================================
def _hex_digits_per_coordinate(curve: Curve) -> int:
    """How many hex digits one coordinate takes on this curve."""
    bits = curve.p.bit_length()  # p = 17 has 5 bits; secp256k1's p has 256
    number_of_bytes = (bits + 7) // 8  # divide by 8 and round up
    return 2 * number_of_bytes  # one byte is two hex digits


def _to_fixed_hex(number: int, digits: int) -> str:
    """Write `number` in hex with exactly `digits` digits, e.g. (6, 2) -> "06"."""
    text = hex(number)  # for example "0x6"
    text = text[2:]  # drop the "0x" in front -> "6"
    text = text.zfill(digits)  # put zeros in front until it is long enough -> "06"
    return text


def point_to_hex(curve: Curve, Q, compressed: bool = True) -> str:
    """Write the curve point Q as a lowercase hex string."""
    if Q is None:
        raise ValueError("the point at infinity cannot be encoded as a public key")

    x = Q[0]
    y = Q[1]
    x_in_range = 0 <= x < curve.p
    y_in_range = 0 <= y < curve.p
    if not x_in_range or not y_in_range or not is_on_curve(curve, Q):
        raise ValueError("the point is not on the curve")

    digits = _hex_digits_per_coordinate(curve)
    x_text = _to_fixed_hex(x, digits)
    y_text = _to_fixed_hex(y, digits)

    if compressed:
        # Only X is written. The first byte tells whether Y is even or odd.
        y_is_even = y % 2 == 0
        if y_is_even:
            return "02" + x_text
        else:
            return "03" + x_text
    else:
        return "04" + x_text + y_text


def _clean_hex(text) -> str:
    """Tidy up hex typed or pasted by a person. Raises ValueError if it is not hex."""
    if not isinstance(text, str):
        raise ValueError("expected a hex string")

    # People paste keys in many styles: "02 00", "02:00", "0x0200", "0200\n".
    # split() cuts the text at every space or line break, and "".join(...)
    # glues the pieces back together, so all the gaps disappear.
    text = "".join(text.split())
    text = text.replace(":", "")
    text = text.lower()
    if text.startswith("0x"):
        text = text[2:]

    if text == "":
        raise ValueError("empty public key")
    for character in text:
        if character not in HEX_DIGITS:
            raise ValueError("not a valid hex string (only the digits 0-9 and a-f are allowed)")
    if len(text) % 2 != 0:
        raise ValueError("not a valid hex string (need an even number of digits)")
    return text


def point_from_hex(curve: Curve, s: str) -> tuple[int, int]:
    """Read a hex string (compressed or uncompressed) and return the point (x, y).

    Raises ValueError, with a message for the user, for anything that is not a
    point on `curve`.
    """
    text = _clean_hex(s)
    p = curve.p
    digits = _hex_digits_per_coordinate(curve)

    prefix = text[0:2]  # the first byte: "04", "02" or "03"
    body = text[2:]  # everything after it

    if prefix == "04":
        # Uncompressed: X followed by Y.
        if len(body) != 2 * digits:
            raise ValueError(
                "an uncompressed point on " + curve.name + " needs "
                + str(2 + 2 * digits) + " hex digits, got " + str(len(text))
            )
        x = int(body[0:digits], 16)  # int(..., 16) reads hexadecimal text
        y = int(body[digits:], 16)
        if x >= p or y >= p:
            raise ValueError("coordinate is not smaller than p")

    elif prefix == "02" or prefix == "03":
        # Compressed: only X is given, and we must work out Y.
        if len(body) != digits:
            raise ValueError(
                "a compressed point on " + curve.name + " needs "
                + str(2 + digits) + " hex digits, got " + str(len(text))
            )
        x = int(body, 16)
        if x >= p:
            raise ValueError("coordinate is not smaller than p")

        # The curve equation is y^2 = x^3 + a*x + b (mod p).
        # Compute the right-hand side, then ask P1's sqrt_mod for a square root.
        right_side = (x * x * x + curve.a * x + curve.b) % p
        y = sqrt_mod(right_side, p)
        if y is None:
            raise ValueError("no point on the curve has this x-coordinate")

        # There are two square roots: y and p - y. One is even, the other odd.
        # The prefix says which one the writer meant.
        wanted_odd = prefix == "03"
        y_is_odd = y % 2 == 1
        if y_is_odd != wanted_odd:
            y = (p - y) % p  # take the other root
        # Rare corner: when y is 0 there is only one root, and it is even.
        y_is_odd = y % 2 == 1
        if y_is_odd != wanted_odd:
            raise ValueError("the parity prefix does not match any point with this x")

    else:
        raise ValueError("unknown point prefix " + prefix + " (expected 02, 03 or 04)")

    # Final safety check before we hand the point back.
    if not is_on_curve(curve, (x, y)):
        raise ValueError("this point is not on the curve")
    return (x, y)


# ==========================================================================
# Part B: the curve inside a key file
# ==========================================================================
def _is_builtin(curve: Curve) -> bool:
    """True if `curve` is one of the built-in curves (same name AND same numbers)."""
    if curve.name not in CURVES:
        return False
    return CURVES[curve.name] == curve


def _curve_to_fields(curve: Curve) -> dict:
    """The part of a key file that says which curve the key is on."""
    if curve.name in CURVES and not _is_builtin(curve):
        # Same name as a built-in curve but different numbers: refuse.
        raise ValueError("'" + curve.name + "' is the name of a built-in curve with different parameters")

    fields = {}
    fields["curve"] = curve.name
    if not _is_builtin(curve):
        # A custom curve's name means nothing on another computer,
        # so its numbers travel with the key.
        fields["p"] = hex(curve.p)
        fields["a"] = hex(curve.a)
        fields["b"] = hex(curve.b)
        fields["Gx"] = hex(curve.G[0])
        fields["Gy"] = hex(curve.G[1])
        fields["n"] = hex(curve.n)
        fields["h"] = hex(curve.h)
    return fields


def _read_number(document: dict, name: str) -> int:
    """Read one number from a loaded key file. Numbers are stored as hex text."""
    if name not in document:
        raise ValueError("missing field '" + name + "'")
    value = document[name]

    # A plain JSON number is accepted as it is (but not true/false).
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    # Normally the value is text such as "0x1f" or "1f".
    if isinstance(value, str) and value.strip() != "":
        try:
            return int(value.strip(), 16)
        except ValueError:
            raise ValueError("field '" + name + "' is not a valid hex number")

    raise ValueError("field '" + name + "' must be a hex string")


def _file_has_curve_numbers(document: dict) -> bool:
    """True if the file contains at least one of p, a, b, Gx, Gy, n, h."""
    for name in CURVE_FIELD_NAMES:
        if name in document:
            return True
    return False


def _curve_from_fields(document: dict) -> Curve:
    """Work out which curve a key file means, and make sure it can be trusted."""
    name = document.get("curve")
    if not isinstance(name, str) or name == "":
        raise ValueError("missing field 'curve' (the curve name)")

    has_numbers = _file_has_curve_numbers(document)
    name_is_builtin = name in CURVES

    # Case 1: a built-in curve, named only. This is the normal case.
    if name_is_builtin and not has_numbers:
        return CURVES[name]

    # Case 2: an unknown name and no numbers. We cannot know the curve.
    if not name_is_builtin and not has_numbers:
        builtin_names = ", ".join(CURVES)
        raise ValueError(
            "unknown curve '" + name + "' (built-in curves: " + builtin_names + "); "
            "a custom curve's file must also contain p, a, b, Gx, Gy, n and h"
        )

    # Cases 3 and 4: the file brings its own numbers. Build the curve from them.
    gx = _read_number(document, "Gx")
    gy = _read_number(document, "Gy")
    curve = Curve(
        name=name,
        p=_read_number(document, "p"),
        a=_read_number(document, "a"),
        b=_read_number(document, "b"),
        G=(gx, gy),
        n=_read_number(document, "n"),
        h=_read_number(document, "h"),
    )

    # Case 3: a built-in name with numbers. They must match exactly, so that
    # a file can never quietly redefine a well-known curve.
    if name_is_builtin:
        if curve != CURVES[name]:
            raise ValueError("the file's parameters do not match the built-in curve '" + name + "'")
        return CURVES[name]

    # Case 4: a real custom curve. Check it before trusting it.
    _check_custom_curve(curve)
    return curve


def _check_custom_curve(curve: Curve) -> None:
    """Sanity checks for a curve that came from a file. Raises ValueError if it is bad."""
    p = curve.p
    a = curve.a
    b = curve.b

    if p.bit_length() > MAX_FIELD_BITS:
        raise ValueError("p is too large (more than " + str(MAX_FIELD_BITS) + " bits)")
    if p <= 3 or p % 2 == 0:
        raise ValueError("p must be an odd prime greater than 3")

    # A "singular" curve has a sharp corner or crosses itself, and point
    # addition does not work on it. This formula detects that.
    if (4 * a * a * a + 27 * b * b) % p == 0:
        raise ValueError("the curve is singular (4a^3 + 27b^2 = 0 mod p)")

    gx = curve.G[0]
    gy = curve.G[1]
    g_in_range = 0 <= gx < p and 0 <= gy < p
    if not g_in_range or not is_on_curve(curve, curve.G):
        raise ValueError("the base point G is not on the curve")

    if curve.h < 1 or curve.n < 2 or curve.n > 2 * p + 2:
        raise ValueError("implausible values for n or h")

    # n must really be the order of G: n * G has to be the point at infinity.
    try:
        n_times_g = scalar_mult(curve, curve.n, curve.G)
    except (ValueError, ZeroDivisionError):
        # Point arithmetic needs divisions mod p, which only always work when p is prime.
        raise ValueError("the curve arithmetic fails - p is probably not a prime")
    if n_times_g is not None:
        raise ValueError("n is not the order of G (n * G != O)")


# ==========================================================================
# Part C: reading and writing the files
# ==========================================================================
def _write_json_file(path, content: dict, is_private: bool) -> None:
    """Write `content` to `path` as readable JSON text.

    Safety: we first write to a temporary file and then rename it. If the
    program stops in the middle, the real file is never left half-written.
    """
    temporary_path = str(path) + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        file.write(json.dumps(content, indent=2))
        file.write("\n")

    if is_private:
        # 0o600 = only the owner of the file may read or write it.
        # (This has little effect on Windows; if it fails we simply carry on.)
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass

    os.replace(temporary_path, path)  # rename the temporary file to the real name


def _read_json_file(path) -> dict:
    """Read a key file and return its content as a dictionary."""
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise ValueError("file is too large to be a key file")

    try:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
        document = json.loads(text)
    except UnicodeDecodeError:
        raise ValueError("this is not a key file (it is not readable text)")
    except json.JSONDecodeError:
        raise ValueError("this is not a key file (it does not contain valid JSON)")

    if not isinstance(document, dict):
        raise ValueError("this is not a key file (expected a JSON object)")
    return document


def save_private_key(path, priv: PrivateKey) -> None:
    """Write a private key file: {"curve": name, "d": hex}. The file is NOT encrypted."""
    if priv.d < 1 or priv.d > priv.curve.n - 1:
        raise ValueError("refusing to save an invalid private key (d not in [1, n-1])")

    content = _curve_to_fields(priv.curve)
    content["d"] = hex(priv.d)
    _write_json_file(path, content, is_private=True)


def load_private_key(path) -> PrivateKey:
    """Read a private key file. Raises ValueError if the content is not a valid key."""
    document = _read_json_file(path)

    # A friendly message if the user picked a public-key file by mistake.
    looks_like_public_key = "Qx" in document or "Qy" in document
    if "d" not in document and looks_like_public_key:
        raise ValueError("this file contains a public key, not a private key")

    curve = _curve_from_fields(document)
    d = _read_number(document, "d")
    if d < 1 or d > curve.n - 1:
        raise ValueError("the private key d is not in the range [1, n - 1]")
    return PrivateKey(d, curve)


def save_public_key(path, pub: PublicKey) -> None:
    """Write a public key file: {"curve": name, "Qx": hex, "Qy": hex}."""
    validate_public_point(pub.curve, pub.Q)  # never write a key we would refuse to load

    content = _curve_to_fields(pub.curve)
    content["Qx"] = hex(pub.Q[0])
    content["Qy"] = hex(pub.Q[1])
    _write_json_file(path, content, is_private=False)


def load_public_key(path) -> PublicKey:
    """Read a public key file and check the point (on the curve, not O, a multiple of G)."""
    document = _read_json_file(path)

    # A friendly message if the user picked a private-key file by mistake.
    has_point = "Qx" in document or "Qy" in document
    if not has_point and "d" in document:
        raise ValueError("this file contains a private key, not a public key")

    curve = _curve_from_fields(document)
    qx = _read_number(document, "Qx")
    qy = _read_number(document, "Qy")
    Q = (qx, qy)
    validate_public_point(curve, Q)
    return PublicKey(Q, curve)

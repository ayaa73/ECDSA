# the keys.py file makes the keys
# the key_io.py file writes them down and reads them back
# to send a key to someone, paste it or save if for longer than the app running time, need to turn it into text

import json  # turns Python dictionaries into JSON text and back
import os    # file operations: size, permissions, safe rename

from .curve import Curve, is_on_curve, scalar_mult   # P1: curve object and point math
from .curves_registry import CURVES                  # P1: the built-in curves, by name
from .field import sqrt_mod                          # P1: square root mod p (for compressed keys)
from .keys import validate_public_point              # ours: the 4 public-key checks
from .types import PrivateKey, PublicKey             # ours: the key containers

HEX_DIGITS = "0123456789abcdef"                         # the only characters allowed in hex
CURVE_FIELD_NAMES = ["p", "a", "b", "Gx", "Gy", "n", "h"]  # saved for custom curves only
MAX_FILE_BYTES = 1_000_000  # a real key file is tiny; refuse anything bigger than 1 MB
MAX_FIELD_BITS = 521        # the biggest standard curve uses a 521-bit prime


"""
Part a: public key as hex string 
A public key is a point, two numbers like (0, 6). To share it (copy it into a chat, a website, a file), you need it as one piece of text. 
here we convert between the two forms (point and hex)
"""
def _hex_digits_per_coordinate(curve):
    """How many hex digits one coordinate takes on this curve (always even)."""
    bits = curve.p.bit_length()       # p = 17 has 5 bits; secp256k1's p has 256
    number_of_bytes = (bits + 7) // 8  # bits / 8, rounded up: 5 bits -> 1 byte
    return 2 * number_of_bytes         # one byte = two hex digits


def _to_fixed_hex(number, digits):
    """Write `number` in hex with exactly `digits` digits, e.g. (6, 2) -> "06"."""
    text = hex(number)         # 6 -> "0x6"
    text = text[2:]            # cut off the "0x" -> "6"
    text = text.zfill(digits)  # add zeros in front until long enough -> "06"
    return text


def point_to_hex(curve, Q, compressed=True):
    """Write the point Q as a hex string: "02.."/"03.." (compressed) or "04.." (full)."""
    if Q is None:
        raise ValueError("the point at infinity cannot be encoded as a public key")

    x = Q[0]
    y = Q[1]
    # Never write down something that is not a real point on this curve.
    if x < 0 or x >= curve.p or y < 0 or y >= curve.p or not is_on_curve(curve, Q):
        raise ValueError("the point is not on the curve")

    digits = _hex_digits_per_coordinate(curve)
    x_text = _to_fixed_hex(x, digits)
    y_text = _to_fixed_hex(y, digits)

    if not compressed:
        return "04" + x_text + y_text  # both coordinates
    if y % 2 == 0:
        return "02" + x_text           # only x; "02" says y is even
    return "03" + x_text               # only x; "03" says y is odd


def _clean_hex(text):
    """Tidy up hex typed or pasted by a person. Raises ValueError if it is not hex."""
    if type(text) != str:
        raise ValueError("expected a hex string")

    # People paste keys in many styles: "02 00", "02:00", "0x0200", "0200\n".
    text = "".join(text.split())  # split() cuts at spaces/new lines, join glues back: no gaps
    text = text.replace(":", "")  # remove colons
    text = text.lower()           # "AB" -> "ab"
    if text.startswith("0x"):
        text = text[2:]           # remove a leading "0x"

    if text == "":
        raise ValueError("empty public key")
    for character in text:
        if character not in HEX_DIGITS:
            raise ValueError("not a valid hex string (only the digits 0-9 and a-f are allowed)")
    if len(text) % 2 != 0:
        raise ValueError("not a valid hex string (need an even number of digits)")
    return text


def point_from_hex(curve, s):
    """Read a hex string (compressed or uncompressed) and return the point (x, y).

    Raises ValueError, with a message for the user, if it is not a point on `curve`.
    """
    text = _clean_hex(s)
    p = curve.p
    digits = _hex_digits_per_coordinate(curve)

    prefix = text[0:2]  # first byte: "04", "02" or "03"
    body = text[2:]     # everything after it

    if prefix == "04":
        # Uncompressed: X then Y, each exactly `digits` long.
        if len(body) != 2 * digits:
            raise ValueError("an uncompressed point on " + curve.name + " needs "
                             + str(2 + 2 * digits) + " hex digits, got " + str(len(text)))
        x = int(body[0:digits], 16)  # int(text, 16) reads hexadecimal
        y = int(body[digits:], 16)
        if x >= p or y >= p:
            raise ValueError("coordinate is not smaller than p")

    elif prefix == "02" or prefix == "03":
        # Compressed: only X is given, so we work out Y.
        if len(body) != digits:
            raise ValueError("a compressed point on " + curve.name + " needs "
                             + str(2 + digits) + " hex digits, got " + str(len(text)))
        x = int(body, 16)
        if x >= p:
            raise ValueError("coordinate is not smaller than p")

        # Curve equation: y^2 = x^3 + a*x + b (mod p). Compute the right side...
        right_side = (x * x * x + curve.a * x + curve.b) % p
        # ...and ask P1's sqrt_mod for one square root (None if there is none).
        y = sqrt_mod(right_side, p)
        if y is None:
            raise ValueError("no point on the curve has this x-coordinate")

        # The two roots are y and p - y: one even, one odd. Pick the one the prefix asks for.
        want_odd = (prefix == "03")
        if (y % 2 == 1) != want_odd:
            y = (p - y) % p  # take the other root
        # Rare corner: if y is 0 there is only one root (even), so "03" cannot match.
        if (y % 2 == 1) != want_odd:
            raise ValueError("the parity prefix does not match any point with this x")

    else:
        raise ValueError("unknown point prefix " + prefix + " (expected 02, 03 or 04)")

    # Final safety check before handing the point back.
    if not is_on_curve(curve, (x, y)):
        raise ValueError("this point is not on the curve")
    return (x, y)


# ==========================================================================
# Part B: which curve a key file belongs to
# ==========================================================================
def _is_builtin(curve):
    """True if `curve` is one of the built-in curves (same name AND same numbers)."""
    if curve.name not in CURVES:
        return False
    return CURVES[curve.name] == curve


def _curve_to_fields(curve):
    """The part of a key file that says which curve the key is on."""
    if curve.name in CURVES and not _is_builtin(curve):
        # Same name as a built-in curve but different numbers: refuse, it would confuse everyone.
        raise ValueError("'" + curve.name + "' is the name of a built-in curve with different parameters")

    fields = {"curve": curve.name}
    if not _is_builtin(curve):
        # A custom curve's name means nothing on another computer, so its numbers travel with the key.
        fields["p"] = hex(curve.p)
        fields["a"] = hex(curve.a)
        fields["b"] = hex(curve.b)
        fields["Gx"] = hex(curve.G[0])
        fields["Gy"] = hex(curve.G[1])
        fields["n"] = hex(curve.n)
        fields["h"] = hex(curve.h)
    return fields


def _read_number(document, name):
    """Read one number from a loaded key file (numbers are stored as hex text)."""
    if name not in document:
        raise ValueError("missing field '" + name + "'")
    value = document[name]

    # A plain JSON number is accepted as it is (type() also refuses true/false).
    if type(value) == int:
        return value

    # Normally the value is text such as "0x1f" or "1f".
    if type(value) == str and value.strip() != "":
        try:
            return int(value.strip(), 16)
        except ValueError:
            raise ValueError("field '" + name + "' is not a valid hex number")

    raise ValueError("field '" + name + "' must be a hex string")


def _file_has_curve_numbers(document):
    """True if the file contains at least one of p, a, b, Gx, Gy, n, h."""
    for name in CURVE_FIELD_NAMES:
        if name in document:
            return True
    return False


def _curve_from_fields(document):
    """Work out which curve a key file means, and make sure it can be trusted."""
    name = document.get("curve")  # .get gives None instead of crashing if it is missing
    if type(name) != str or name == "":
        raise ValueError("missing field 'curve' (the curve name)")

    has_numbers = _file_has_curve_numbers(document)
    name_is_builtin = name in CURVES

    # Case 1: a built-in curve, named only. This is the normal case.
    if name_is_builtin and not has_numbers:
        return CURVES[name]

    # Case 2: an unknown name and no numbers. We cannot know the curve.
    if not name_is_builtin and not has_numbers:
        raise ValueError("unknown curve '" + name + "' (built-in curves: " + ", ".join(CURVES) + "); "
                         "a custom curve's file must also contain p, a, b, Gx, Gy, n and h")

    # Cases 3 and 4: the file brings its own numbers. Build a curve from them.
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

    # Case 3: a built-in name with numbers. They must match exactly,
    # so a file can never quietly redefine a well-known curve.
    if name_is_builtin:
        if curve != CURVES[name]:
            raise ValueError("the file's parameters do not match the built-in curve '" + name + "'")
        return CURVES[name]

    # Case 4: a real custom curve. Check it before trusting it.
    _check_custom_curve(curve)
    return curve


def _check_custom_curve(curve):
    """Sanity checks for a curve that came from a file. Raises ValueError if it is bad."""
    p = curve.p
    a = curve.a
    b = curve.b

    if p.bit_length() > MAX_FIELD_BITS:
        raise ValueError("p is too large (more than " + str(MAX_FIELD_BITS) + " bits)")
    if p <= 3 or p % 2 == 0:
        raise ValueError("p must be an odd prime greater than 3")

    # A "singular" curve has a sharp corner or crosses itself; point addition breaks on it.
    if (4 * a * a * a + 27 * b * b) % p == 0:
        raise ValueError("the curve is singular (4a^3 + 27b^2 = 0 mod p)")

    gx = curve.G[0]
    gy = curve.G[1]
    if gx < 0 or gx >= p or gy < 0 or gy >= p or not is_on_curve(curve, curve.G):
        raise ValueError("the base point G is not on the curve")

    if curve.h < 1 or curve.n < 2 or curve.n > 2 * p + 2:
        raise ValueError("implausible values for n or h")

    # n must really be the order of G: n * G has to be the point at infinity.
    # If p is secretly not prime, a division inside scalar_mult fails; we catch
    # that error and give a clear message instead of a crash.
    try:
        n_times_g = scalar_mult(curve, curve.n, curve.G)
    except (ValueError, ZeroDivisionError):
        raise ValueError("the curve arithmetic fails - p is probably not a prime")
    if n_times_g is not None:
        raise ValueError("n is not the order of G (n * G != O)")


# ==========================================================================
# Part C: reading and writing the files
# ==========================================================================
def _write_json_file(path, content, is_private):
    """Write `content` (a dictionary) to `path` as readable JSON text.

    Safety: write to a temporary file first, then rename it. If the program
    stops in the middle, the real file is never left half-written.
    """
    temporary_path = str(path) + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:  # "w" = write; closes itself at the end
        file.write(json.dumps(content, indent=2))  # dictionary -> nicely indented JSON text
        file.write("\n")

    if is_private:
        # 0o600 = only the file's owner may read or write it.
        # (Little effect on Windows; if it fails we simply carry on.)
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass

    os.replace(temporary_path, path)  # rename the temporary file to the real name in one step


def _read_json_file(path):
    """Read a key file and return its content as a dictionary."""
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise ValueError("file is too large to be a key file")

    try:
        with open(path, "r", encoding="utf-8") as file:  # "r" = read
            text = file.read()
        document = json.loads(text)  # JSON text -> Python dictionary
    except UnicodeDecodeError:
        raise ValueError("this is not a key file (it is not readable text)")
    except json.JSONDecodeError:
        raise ValueError("this is not a key file (it does not contain valid JSON)")

    if type(document) != dict:
        raise ValueError("this is not a key file (expected a JSON object)")
    return document


def save_private_key(path, priv):
    """Write a private key file: {"curve": name, "d": hex}. The file is NOT encrypted."""
    if priv.d < 1 or priv.d > priv.curve.n - 1:
        raise ValueError("refusing to save an invalid private key (d not in [1, n-1])")

    content = _curve_to_fields(priv.curve)
    content["d"] = hex(priv.d)
    _write_json_file(path, content, is_private=True)


def load_private_key(path):
    """Read a private key file. Raises ValueError if it does not hold a valid key."""
    document = _read_json_file(path)

    # Friendly message if the user picked a public-key file by mistake.
    if "d" not in document and ("Qx" in document or "Qy" in document):
        raise ValueError("this file contains a public key, not a private key")

    curve = _curve_from_fields(document)
    d = _read_number(document, "d")
    if d < 1 or d > curve.n - 1:
        raise ValueError("the private key d is not in the range [1, n - 1]")
    return PrivateKey(d, curve)


def save_public_key(path, pub):
    """Write a public key file: {"curve": name, "Qx": hex, "Qy": hex}."""
    validate_public_point(pub.curve, pub.Q)  # never write a key we would refuse to load

    content = _curve_to_fields(pub.curve)
    content["Qx"] = hex(pub.Q[0])
    content["Qy"] = hex(pub.Q[1])
    _write_json_file(path, content, is_private=False)


def load_public_key(path):
    """Read a public key file and run the 4 public-key checks on the point."""
    document = _read_json_file(path)

    # Friendly message if the user picked a private-key file by mistake.
    if "Qx" not in document and "Qy" not in document and "d" in document:
        raise ValueError("this file contains a private key, not a public key")

    curve = _curve_from_fields(document)
    Q = (_read_number(document, "Qx"), _read_number(document, "Qy"))
    validate_public_point(curve, Q)
    return PublicKey(Q, curve)

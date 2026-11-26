"""Small X.509 certificates for ECDSA keys, written from scratch (no libraries).

A certificate is a public key plus a name, wrapped in ASN.1 DER and signed.
This module does just enough of X.509 (RFC 5280) for the app:

* ``make_self_signed_certificate`` puts an EC public key and a name into a
  version-3 certificate and signs it with the matching private key, using this
  project's own ECDSA (``core.sign``).
* ``load_certificate`` reads a PEM or DER certificate, returns the subject,
  validity, curve and public key, and checks the self-signature with
  ``core.verify`` when the certificate is self-signed.

Only the named curves that X.509 knows are supported: secp256k1 and P-256.
The toy curves (and custom curves) have no standard object identifier, so
they cannot appear in a standard certificate.
"""
from __future__ import annotations

import base64
import binascii
import datetime as _dt
import secrets
from dataclasses import dataclass

from ecdsa_edu.core.curve import Curve
from ecdsa_edu.core.curves_registry import CURVES
from ecdsa_edu.core.key_io import point_from_hex, point_to_hex
from ecdsa_edu.core.keys import validate_public_point
from ecdsa_edu.core.sig_encoding import sig_from_der, sig_to_der
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.types import PrivateKey, PublicKey, Signature
from ecdsa_edu.core.verify import verify

__all__ = [
    "CERTIFICATE_EXTENSIONS", "CertificateInfo", "certificate_supported", "load_certificate",
    "make_self_signed_certificate", "to_pem",
]

CERTIFICATE_EXTENSIONS = (".pem", ".crt", ".cer", ".der")

# Object identifiers (OIDs) used below.
_OID_EC_PUBLIC_KEY = "1.2.840.10045.2.1"
_OID_COMMON_NAME = "2.5.4.3"
_CURVE_OIDS = {"secp256k1": "1.3.132.0.10", "P-256": "1.2.840.10045.3.1.7"}
_SIGNATURE_OIDS = {
    "sha256": "1.2.840.10045.4.3.2",  # ecdsa-with-SHA256
    "sha384": "1.2.840.10045.4.3.3",
    "sha512": "1.2.840.10045.4.3.4",
}
_PEM_BEGIN, _PEM_END = "-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"


def certificate_supported(curve: Curve) -> bool:
    """True if keys on ``curve`` can be put in a standard X.509 certificate."""
    return curve.name in _CURVE_OIDS and CURVES.get(curve.name) == curve


# ---------------------------------------------------------------- DER writing
def _length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _length(len(content)) + content


def _sequence(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _integer(value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw  # keep it positive
    return _tlv(0x02, raw)


def _oid(dotted: str) -> bytes:
    numbers = [int(part) for part in dotted.split(".")]
    body = bytearray([40 * numbers[0] + numbers[1]])
    for number in numbers[2:]:
        chunk = [number & 0x7F]
        number >>= 7
        while number:
            chunk.append(0x80 | (number & 0x7F))
            number >>= 7
        body.extend(reversed(chunk))
    return _tlv(0x06, bytes(body))


def _bit_string(data: bytes) -> bytes:
    return _tlv(0x03, b"\x00" + data)  # 0 unused bits


def _name(common_name: str) -> bytes:
    attribute = _sequence(_oid(_OID_COMMON_NAME), _tlv(0x0C, common_name.encode("utf-8")))
    return _sequence(_tlv(0x31, attribute))  # Name = SEQUENCE OF SET OF AttributeTypeAndValue


def _time(moment: _dt.datetime) -> bytes:
    if moment.year < 2050:
        return _tlv(0x17, moment.strftime("%y%m%d%H%M%SZ").encode())  # UTCTime
    return _tlv(0x18, moment.strftime("%Y%m%d%H%M%SZ").encode())      # GeneralizedTime


# ---------------------------------------------------------------- DER reading
class _Reader:
    """Walks through DER bytes one TLV at a time."""

    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0

    def done(self) -> bool:
        return self.pos >= len(self.data)

    def read(self, expected_tag: int | None = None) -> tuple[int, bytes, bytes]:
        """Return (tag, content, whole TLV)."""
        start = self.pos
        if self.pos + 2 > len(self.data):
            raise ValueError("the file ends in the middle of the certificate")
        tag, first = self.data[self.pos], self.data[self.pos + 1]
        self.pos += 2
        if first & 0x80:
            count = first & 0x7F
            if count == 0 or count > 4 or self.pos + count > len(self.data):
                raise ValueError("the certificate has a broken length field")
            length = int.from_bytes(self.data[self.pos:self.pos + count], "big")
            self.pos += count
        else:
            length = first
        end = self.pos + length
        if end > len(self.data):
            raise ValueError("the file ends in the middle of the certificate")
        if expected_tag is not None and tag != expected_tag:
            raise ValueError("this is not the structure of an X.509 certificate")
        content = self.data[self.pos:end]
        self.pos = end
        return tag, content, self.data[start:end]


def _read_oid(content: bytes) -> str:
    if not content:
        raise ValueError("empty object identifier")
    numbers = [content[0] // 40, content[0] % 40]
    value = 0
    for byte in content[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            numbers.append(value)
            value = 0
    return ".".join(map(str, numbers))


def _read_name(content: bytes) -> str:
    """The common name (CN) of a Name, or the empty string if it has none."""
    names = _Reader(content)
    while not names.done():
        _, rdn, _ = names.read(0x31)
        attributes = _Reader(rdn)
        while not attributes.done():
            _, pair, _ = attributes.read(0x30)
            inner = _Reader(pair)
            _, oid, _ = inner.read(0x06)
            _, value, _ = inner.read()
            if _read_oid(oid) == _OID_COMMON_NAME:
                return value.decode("utf-8", errors="replace")
    return ""


def _read_time(tag: int, content: bytes) -> _dt.datetime:
    text = content.decode("ascii", errors="replace")
    fmt = "%y%m%d%H%M%SZ" if tag == 0x17 else "%Y%m%d%H%M%SZ"
    try:
        return _dt.datetime.strptime(text, fmt).replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        raise ValueError(f"unreadable date in the certificate: {text!r}") from None


# ---------------------------------------------------------------- public API
@dataclass(frozen=True)
class CertificateInfo:
    subject: str
    issuer: str
    not_before: _dt.datetime
    not_after: _dt.datetime
    public_key: PublicKey
    hash_name: str           # hash of the certificate's own signature
    self_signed: bool
    signature_valid: bool | None  # None: issued by someone else, so it cannot be checked here
    der: bytes

    @property
    def curve(self) -> Curve:
        return self.public_key.curve

    def is_current(self, now: _dt.datetime | None = None) -> bool:
        now = now or _dt.datetime.now(_dt.timezone.utc)
        return self.not_before <= now <= self.not_after


def make_self_signed_certificate(
    priv: PrivateKey,
    pub: PublicKey,
    common_name: str = "ECDSA Lab demo key",
    days: int = 365,
    hash_name: str = "sha256",
    now: _dt.datetime | None = None,
) -> bytes:
    """A DER-encoded, self-signed X.509 v3 certificate for ``pub``, signed with ``priv``."""
    curve = pub.curve
    if priv.curve != curve:
        raise ValueError("the private and the public key belong to different curves")
    if not certificate_supported(curve):
        raise ValueError(f"{curve.name} has no standard name in X.509, so it cannot go into a certificate. "
                         "Use secp256k1 or P-256.")
    if hash_name not in _SIGNATURE_OIDS:
        raise ValueError(f"certificates here are signed with SHA-256, SHA-384 or SHA-512, not {hash_name}")
    now = (now or _dt.datetime.now(_dt.timezone.utc)).replace(microsecond=0)
    algorithm = _sequence(_oid(_SIGNATURE_OIDS[hash_name]))
    name = _name(common_name)
    point = bytes.fromhex(point_to_hex(curve, pub.Q, compressed=False))
    key_info = _sequence(_sequence(_oid(_OID_EC_PUBLIC_KEY), _oid(_CURVE_OIDS[curve.name])), _bit_string(point))
    tbs = _sequence(
        _tlv(0xA0, _integer(2)),                 # version 3
        _integer(secrets.randbits(63) | 1),      # serial number: positive and non-zero
        algorithm,
        name,                                    # issuer = subject: self-signed
        _sequence(_time(now), _time(now + _dt.timedelta(days=days))),
        name,
        key_info,
    )
    signature = sign(priv, tbs, hash_name)
    return _sequence(tbs, algorithm, _bit_string(sig_to_der(signature)))


def to_pem(der: bytes) -> str:
    body = base64.b64encode(der).decode("ascii")
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "\n".join([_PEM_BEGIN, *lines, _PEM_END]) + "\n"


def _der_from_file_bytes(data: bytes) -> bytes:
    text = data.lstrip()
    if text.startswith(b"-----BEGIN"):
        decoded = data.decode("ascii", errors="replace")
        if _PEM_BEGIN not in decoded:
            raise ValueError("this PEM file does not contain a certificate (it may be a key file)")
        body = decoded.split(_PEM_BEGIN, 1)[1].split(_PEM_END, 1)[0]
        try:
            return base64.b64decode("".join(body.split()), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("the PEM text is damaged (invalid base64)") from None
    if not data or data[0] != 0x30:
        raise ValueError("this is not a certificate: expected PEM text or DER bytes")
    return data


def load_certificate(data: bytes) -> CertificateInfo:
    """Read a PEM or DER certificate. Raises ValueError with a readable reason."""
    der = _der_from_file_bytes(data)
    outer = _Reader(der)
    _, certificate, _ = outer.read(0x30)
    if not outer.done():
        raise ValueError("unexpected extra data after the certificate")
    parts = _Reader(certificate)
    _, tbs_content, tbs = parts.read(0x30)
    _, algorithm, _ = parts.read(0x30)
    _, signature_bits, _ = parts.read(0x03)

    fields = _Reader(tbs_content)
    tag, _, _ = fields.read()
    if tag == 0xA0:  # optional version; the serial number follows
        fields.read(0x02)
    elif tag != 0x02:
        raise ValueError("this is not the structure of an X.509 certificate")
    fields.read(0x30)  # signature algorithm (repeated inside the signed part)
    _, issuer, _ = fields.read(0x30)
    _, validity, _ = fields.read(0x30)
    _, subject, _ = fields.read(0x30)
    _, key_info, _ = fields.read(0x30)

    times = _Reader(validity)
    tag1, start, _ = times.read()
    tag2, end, _ = times.read()

    key_parts = _Reader(key_info)
    _, key_algorithm, _ = key_parts.read(0x30)
    _, key_bits, _ = key_parts.read(0x03)
    algorithm_parts = _Reader(key_algorithm)
    _, key_type, _ = algorithm_parts.read(0x06)
    if _read_oid(key_type) != _OID_EC_PUBLIC_KEY:
        raise ValueError("this certificate does not hold an elliptic-curve (ECDSA) key; it may be an RSA "
                         "certificate")
    tag, curve_oid, _ = algorithm_parts.read()
    curve_name = next((name for name, oid in _CURVE_OIDS.items() if tag == 0x06 and oid == _read_oid(curve_oid)),
                      None)
    if curve_name is None:
        shown = _read_oid(curve_oid) if tag == 0x06 else "explicit parameters"
        raise ValueError(f"the key uses a curve this app does not support ({shown}); secp256k1 and P-256 are "
                         "supported")
    curve = CURVES[curve_name]
    if not key_bits or key_bits[0] != 0:
        raise ValueError("the public key in the certificate is damaged")
    Q = point_from_hex(curve, key_bits[1:].hex())
    validate_public_point(curve, Q)
    public_key = PublicKey(Q, curve)

    algorithm_oid = _read_oid(_Reader(algorithm).read(0x06)[1])
    hash_name = next((h for h, oid in _SIGNATURE_OIDS.items() if oid == algorithm_oid), "")
    issuer_cn, subject_cn = _read_name(issuer), _read_name(subject)
    self_signed = issuer == subject
    valid: bool | None = None
    if self_signed:
        valid = False
        if hash_name and signature_bits[:1] == b"\x00":
            try:
                signature: Signature = sig_from_der(signature_bits[1:])
                valid = verify(public_key, tbs, signature, hash_name)
            except ValueError:
                valid = False
    return CertificateInfo(subject_cn, issuer_cn, _read_time(tag1, start), _read_time(tag2, end), public_key,
                           hash_name, self_signed, valid, der)

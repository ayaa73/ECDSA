"""core/x509.py: our own certificates, cross-checked with the 'cryptography'
package (a test-only reference, like in the other core tests)."""
from __future__ import annotations

import datetime as dt

import pytest

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.types import PrivateKey, PublicKey
from ecdsa_edu.core.x509 import (
    certificate_supported, load_certificate, make_self_signed_certificate, to_pem,
)

crypto = pytest.importorskip("cryptography")
from cryptography import x509 as cx509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

REAL = ["secp256k1", "P-256"]
CRYPTO_CURVES = {"secp256k1": ec.SECP256K1(), "P-256": ec.SECP256R1()}


def test_only_named_curves_are_supported():
    assert certificate_supported(get_curve("secp256k1")) and certificate_supported(get_curve("P-256"))
    assert not certificate_supported(get_curve("toy-17")) and not certificate_supported(get_curve("toy-97"))
    toy = get_curve("toy-17")
    with pytest.raises(ValueError, match="no standard name"):
        make_self_signed_certificate(PrivateKey(7, toy), PublicKey((0, 6), toy))


@pytest.mark.parametrize("curve_name", REAL)
@pytest.mark.parametrize("hash_name", ["sha256", "sha512"])
def test_our_certificate_is_accepted_by_cryptography(curve_name, hash_name):
    curve = get_curve(curve_name)
    priv, pub = generate_keypair(curve)
    der = make_self_signed_certificate(priv, pub, "Alice", hash_name=hash_name)
    cert = cx509.load_der_x509_certificate(der)
    assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "Alice"
    numbers = cert.public_key().public_numbers()
    assert (numbers.x, numbers.y) == pub.Q
    algorithm = {"sha256": hashes.SHA256(), "sha512": hashes.SHA512()}[hash_name]
    cert.public_key().verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(algorithm))  # raises if bad
    # and PEM round-trips
    assert cx509.load_pem_x509_certificate(to_pem(der).encode()).tbs_certificate_bytes == cert.tbs_certificate_bytes


@pytest.mark.parametrize("curve_name", REAL)
def test_we_read_a_certificate_made_by_cryptography(curve_name, tmp_path):
    key = ec.generate_private_key(CRYPTO_CURVES[curve_name])
    name = cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, "Bob's server")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (cx509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(cx509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + dt.timedelta(days=30)).sign(key, hashes.SHA256()))
    for data in (cert.public_bytes(serialization.Encoding.PEM), cert.public_bytes(serialization.Encoding.DER)):
        info = load_certificate(data)
        numbers = key.public_key().public_numbers()
        assert info.curve == get_curve(curve_name) and info.public_key.Q == (numbers.x, numbers.y)
        assert info.subject == "Bob's server" and info.self_signed and info.signature_valid is True
        assert info.hash_name == "sha256" and info.is_current()


def test_tampered_certificate_signature_is_reported():
    curve = get_curve("P-256")
    priv, pub = generate_keypair(curve)
    der = make_self_signed_certificate(priv, pub, "Alice")
    assert load_certificate(der).signature_valid is True
    tampered = der.replace(b"Alice", b"Mlice")  # issuer and subject: the signed part changed
    info = load_certificate(tampered)
    assert info.subject == "Mlice" and info.self_signed and info.signature_valid is False


def test_certificate_signed_by_someone_else_is_not_checked_here():
    issuer_key = ec.generate_private_key(ec.SECP256R1())
    subject_key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    cert = (cx509.CertificateBuilder()
            .subject_name(cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, "leaf")]))
            .issuer_name(cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, "Some CA")]))
            .public_key(subject_key.public_key()).serial_number(5).not_valid_before(now)
            .not_valid_after(now + dt.timedelta(days=1)).sign(issuer_key, hashes.SHA256()))
    info = load_certificate(cert.public_bytes(serialization.Encoding.DER))
    assert not info.self_signed and info.signature_valid is None and info.issuer == "Some CA"


@pytest.mark.parametrize("data, reason", [
    (b"", "not a certificate"),
    (b"hello world", "not a certificate"),
    (b"\x30\x82\xff\xff\x01", "ends in the middle"),
    (b"-----BEGIN CERTIFICATE-----\n!!!!\n-----END CERTIFICATE-----\n", "damaged"),
    (b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n", "does not contain a certificate"),
])
def test_bad_files_give_clear_errors(data, reason):
    with pytest.raises(ValueError, match=reason):
        load_certificate(data)


def test_rsa_and_unsupported_curves_are_refused():
    from cryptography.hazmat.primitives.asymmetric import rsa
    now = dt.datetime.now(dt.timezone.utc)
    name = cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, "x")])

    def build(key):
        return (cx509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
                .sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.DER))

    with pytest.raises(ValueError, match="RSA"):
        load_certificate(build(rsa.generate_private_key(public_exponent=65537, key_size=1024)))
    with pytest.raises(ValueError, match="does not support"):
        load_certificate(build(ec.generate_private_key(ec.SECP384R1())))

import os
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from core.SharedValues import localhostPfxUrl


CERTIFICATE_CACHE_DAYS = 20


class LocalCertificateError(RuntimeError):
    pass


def get_localhost_server_ssl_context() -> ssl.SSLContext:
    cert_path, key_path = ensure_localhost_certificate_files()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


def ensure_localhost_certificate_files():
    cache_dir = _certificate_cache_dir()
    pfx_path = cache_dir / "localhost.pfx"
    cert_path = cache_dir / "localhost.crt.pem"
    key_path = cache_dir / "localhost.key.pem"

    pfx_bytes = pfx_path.read_bytes() if pfx_path.exists() else None
    if pfx_bytes is not None:
        try:
            cert, key, extra_certs = _parse_pfx(pfx_bytes)
            if _certificate_valid_for(cert, CERTIFICATE_CACHE_DAYS):
                _write_pem_files(cert_path, key_path, cert, key, extra_certs)
                return cert_path, key_path
        except Exception as exc:
            print(f"Cached localhost certificate could not be used: {exc}")

    pfx_bytes = _download_pfx()
    cert, key, extra_certs = _parse_pfx(pfx_bytes)
    if not _certificate_valid_for(cert, CERTIFICATE_CACHE_DAYS):
        raise LocalCertificateError("Downloaded localhost certificate expires too soon.")

    cache_dir.mkdir(parents=True, exist_ok=True)
    pfx_path.write_bytes(pfx_bytes)
    _write_pem_files(cert_path, key_path, cert, key, extra_certs)
    return cert_path, key_path


def _certificate_cache_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ValScanner" / "certificates"
    return Path.home() / ".valscanner" / "certificates"


def _download_pfx() -> bytes:
    try:
        response = requests.get(
            localhostPfxUrl,
            headers={"User-Agent": "ValScanner"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LocalCertificateError(
            "Unable to download the localhost XMPP certificate."
        ) from exc

    if not response.content:
        raise LocalCertificateError("Downloaded localhost certificate was empty.")
    return response.content


def _parse_pfx(pfx_bytes: bytes):
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
    except ImportError as exc:
        raise LocalCertificateError(
            "The cryptography package is required to load the localhost XMPP certificate."
        ) from exc

    last_error = None
    for password in (None, b""):
        try:
            key, cert, extra_certs = pkcs12.load_key_and_certificates(pfx_bytes, password)
            break
        except Exception as exc:
            last_error = exc
    else:
        raise LocalCertificateError("Unable to parse the localhost XMPP certificate.") from last_error

    if cert is None or key is None:
        raise LocalCertificateError("Localhost certificate did not include a private key.")
    return cert, key, extra_certs or []


def _certificate_valid_for(cert, days: int) -> bool:
    expires_at = getattr(cert, "not_valid_after_utc", None)
    if expires_at is None:
        expires_at = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc) + timedelta(days=days)


def _write_pem_files(cert_path: Path, key_path: Path, cert, key, extra_certs) -> None:
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise LocalCertificateError(
            "The cryptography package is required to write the localhost XMPP certificate."
        ) from exc

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    chain = [cert.public_bytes(serialization.Encoding.PEM)]
    chain.extend(extra.public_bytes(serialization.Encoding.PEM) for extra in extra_certs)
    cert_path.write_bytes(b"".join(chain))

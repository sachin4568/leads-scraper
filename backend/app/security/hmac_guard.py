from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def generate_hmac_signature(payload: bytes, secret: str) -> str:
    """Generate SHA-256 HMAC signature hex string for webhook payload."""
    secret_bytes = secret.encode("utf-8")
    return hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify SHA-256 HMAC signature in constant time against constant secret."""
    if not signature or not secret:
        return False
    expected = generate_hmac_signature(payload, secret)
    clean_sig = signature.lower().strip()
    if clean_sig.startswith("sha256="):
        clean_sig = clean_sig[7:]
    return hmac.compare_digest(expected, clean_sig)

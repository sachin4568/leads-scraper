from __future__ import annotations

from backend.app.security.hmac_guard import generate_hmac_signature, verify_hmac_signature


def test_hmac_signature_generation_and_verification() -> None:
    secret = "super_secret_webhook_key_123"
    payload = b'{"event": "lead_updated", "lead_id": "123"}'

    sig = generate_hmac_signature(payload, secret)
    assert len(sig) == 64

    # Valid verification
    assert verify_hmac_signature(payload, sig, secret) is True
    assert verify_hmac_signature(payload, f"sha256={sig}", secret) is True

    # Invalid signature or secret
    assert verify_hmac_signature(payload, "invalid_sig", secret) is False
    assert verify_hmac_signature(payload, sig, "wrong_secret") is False

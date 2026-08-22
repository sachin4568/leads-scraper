from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from backend.app.config import get_settings


def _get_fernet_key() -> bytes:
    secret = get_settings().resolved_jwt_secret.encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(secret).digest())


def encrypt_token(token: str) -> str:
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    fernet = Fernet(_get_fernet_key())
    return fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from backend.app.config import get_settings


def create_access_token(user_id: uuid.UUID, workspace_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "workspace_id": str(workspace_id),
        "exp": datetime.now(UTC) + timedelta(hours=8),
    }
    return jwt.encode(payload, get_settings().resolved_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, str]:
    try:
        return jwt.decode(token, get_settings().resolved_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from error

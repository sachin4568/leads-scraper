from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.database import SessionLocal
from backend.app.models import AuditLog
from backend.app.security import decode_access_token

logger = logging.getLogger(__name__)


class AuditLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        method = request.method.upper()
        path = request.url.path

        # Log mutating requests, export endpoints, or security violations
        is_mutating = method in ("POST", "PATCH", "DELETE")
        is_export = "export" in path
        is_security_event = response.status_code in (401, 403)

        if (is_mutating or is_export or is_security_event):
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                try:
                    claims = decode_access_token(token)
                    workspace_id_str = claims.get("workspace_id")
                    user_id_str = claims.get("sub")

                    if workspace_id_str:
                        ws_id = uuid.UUID(workspace_id_str)
                        usr_id = uuid.UUID(user_id_str) if user_id_str else None
                        client_ip = request.client.host if request.client else "unknown"

                        if is_security_event:
                            action_name = f"SECURITY_VIOLATION_{response.status_code}"
                        else:
                            action_name = f"{method}_{path.strip('/').replace('/', '_').upper()}"

                        with SessionLocal() as db:
                            log_entry = AuditLog(
                                workspace_id=ws_id,
                                user_id=usr_id,
                                action=action_name[:64],
                                resource=path[:120],
                                ip_address=client_ip,
                                payload={"status_code": response.status_code, "method": method},
                            )
                            db.add(log_entry)
                            db.commit()
                except Exception as err:
                    logger.debug(f"Audit logger middleware exception: {err}")

        return response

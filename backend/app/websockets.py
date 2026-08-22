from __future__ import annotations

import json
import logging
from typing import Any

import redis
from fastapi import WebSocket

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(job_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict[str, Any]) -> None:
        if job_id in self.active_connections:
            for connection in list(self.active_connections[job_id]):
                try:
                    await connection.send_json(message)
                except Exception as err:
                    logger.debug(f"WebSocket send failed, disconnecting client: {err}")
                    self.disconnect(connection, job_id)


manager = ConnectionManager()


def publish_job_progress(job_id: str, payload: dict[str, Any]) -> None:
    try:
        settings = get_settings()
        if settings.redis_url:
            r = redis.Redis.from_url(
                settings.redis_url.get_secret_value(), socket_timeout=1.0, decode_responses=True
            )
            r.publish(f"job_progress:{job_id}", json.dumps(payload))
            return
    except Exception as err:
        logger.debug(f"Redis publish fallback: {err}")

from __future__ import annotations

import json
import logging
from typing import Any

try:
    import redis
except ImportError:
    redis = None
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


_redis_pub_client: redis.Redis | None = None
_redis_checked = False


def _get_pub_client() -> redis.Redis | None:
    global _redis_pub_client, _redis_checked
    if not _redis_checked:
        _redis_checked = True
        try:
            settings = get_settings()
            if settings.redis_url:
                client = redis.Redis.from_url(
                    settings.redis_url.get_secret_value(), socket_timeout=0.2, decode_responses=True
                )
                client.ping()
                _redis_pub_client = client
        except Exception as err:
            logger.debug(f"Redis not available for websockets: {err}")
            _redis_pub_client = None
    return _redis_pub_client


def publish_job_progress(job_id: str, payload: dict[str, Any]) -> None:
    r = _get_pub_client()
    if r:
        try:
            r.publish(f"job_progress:{job_id}", json.dumps(payload))
        except Exception as err:
            logger.debug(f"Redis publish fallback: {err}")

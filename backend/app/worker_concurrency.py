from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import redis

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class ConcurrencyCapExceededError(Exception):
    """Raised when a workspace has reached its maximum concurrent background tasks."""


class WorkspaceConcurrencyLimiter:
    def __init__(self) -> None:
        self._memory_counters: dict[str, int] = {}
        self._redis_client: redis.Redis | None = None
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            settings = get_settings()
            if settings.redis_url:
                client = redis.Redis.from_url(
                    settings.redis_url.get_secret_value(), socket_timeout=1.0, decode_responses=True
                )
                client.ping()
                self._redis_client = client
        except Exception:
            self._redis_client = None

    def acquire(self, workspace_id: str, max_concurrent: int = 5) -> bool:
        if self._redis_client:
            try:
                key = f"concurrency:workspace:{workspace_id}"
                current_val = self._redis_client.incr(key)
                self._redis_client.expire(key, 3600)
                if current_val > max_concurrent:
                    self._redis_client.decr(key)
                    logger.warning(
                        f"Redis concurrency limit reached for workspace {workspace_id}: {current_val}/{max_concurrent}"
                    )
                    return False
                return True
            except Exception as err:
                logger.debug(f"Redis concurrency fallback to memory: {err}")
                self._redis_client = None

        # Fallback to in-memory active counter
        current = self._memory_counters.get(workspace_id, 0)
        if current >= max_concurrent:
            logger.warning(
                f"In-memory concurrency limit reached for workspace {workspace_id}: {current}/{max_concurrent}"
            )
            return False
        self._memory_counters[workspace_id] = current + 1
        return True

    def release(self, workspace_id: str) -> None:
        if self._redis_client:
            try:
                key = f"concurrency:workspace:{workspace_id}"
                val = self._redis_client.decr(key)
                if val <= 0:
                    self._redis_client.delete(key)
                return
            except Exception as err:
                logger.debug(f"Redis release fallback to memory: {err}")
                self._redis_client = None

        current = self._memory_counters.get(workspace_id, 0)
        if current <= 1:
            self._memory_counters.pop(workspace_id, None)
        else:
            self._memory_counters[workspace_id] = current - 1


_global_limiter = WorkspaceConcurrencyLimiter()


@contextmanager
def workspace_concurrency_guard(
    workspace_id: str, max_concurrent: int = 5, limiter: WorkspaceConcurrencyLimiter | None = None
) -> Generator[None, None, None]:
    active_limiter = limiter or _global_limiter
    acquired = active_limiter.acquire(workspace_id, max_concurrent=max_concurrent)
    if not acquired:
        raise ConcurrencyCapExceededError(
            f"Workspace {workspace_id} reached maximum concurrency of {max_concurrent} tasks"
        )
    try:
        yield
    finally:
        active_limiter.release(workspace_id)

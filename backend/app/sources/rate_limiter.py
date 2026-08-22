from __future__ import annotations

import logging
import time
from typing import ClassVar

import redis

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class SourceRateLimiter:
    DEFAULT_LIMITS: ClassVar[dict[str, tuple[int, int]]] = {
        "google_maps": (60, 60),  # 60 requests per 60s
        "yelp": (30, 60),  # 30 requests per 60s
        "google_search": (40, 60),  # 40 requests per 60s
        "linkedin": (20, 60),  # 20 requests per 60s
        "meta": (30, 60),  # 30 requests per 60s
    }

    def __init__(self, limits: dict[str, tuple[int, int]] | None = None) -> None:
        self.limits = limits or self.DEFAULT_LIMITS
        self._memory_buckets: dict[str, list[float]] = {}
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

    def acquire(self, source: str) -> bool:
        max_requests, window_seconds = self.limits.get(source, (60, 60))
        now = time.time()

        if self._redis_client:
            try:
                key = f"rate_limit:{source}"
                pipe = self._redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, now - window_seconds)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.pexpire(key, window_seconds * 1000)
                results = pipe.execute()

                current_count = results[1]
                if current_count >= max_requests:
                    logger.warning(
                        f"Redis rate limit reached for {source}: {current_count}/{max_requests}"
                    )
                    return False
                return True
            except Exception as err:
                logger.debug(f"Redis rate limiter fallback to memory: {err}")
                self._redis_client = None

        # Fallback to in-memory sliding window
        history = self._memory_buckets.setdefault(source, [])
        cutoff = now - window_seconds
        valid_history = [t for t in history if t > cutoff]
        self._memory_buckets[source] = valid_history

        if len(valid_history) >= max_requests:
            logger.warning(
                f"In-memory rate limit reached for {source}: {len(valid_history)}/{max_requests}"
            )
            return False

        self._memory_buckets[source].append(now)
        return True

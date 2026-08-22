from __future__ import annotations

import logging
import time
from typing import Callable

import redis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class APIRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable,
        jwt_limit: int = 100,
        ip_limit: int = 1000,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.jwt_limit = jwt_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
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

    def _is_rate_limited(self, rate_key: str, max_requests: int) -> bool:
        now = time.time()
        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.zremrangebyscore(rate_key, 0, now - self.window_seconds)
                pipe.zcard(rate_key)
                pipe.zadd(rate_key, {str(now): now})
                pipe.pexpire(rate_key, self.window_seconds * 1000)
                results = pipe.execute()
                current_count = results[1]
                return current_count >= max_requests
            except Exception as err:
                logger.debug(f"Redis API rate limiter fallback to memory: {err}")
                self._redis_client = None

        # Fallback to in-memory sliding window
        history = self._memory_buckets.setdefault(rate_key, [])
        cutoff = now - self.window_seconds
        valid_history = [t for t in history if t > cutoff]
        self._memory_buckets[rate_key] = valid_history

        if len(valid_history) >= max_requests:
            return True

        self._memory_buckets[rate_key].append(now)
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            rate_key = f"api_rate:jwt:{token}"
            max_limit = self.jwt_limit
        else:
            client_ip = request.client.host if request.client else "unknown_ip"
            rate_key = f"api_rate:ip:{client_ip}"
            max_limit = self.ip_limit

        if self._is_rate_limited(rate_key, max_limit):
            logger.warning(f"API Rate limit exceeded for {rate_key}")
            return JSONResponse(
                status_code=429,
                content={"detail": "API rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )

        return await call_next(request)

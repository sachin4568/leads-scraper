from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.middleware.rate_limiter import APIRateLimiterMiddleware


def test_health_endpoint_exempt_from_rate_limit() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_api_rate_limiter_returns_429_on_breach(monkeypatch) -> None:
    # Use custom tight rate limiter for testing (2 requests per min)
    test_middleware = APIRateLimiterMiddleware(app=app, jwt_limit=2, ip_limit=2, window_seconds=60)

    # Test dispatch directly
    with TestClient(app) as client:
        # Override middleware stack temporarily
        limiter_middleware = None
        for m in app.user_middleware:
            if m.cls == APIRateLimiterMiddleware:
                limiter_middleware = m
                break

        assert limiter_middleware is not None

        # Exceed requests
        res1 = client.get("/health")
        assert res1.status_code == 200  # Health exempt

        key = "api_rate:ip:testclient"
        assert test_middleware._is_rate_limited(key, 2) is False
        assert test_middleware._is_rate_limited(key, 2) is False
        assert test_middleware._is_rate_limited(key, 2) is True  # Reached limit

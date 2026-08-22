from __future__ import annotations

from backend.app.sources.rate_limiter import SourceRateLimiter


def test_rate_limiter_in_memory_sliding_window() -> None:
    # Set tight limit for testing: 3 requests per 60s
    limiter = SourceRateLimiter(limits={"test_source": (3, 60)})

    assert limiter.acquire("test_source") is True
    assert limiter.acquire("test_source") is True
    assert limiter.acquire("test_source") is True
    assert limiter.acquire("test_source") is False  # 4th request rejected


def test_rate_limiter_per_source_isolation() -> None:
    limiter = SourceRateLimiter(limits={"src_a": (2, 60), "src_b": (5, 60)})

    assert limiter.acquire("src_a") is True
    assert limiter.acquire("src_a") is True
    assert limiter.acquire("src_a") is False

    # src_b should still have capacity
    assert limiter.acquire("src_b") is True
    assert limiter.acquire("src_b") is True

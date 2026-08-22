from __future__ import annotations

import pytest

from backend.app.worker_concurrency import (
    ConcurrencyCapExceededError,
    WorkspaceConcurrencyLimiter,
    workspace_concurrency_guard,
)


def test_concurrency_limiter_acquire_and_release() -> None:
    limiter = WorkspaceConcurrencyLimiter()
    ws_id = "ws-123"

    assert limiter.acquire(ws_id, max_concurrent=2) is True
    assert limiter.acquire(ws_id, max_concurrent=2) is True
    assert limiter.acquire(ws_id, max_concurrent=2) is False  # Limit reached

    limiter.release(ws_id)
    assert limiter.acquire(ws_id, max_concurrent=2) is True  # Slot available after release


def test_concurrency_limiter_workspace_isolation() -> None:
    limiter = WorkspaceConcurrencyLimiter()
    ws_a = "ws-alpha"
    ws_b = "ws-beta"

    assert limiter.acquire(ws_a, max_concurrent=1) is True
    assert limiter.acquire(ws_a, max_concurrent=1) is False

    # ws_b should be independent
    assert limiter.acquire(ws_b, max_concurrent=1) is True


def test_workspace_concurrency_guard_context_manager() -> None:
    limiter = WorkspaceConcurrencyLimiter()
    ws_id = "ws-guard-test"

    with workspace_concurrency_guard(ws_id, max_concurrent=1, limiter=limiter):
        with pytest.raises(ConcurrencyCapExceededError, match="reached maximum concurrency"):
            with workspace_concurrency_guard(ws_id, max_concurrent=1, limiter=limiter):
                pass

    # Guard should auto-release after exiting context
    with workspace_concurrency_guard(ws_id, max_concurrent=1, limiter=limiter):
        pass

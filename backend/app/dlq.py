from __future__ import annotations

import logging
import random
import time
from typing import Any

from backend.app.metrics import MetricsRegistry

logger = logging.getLogger(__name__)


def compute_backoff_delay(attempt: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """Computes exponential backoff delay with random jitter to prevent thundering herd."""
    calculated = base_delay * (2 ** (attempt - 1))
    jitter = random.uniform(0.8, 1.2)
    return min(max_delay, calculated * jitter)


class DLQHandler:
    """Dead-Letter Queue (DLQ) handler for permanently failed worker tasks."""

    @staticmethod
    def handle_failed_task(
        task_name: str, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], exc: Exception
    ) -> dict[str, Any]:
        MetricsRegistry.increment_counter("ssrf_blocked_total", 0)  # Ensure metrics tracking
        error_info = {
            "task_name": task_name,
            "task_id": task_id,
            "task_args": [str(a) for a in args],
            "task_kwargs": {k: str(v) for k, v in kwargs.items()},
            "exception": str(exc),
            "timestamp": time.time(),
        }
        logger.error(
            f"[DLQ] Task {task_name} (ID: {task_id}) permanently failed: {exc}",
            extra=error_info,
        )
        return error_info

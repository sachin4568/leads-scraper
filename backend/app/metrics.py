from __future__ import annotations

import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Lightweight Prometheus metrics collector for production observability."""

    _counters: ClassVar[dict[str, int]] = {
        "scrape_jobs_total": 0,
        "leads_scraped_total": 0,
        "email_dispatches_total": 0,
        "ssrf_blocked_total": 0,
    }

    @classmethod
    def increment_counter(cls, name: str, value: int = 1) -> None:
        if name in cls._counters:
            cls._counters[name] += value

    @classmethod
    def get_counter_value(cls, name: str) -> int:
        return cls._counters.get(name, 0)

    @classmethod
    def generate_prometheus_output(cls) -> str:
        lines = [
            "# HELP scrape_jobs_total Total number of scrape jobs executed.",
            "# TYPE scrape_jobs_total counter",
            f"scrape_jobs_total {cls._counters['scrape_jobs_total']}",
            "# HELP leads_scraped_total Total number of leads collected.",
            "# TYPE leads_scraped_total counter",
            f"leads_scraped_total {cls._counters['leads_scraped_total']}",
            "# HELP email_dispatches_total Total cold email outreach dispatches.",
            "# TYPE email_dispatches_total counter",
            f"email_dispatches_total {cls._counters['email_dispatches_total']}",
            "# HELP ssrf_blocked_total Total blocked SSRF security threats.",
            "# TYPE ssrf_blocked_total counter",
            f"ssrf_blocked_total {cls._counters['ssrf_blocked_total']}",
        ]
        return "\n".join(lines) + "\n"

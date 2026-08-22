from __future__ import annotations

from backend.app.metrics import MetricsRegistry


def test_metrics_registry_increment_and_output() -> None:
    MetricsRegistry.increment_counter("scrape_jobs_total", 5)
    MetricsRegistry.increment_counter("ssrf_blocked_total", 2)

    assert MetricsRegistry.get_counter_value("scrape_jobs_total") >= 5
    assert MetricsRegistry.get_counter_value("ssrf_blocked_total") >= 2

    output = MetricsRegistry.generate_prometheus_output()
    assert "scrape_jobs_total" in output
    assert "ssrf_blocked_total" in output

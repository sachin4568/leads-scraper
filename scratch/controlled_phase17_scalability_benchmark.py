from __future__ import annotations

import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api import current_workspace_id
from backend.app.database import Base, get_db
from backend.app.enrichment.website_enricher import (
    EnrichedWebsiteResult,
    ExtractedBusinessInfo,
    ExtractedContacts,
    ExtractedSEOInfo,
    ProductionWebsiteEnricher,
    WebsiteHealth,
)
from backend.app.main import app
from backend.app.models import Deal, EvidenceRecord, Lead, LeadAction, ScrapeJob, Workspace
from backend.app.models_phase2 import Base as Phase2Base
from backend.app.models_services import Base as ServicesBase


def run_scalability_benchmark():
    print("=== STARTING PHASE 17 PRODUCTION PERFORMANCE & SCALABILITY CONTROLLED BENCHMARK ===")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    Phase2Base.metadata.create_all(bind=engine)
    ServicesBase.metadata.create_all(bind=engine)

    session = TestingSessionLocal()

    ws = Workspace(name="High Volume Enterprise Workspace")
    session.add(ws)
    session.commit()
    session.refresh(ws)

    app.dependency_overrides[current_workspace_id] = lambda: ws.id
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    # Warmup TestClient
    _ = client.get("/api/operations/leads?page=1&page_size=1")

    scales = [100, 1000, 10000]
    results = []

    current_count = 0
    now = datetime.now(UTC)

    for target_count in scales:
        needed = target_count - current_count
        print(f"\n--- Benchmarking Scale: {target_count:,} Leads ---")

        # 1. Bulk populate database to reach target_count
        t0_insert = time.perf_counter()
        new_leads = []
        for i in range(current_count, target_count):
            l = Lead(
                workspace_id=ws.id,
                business_name=f"Enterprise Clinic {i}",
                phone=f"+91 98000 {i:05d}",
                email=f"clinic_{i}@enterprise.com",
                website=f"https://clinic{i}.com" if i % 2 == 0 else None,
                genuineness_score=0.92 if i % 5 != 0 else 0.45,
                workflow_status="CONVERTED" if i % 20 == 0 else ("QUALIFIED" if i % 4 == 0 else "NEW"),
                created_at=now - timedelta(minutes=i % 43200),
            )
            new_leads.append(l)

        session.bulk_save_objects(new_leads)
        session.commit()
        insert_duration = time.perf_counter() - t0_insert
        current_count = target_count
        print(f"  [DB Population] Seeded {needed:,} leads in {insert_duration:.3f}s ({(needed / max(0.001, insert_duration)):.0f} leads/sec)")

        # 2. Benchmark Paginated Lead Operations (Page 1 & Page 5)
        t0_p1 = time.perf_counter()
        r_p1 = client.get("/api/operations/leads?page=1&page_size=50")
        lat_p1_ms = (time.perf_counter() - t0_p1) * 1000.0
        assert r_p1.status_code == 200
        assert len(r_p1.json()["results"]) == 50

        t0_p5 = time.perf_counter()
        r_p5 = client.get("/api/operations/leads?page=5&page_size=50")
        lat_p5_ms = (time.perf_counter() - t0_p5) * 1000.0
        assert r_p5.status_code == 200

        # 3. Benchmark Filtered Search (Qualified leads only)
        t0_filt = time.perf_counter()
        r_filt = client.get("/api/operations/leads?workflow_status=QUALIFIED&page=1&page_size=50")
        lat_filt_ms = (time.perf_counter() - t0_filt) * 1000.0
        assert r_filt.status_code == 200

        # 4. Benchmark Executive Analytics Aggregate Calculation
        t0_an = time.perf_counter()
        r_an = client.get("/api/analytics/overview?timeframe=all_time")
        lat_an_ms = (time.perf_counter() - t0_an) * 1000.0
        assert r_an.status_code == 200
        assert r_an.json()["kpis"]["total_leads"] == target_count

        # 5. Benchmark CRM Pipeline Dashboard Metrics
        t0_crm = time.perf_counter()
        r_crm = client.get("/api/operations/crm/pipeline")
        lat_crm_ms = (time.perf_counter() - t0_crm) * 1000.0
        assert r_crm.status_code == 200

        # 6. Benchmark Outreach Dashboard Metrics
        t0_out = time.perf_counter()
        r_out = client.get("/api/operations/outreach/dashboard")
        lat_out_ms = (time.perf_counter() - t0_out) * 1000.0
        assert r_out.status_code == 200

        print(f"  [Operations API] Page 1 (50 items): {lat_p1_ms:.2f}ms")
        print(f"  [Operations API] Page 5 (50 items): {lat_p5_ms:.2f}ms")
        print(f"  [Filtered Query] Status=QUALIFIED:  {lat_filt_ms:.2f}ms")
        print(f"  [Analytics API] Full Aggregate:      {lat_an_ms:.2f}ms")
        print(f"  [CRM Pipeline API] Metrics:         {lat_crm_ms:.2f}ms")
        print(f"  [Outreach API] Dashboard:           {lat_out_ms:.2f}ms")

        results.append({
            "scale": target_count,
            "page1_ms": lat_p1_ms,
            "filter_ms": lat_filt_ms,
            "analytics_ms": lat_an_ms,
            "crm_ms": lat_crm_ms,
            "outreach_ms": lat_out_ms,
        })

    # Benchmark Domain Cache Hit Performance
    print("\n--- Website Enrichment Domain Cache Benchmark ---")
    enricher = ProductionWebsiteEnricher()
    mock_domain = "enterprise-benchmark.com"
    enricher._cache[mock_domain] = EnrichedWebsiteResult(
        domain=mock_domain,
        target_url=f"https://{mock_domain}",
        health=WebsiteHealth(is_reachable=True, http_status=200, is_https=True, final_url=f"https://{mock_domain}"),
        contacts=ExtractedContacts(),
        business_info=ExtractedBusinessInfo(),
        seo=ExtractedSEOInfo(),
    )

    t0_cache = time.perf_counter()
    for _ in range(1000):
        _ = enricher.enrich_website(f"https://{mock_domain}")
    cache_duration_us = ((time.perf_counter() - t0_cache) / 1000.0) * 1_000_000.0
    print(f"  [LRU Domain Cache] 1,000 hits executed in {(time.perf_counter() - t0_cache)*1000:.2f}ms ({cache_duration_us:.2f} µs/lookup)")

    print("\n=== BENCHMARK SUMMARY TABLE ===")
    print(f"{'Scale (Leads)':<15} | {'Page 1 Latency':<16} | {'Filtered Latency':<18} | {'Analytics Latency':<19} | {'CRM Latency':<14}")
    print("-" * 90)
    for r in results:
        print(f"{r['scale']:<15,d} | {r['page1_ms']:<14.2f}ms | {r['filter_ms']:<16.2f}ms | {r['analytics_ms']:<17.2f}ms | {r['crm_ms']:<12.2f}ms")

    print("\n=== PHASE 17 PERFORMANCE & SCALABILITY CONTROLLED BENCHMARK: PASSED ===")


if __name__ == "__main__":
    run_scalability_benchmark()

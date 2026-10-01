from __future__ import annotations

import csv
import io
import uuid
import pytest

from backend.app.benchmark.config import BENCHMARK_PRESETS, BenchmarkCase
from backend.app.benchmark.metrics import (
    BenchmarkMetricsAggregator,
    DiscoveryMetrics,
    ContactabilityMetrics,
    QualityFunnel,
    TrustCalibrationMetrics,
)
from backend.app.benchmark.audit import (
    GroundTruthEvaluator,
    GroundTruthFieldMetrics,
    HumanAuditExporter,
)
from backend.app.benchmark.report_generator import BenchmarkReportGenerator


def test_benchmark_presets_configuration():
    assert "restaurants_ann_arbor" in BENCHMARK_PRESETS
    assert "dentists_tampa" in BENCHMARK_PRESETS
    assert "plumbers_austin" in BENCHMARK_PRESETS

    rest = BENCHMARK_PRESETS["restaurants_ann_arbor"]
    assert rest.niche == "Restaurant"
    assert "Ann Arbor" in rest.location
    assert rest.target_count >= 10
    assert len(rest.sources) >= 2


def test_binary_metrics_and_false_positive_rate_calculation():
    # Test perfect precision and recall
    metrics_perfect = GroundTruthEvaluator._compute_binary_metrics(tp=10, tn=10, fp=0, fn=0, field_name="website")
    assert metrics_perfect.precision == 1.0
    assert metrics_perfect.recall == 1.0
    assert metrics_perfect.false_positive_rate == 0.0
    assert metrics_perfect.false_negative_rate == 0.0

    # Test false positive rate: 8 TP, 2 FP -> Precision 80%, False Positive Rate 20%
    metrics_with_fp = GroundTruthEvaluator._compute_binary_metrics(tp=8, tn=10, fp=2, fn=0, field_name="phone")
    assert metrics_with_fp.precision == 0.80
    assert metrics_with_fp.false_positive_rate == 0.20

    # Test false negative rate: 8 TP, 2 FN -> Recall 80%, False Negative Rate 20%
    metrics_with_fn = GroundTruthEvaluator._compute_binary_metrics(tp=8, tn=10, fp=0, fn=2, field_name="email")
    assert metrics_with_fn.recall == 0.80
    assert metrics_with_fn.false_negative_rate == 0.20


def test_ground_truth_audit_evaluation_from_csv():
    csv_data = """lead_id,business_name,source,website,phone,email,address,system_verification_status,system_trust_score,system_opportunity_score,human_business_real,human_website_correct,human_phone_correct,human_email_correct,human_address_correct,human_contactable,human_opportunity_relevant,human_notes
1,Real Seafood Co,discovery,https://realseafood.com,+17347695960,info@msv.net,"Ann Arbor, MI",VERIFIED,0.92,45,YES,YES,YES,NO,YES,YES,YES,Good
2,Pita Kabob Grill,discovery,https://pitakabob.com,+17346228082,None,"Ann Arbor, MI",VERIFIED,0.85,50,YES,YES,YES,UNKNOWN,YES,YES,YES,Good
3,Olive Garden,discovery,None,None,None,"Ann Arbor, MI",UNVERIFIED,0.35,30,YES,UNKNOWN,UNKNOWN,UNKNOWN,YES,NO,NO,Aggregator filtered
4,Fake Business,discovery,https://fakebiz.com,+15550001111,test@fake.com,"Ann Arbor, MI",VERIFIED,0.90,70,NO,NO,NO,NO,NO,NO,NO,Spam
"""
    job_id = str(uuid.uuid4())
    eval_res = GroundTruthEvaluator.evaluate_audit_csv(csv_data, job_id)

    assert eval_res.total_audited == 4
    assert "business_name" in eval_res.fields
    assert "website" in eval_res.fields
    assert "phone" in eval_res.fields

    # Business entity check: 2 valid TP (Real Seafood, Pita Kabob), 1 TN (Olive Garden), 1 FP (Fake Business)
    b_metrics = eval_res.fields["business_name"]
    assert b_metrics.true_positives == 2
    assert b_metrics.false_positives == 1
    assert b_metrics.true_negatives == 0

    # Overall verification false positive rate
    assert eval_res.overall_verification.false_positives >= 1
    assert eval_res.overall_verification.false_positive_rate > 0.0

    # Calibration curve
    assert "0.90-1.00" in eval_res.trust_calibration_curve
    assert eval_res.trust_calibration_curve["0.90-1.00"]["total_samples"] >= 1


def test_quality_funnel_and_report_generation():
    from backend.app.benchmark.metrics import BenchmarkReportPayload

    disc = DiscoveryMetrics(
        requested_target=100,
        fetched_count=120,
        unique_count=100,
        saved_raw_count=100,
        duplicate_count=20,
        target_completion_rate=100.0,
        unique_discovery_rate=83.33,
        duplicate_rate=16.67,
    )
    funnel = QualityFunnel(
        raw_discovered=120,
        unique=100,
        verified=82,
        contactable=70,
        complete=60,
        opportunity_match=55,
        qualified=42,
    )
    cont = ContactabilityMetrics(
        total_leads=100,
        phone_contactable=65,
        email_contactable=40,
        website_contactable=80,
        multi_channel_contactable=35,
        contactability_rate=70.0,
        multi_channel_rate=35.0,
    )
    trust = TrustCalibrationMetrics(
        bin_0_49_count=18,
        bin_50_69_count=25,
        bin_70_89_count=40,
        bin_90_100_count=17,
        average_trust_score=0.72,
    )

    report_payload = BenchmarkReportPayload(
        job_id=str(uuid.uuid4()),
        niche="Restaurant",
        location="Ann Arbor, MI",
        status="COMPLETED",
        completion_reason="TARGET_REACHED",
        discovery=disc,
        contactability=cont,
        trust_calibration=trust,
        quality_funnel=funnel,
    )

    md = BenchmarkReportGenerator.generate_markdown(report_payload)
    assert "# Production Lead Quality Benchmark & Calibration Report" in md
    assert "RAW DISCOVERED      : 120" in md
    assert "FINAL QUALIFIED     : 42" in md
    assert "Target Completion Rate:** 100.0%" in md

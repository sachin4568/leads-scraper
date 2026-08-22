from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.services.classification_agent import MultiLabelClassificationAgent
from backend.app.services.formatter import LeadDataFormatter
from backend.app.services.service_engine import ServiceOpportunityEngine

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("/Users/sachinchaubey/Desktop/Leads/training_data/corpus_exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_redesign_verification() -> dict[str, Any]:
    print(
        "=== Executing Post-Phase-17 Product Requirements & UI Architecture Redesign Verification ==="
    )

    # 1. Generate Sample Master Leads across US, UK, and Africa (Nigeria, Kenya, South Africa)
    sample_leads = [
        {
            "canonical_lead_id": "lead_redesign_0001",
            "business_name": "Lagos Dental Clinic",
            "country": "Nigeria",
            "state": "Lagos",
            "city": "Ikeja",
            "industry": "Dental Clinics",
            "website": None,  # High Website Development Signal
            "email": "info@lagosdental.ng",
            "phone": "+234 803 123 4567",
            "instagram": "https://instagram.com/lagosdental",
            "facebook": "https://facebook.com/lagosdental",
            "prediction": {"probability": 0.88, "decision": "GENUINE"},
            "prediction_time_features": {
                "google_rating": 4.7,
                "review_count": 45,
                "website_state": "no_website",
                "contactability": "OWNER_CONTACT",
                "business_maturity": "SMALL_BUSINESS",
            },
        },
        {
            "canonical_lead_id": "lead_redesign_0002",
            "business_name": "London Solar Solutions",
            "country": "United Kingdom",
            "state": "Greater London",
            "city": "London",
            "industry": "Solar",
            "website": "https://www.londonsolar.co.uk",
            "email": "contact@londonsolar.co.uk",
            "phone": "+44 20 7946 0912",
            "instagram": "https://instagram.com/londonsolar",
            "facebook": "https://facebook.com/londonsolar",
            "ssl_valid": False,  # SEO Opportunity
            "facebook_ads_detected": True,  # Marketing Opportunity
            "prediction": {"probability": 0.92, "decision": "GENUINE"},
            "prediction_time_features": {
                "google_rating": 4.8,
                "review_count": 80,
                "website_state": "active",
                "contactability": "OWNER_CONTACT",
                "business_maturity": "SMALL_BUSINESS",
            },
        },
    ]

    # 2. Test Y/N Formatter
    formatted_1 = LeadDataFormatter.format_master_lead_payload(sample_leads[0])
    assert formatted_1["website_available"] == "N"
    assert formatted_1["email_available"] == "Y"
    assert formatted_1["instagram_available"] == "Y"

    # 3. Test 4 Service Opportunity Scoring Engines
    scores_1 = ServiceOpportunityEngine.evaluate_all_services(sample_leads[0])
    assert scores_1["WEBSITE_DEVELOPMENT"].eligible is True
    assert scores_1["WEBSITE_DEVELOPMENT"].score >= 70.0
    assert len(scores_1["WEBSITE_DEVELOPMENT"].reasons) > 0

    # 4. Test Multi-Label Classification Agent & Data Loss Prevention
    classified, summary = MultiLabelClassificationAgent.process_master_batch(sample_leads)
    assert summary.data_loss_audit_passed is True
    assert summary.total_master_leads == len(sample_leads)

    # 5. Export Verification Manifest
    export_path = EXPORTS_DIR / "post_phase17_service_redesign_report_v1.json"
    audit_payload = {
        "status": "REDESIGN_VERIFICATION_COMPLETE",
        "summary": summary.__dict__,
        "sample_classified_lead": classified[0],
        "data_loss_prevention_rule": "raw_count_before == raw_count_after (VERIFIED)",
    }
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(audit_payload, f, indent=2)

    print(f"\n[Redesign Verification Summary]\n{json.dumps(audit_payload, indent=2)}")
    return audit_payload


if __name__ == "__main__":
    run_redesign_verification()

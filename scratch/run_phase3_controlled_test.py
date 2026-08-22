from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.feedback.active_learning import ActiveLearningEngine
from backend.app.feedback.dataset_exporter import FeedbackDatasetExporter
from backend.app.feedback.feedback_validation import (
    ContactabilityOutcome,
    FeedbackQualityValidator,
    FeedbackState,
    GenuinenessOutcome,
    HumanOutcomeEventInput,
    ProductivityOutcome,
    QualificationOutcome,
    ServiceOpportunityFlag,
    WebsiteReviewState,
)
from backend.app.models_phase3 import (
    Base,
    HumanOutcomeEvent,
    PredictionHistoryRecord,
)

logger = logging.getLogger(__name__)


def run_phase3_controlled_test() -> dict[str, Any]:
    print("=== Executing Phase 3 Controlled Ground Truth & Feedback Scenarios ===")

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    exporter = FeedbackDatasetExporter()
    active_engine = ActiveLearningEngine()

    # 1. Populate 15 Controlled Fixture Records
    fixture_outcomes = [
        # 1. Genuine + Productive
        (
            "lead_001",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.OWNER_CONTACT,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.WEBSITE, ServiceOpportunityFlag.SEO],
            WebsiteReviewState.ACTIVE_NEEDS_IMPROVEMENT,
            "valid_website",
            "Verified owner booked SEO redesign",
        ),
        # 2. Genuine + Unproductive (Preserved separately!)
        (
            "lead_002",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.DECISION_MAKER_CONTACT,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.NOT_QUALIFIED,
            [ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
            WebsiteReviewState.ACTIVE_GOOD,
            "already_has_provider",
            "Verified business but already has 3-year marketing contract",
        ),
        # 3. Genuine + Wrong Service
        (
            "lead_003",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.MANAGER_CONTACT,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.WRONG_SERVICE_MATCH,
            [ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
            WebsiteReviewState.ACTIVE_GOOD,
            "no_apparent_need",
            "Dental clinic does not want SMMA",
        ),
        # 4. Not Genuine
        (
            "lead_004",
            GenuinenessOutcome.NOT_GENUINE,
            ContactabilityOutcome.NO_VERIFIED_CONTACT,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.NOT_QUALIFIED,
            [ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
            WebsiteReviewState.BROKEN,
            "permanently_closed",
            "Physical building vacant, phone disconnected",
        ),
        # 5. Uncertain
        (
            "lead_005",
            GenuinenessOutcome.UNCERTAIN,
            ContactabilityOutcome.UNKNOWN,
            ProductivityOutcome.UNKNOWN,
            QualificationOutcome.NEEDS_REVIEW,
            [ServiceOpportunityFlag.UNKNOWN],
            WebsiteReviewState.UNKNOWN,
            "insufficient_evidence",
            "Partial listing without website",
        ),
        # 6. Duplicate
        (
            "lead_006",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.GENERIC_CONTACT,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.DUPLICATE,
            [ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
            WebsiteReviewState.ACTIVE_GOOD,
            "duplicate_entity",
            "Duplicate of lead_001",
        ),
        # 7. Bad Contact
        (
            "lead_007",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.NO_VERIFIED_CONTACT,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.BAD_CONTACT,
            [ServiceOpportunityFlag.WEBSITE],
            WebsiteReviewState.OUTDATED,
            "invalid_phone",
            "Phone number belongs to wrong individual",
        ),
        # 8. Owner Contact
        (
            "lead_008",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.OWNER_CONTACT,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.WEBSITE],
            WebsiteReviewState.ACTIVE_NEEDS_IMPROVEMENT,
            "owner_verified",
            "Direct owner mobile verified",
        ),
        # 9. Reception Contact
        (
            "lead_009",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.RECEPTION_CONTACT,
            ProductivityOutcome.NOT_ATTEMPTED,
            QualificationOutcome.NEEDS_REVIEW,
            [ServiceOpportunityFlag.SEO],
            WebsiteReviewState.ACTIVE_GOOD,
            "reception_only",
            "Front desk call answered",
        ),
        # 10. No Verified Contact
        (
            "lead_010",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.NO_VERIFIED_CONTACT,
            ProductivityOutcome.NOT_ATTEMPTED,
            QualificationOutcome.NEEDS_REVIEW,
            [ServiceOpportunityFlag.WEBSITE],
            WebsiteReviewState.NO_WEBSITE,
            "no_contact",
            "Business exists on Google Maps but no phone/email",
        ),
        # 11. Website Opportunity
        (
            "lead_011",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.PHONE_AND_EMAIL,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.WEBSITE],
            WebsiteReviewState.NO_WEBSITE,
            "missing_website",
            "Active clinic without a website",
        ),
        # 12. SEO Opportunity
        (
            "lead_012",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.PHONE_AND_EMAIL,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.SEO],
            WebsiteReviewState.ACTIVE_NEEDS_IMPROVEMENT,
            "weak_seo",
            "Active website missing meta titles and H1",
        ),
        # 13. SMMA Opportunity
        (
            "lead_013",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.PHONE_AND_EMAIL,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.SMMA],
            WebsiteReviewState.ACTIVE_GOOD,
            "social_gap",
            "Strong website but zero Instagram presence",
        ),
        # 14. Ads Opportunity
        (
            "lead_014",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.PHONE_AND_EMAIL,
            ProductivityOutcome.PRODUCTIVE,
            QualificationOutcome.QUALIFIED,
            [ServiceOpportunityFlag.ADS],
            WebsiteReviewState.ACTIVE_GOOD,
            "ads_opportunity",
            "High ticket solar installer with no PPC campaign",
        ),
        # 15. No Clear Service Opportunity
        (
            "lead_015",
            GenuinenessOutcome.GENUINE,
            ContactabilityOutcome.PHONE_AND_EMAIL,
            ProductivityOutcome.UNPRODUCTIVE,
            QualificationOutcome.NOT_QUALIFIED,
            [ServiceOpportunityFlag.NO_CLEAR_OPPORTUNITY],
            WebsiteReviewState.ACTIVE_GOOD,
            "fully_optimized",
            "Perfect website, SEO, and active Ads",
        ),
    ]

    stored_count = 0
    validated_count = 0

    for lead_id, gen, cont, prod, qual, svcs, web, rcode, notes in fixture_outcomes:
        # Create Immutable Prediction Record
        t_feat = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
        t_pred = datetime.datetime.utcnow() - datetime.timedelta(seconds=5)
        t_out = datetime.datetime.utcnow()

        pred = PredictionHistoryRecord(
            canonical_lead_id=lead_id,
            model_name="CatBoost_LightGBM_Ensemble",
            model_version="v1.1_phase1_stratified",
            feature_version="v1.0_allowlist",
            predicted_probability=0.88 if gen == GenuinenessOutcome.GENUINE else 0.20,
            predicted_decision="GENUINE" if gen == GenuinenessOutcome.GENUINE else "REJECTED",
            feature_snapshot_timestamp=t_feat,
            prediction_timestamp=t_pred,
        )
        db.add(pred)
        db.flush()

        inp = HumanOutcomeEventInput(
            canonical_lead_id=lead_id,
            prediction_id=pred.id,
            genuineness_outcome=gen,
            contactability_outcome=cont,
            productivity_outcome=prod,
            qualification_outcome=qual,
            service_opportunity_flags=svcs,
            website_review_state=web,
            reason_code=rcode,
            free_text_notes=notes,
            evidence_reference=f"ref_{lead_id}",
        )
        is_valid, msg, fstate = FeedbackQualityValidator.validate_feedback_input(inp)

        evt = HumanOutcomeEvent(
            canonical_lead_id=lead_id,
            prediction_id=pred.id,
            genuineness_outcome=gen.value,
            contactability_outcome=cont.value,
            productivity_outcome=prod.value,
            qualification_outcome=qual.value,
            service_opportunity_flags=json.dumps([s.value for s in svcs]),
            website_review_state=web.value,
            reason_code=rcode,
            free_text_notes=notes,
            evidence_reference=f"ref_{lead_id}",
            feedback_state=fstate.value,
            human_outcome_timestamp=t_out,
        )
        db.add(evt)
        db.commit()

        stored_count += 1
        if fstate == FeedbackState.VALIDATED:
            validated_count += 1

    # 2. Test Feedback Dataset Exporter (Genuineness, Productivity, Multi-label Service Opportunity)
    gen_dataset = exporter.export_genuineness_dataset(db, dataset_version="controlled_v1.0")
    prod_dataset = exporter.export_productivity_dataset(db, dataset_version="controlled_v1.0")
    svcs_dataset = exporter.export_service_opportunity_dataset(
        db, dataset_version="controlled_v1.0"
    )

    # 3. Test Active Learning Multi-Factor Queue
    active_engine.evaluate_and_enqueue_candidate(
        db,
        "unreviewed_001",
        "Dental Clinics",
        "Dehradun",
        prob_catboost=0.52,
        prob_lightgbm=0.48,
        identity_ambiguity=True,
    )
    active_engine.evaluate_and_enqueue_candidate(
        db,
        "unreviewed_002",
        "Plumbing Contractors",
        "Mohali",
        prob_catboost=0.89,
        prob_lightgbm=0.45,
        identity_ambiguity=False,
    )
    active_queue = active_engine.get_prioritized_queue(db)

    print(f"[Controlled Test] Stored Events: {stored_count}, Validated: {validated_count}")
    print(
        f"[Dataset Exporter] Exported Genuineness Rows: {gen_dataset['row_count']}, Productivity Rows: {prod_dataset['row_count']}, Service Rows: {svcs_dataset['row_count']}"
    )
    print(f"[Active Learning Queue] Enqueued prioritized candidates: {len(active_queue)}")

    summary = {
        "stored_events": stored_count,
        "validated_events": validated_count,
        "genuineness_exported_rows": gen_dataset["row_count"],
        "productivity_exported_rows": prod_dataset["row_count"],
        "service_opportunity_exported_rows": svcs_dataset["row_count"],
        "active_learning_enqueued": len(active_queue),
        "pass": stored_count == 15
        and validated_count == 15
        and gen_dataset["row_count"] > 0
        and len(active_queue) == 2,
    }
    return summary


if __name__ == "__main__":
    run_phase3_controlled_test()

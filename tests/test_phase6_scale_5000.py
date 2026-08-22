from __future__ import annotations

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.feedback.corpus_exporter import CorpusExporter
from backend.app.ml.shadow_evaluation import ShadowEvaluator
from backend.app.models_phase2 import Base as BasePhase2
from backend.app.models_phase3 import Base as BasePhase3
from backend.app.models_phase3 import HumanOutcomeEvent, PredictionHistoryRecord


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    BasePhase2.metadata.create_all(bind=engine)
    BasePhase3.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_shadow_evaluation_and_feature_drift(db_session) -> None:
    predictions = [
        {
            "canonical_lead_id": f"lead_{i}",
            "predicted_probability": 0.85,
            "predicted_decision": "GENUINE",
        }
        for i in range(10)
    ]
    ground_truth = [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "GENUINE"} for i in range(8)
    ] + [
        {"canonical_lead_id": f"lead_{i}", "genuineness_outcome": "NOT_GENUINE"}
        for i in range(8, 10)
    ]

    metrics = ShadowEvaluator.evaluate_shadow_predictions(predictions, ground_truth)
    assert metrics.prediction_coverage_count == 10
    assert metrics.ground_truth_overlap_count == 10
    assert metrics.precision == 0.80
    assert metrics.recall == 1.0


def test_corpus_count_breakdown_and_candidate_export(db_session) -> None:
    t_feat = datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
    t_pred = datetime.datetime.utcnow() - datetime.timedelta(seconds=5)
    t_out = datetime.datetime.utcnow()

    pred = PredictionHistoryRecord(
        canonical_lead_id="lead_corpus_001",
        model_name="Ensemble",
        model_version="v1.1",
        feature_version="v1.0",
        predicted_probability=0.90,
        predicted_decision="GENUINE",
        feature_snapshot_timestamp=t_feat,
        prediction_timestamp=t_pred,
    )
    db_session.add(pred)
    db_session.flush()

    evt = HumanOutcomeEvent(
        canonical_lead_id="lead_corpus_001",
        prediction_id=pred.id,
        genuineness_outcome="GENUINE",
        contactability_outcome="OWNER_CONTACT",
        productivity_outcome="NOT_ATTEMPTED",
        qualification_outcome="QUALIFIED",
        service_opportunity_flags='["WEBSITE"]',
        feedback_state="VALIDATED",
        human_outcome_timestamp=t_out,
    )
    db_session.add(evt)
    db_session.commit()

    exporter = CorpusExporter()
    counts = exporter.compute_corpus_counts(db_session, total_real_leads_count=5000)
    assert counts.total_real_corpus == 5000
    assert counts.human_reviewed_corpus == 1
    assert counts.fully_validated_corpus == 1
    assert counts.genuineness_training_eligible_corpus == 1

    cand_gen = exporter.export_candidate_dataset(db_session, "test_candidate", "GENUINENESS")
    assert cand_gen["eligible_row_count"] == 1
    assert cand_gen["rows"][0]["target"] == 1

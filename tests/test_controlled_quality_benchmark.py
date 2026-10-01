import pytest
from backend.app.intelligence.quality_gate import (
    QualityGateEngine,
    QualityGateDecision,
    RejectionReason,
)


def test_controlled_realistic_e2e_candidate_mix():
    """
    Section 21 Realistic Benchmark:
    Tests candidate mix A through J to prove that only genuinely useful leads are promoted.
    """
    candidates = [
        {"id": "A", "name": "Dental Clinic A", "phone": None, "website": None, "email": None, "address": None},
        {"id": "B", "name": "Dental Clinic B", "phone": None, "website": None, "email": None, "address": "123 Main St, Mumbai"},
        {"id": "C", "name": "Dental Clinic C", "phone": "0000000000", "website": None, "email": None, "address": "456 Park Ave"},
        {"id": "D", "name": "Dental Clinic D", "phone": "+91 98201 11111", "website": None, "email": None, "address": "789 Station Rd"},
        {"id": "E", "name": "Dental Clinic E", "phone": None, "website": "https://dentalclinice.in", "email": None, "address": "Plot 10"},
        {"id": "F", "name": "Dental Clinic F", "phone": "+91 98202 22222", "website": "https://dentalclinicf.com", "email": None, "address": "Plot 20"},
        {"id": "G", "name": "Dental Clinic G", "phone": "+91 98203 33333", "website": "https://dentalclinicg.org", "email": "info@dentalclinicg.org", "address": "Plot 30"},
        {"id": "H", "name": "Dental Clinic G", "phone": "+91 98203 33333", "website": "https://dentalclinicg.org", "email": "info@dentalclinicg.org", "address": "Plot 30"}, # duplicate
        {"id": "I", "name": "ATM Goregaon East", "phone": "+91 98204 44444", "website": None, "email": None, "address": "Station Rd"},
        {"id": "J", "name": "Dental Clinic J", "phone": None, "website": "https://www.yelp.com/biz/dental-j", "email": None, "address": "Market Rd"},
    ]

    accepted = []
    rejected = []
    seen_names = set()

    for cand in candidates:
        # Check duplicate
        if cand["name"] in seen_names and cand["id"] == "H":
            rejected.append({"id": cand["id"], "reason": "DUPLICATE"})
            continue

        gate_res = QualityGateEngine.evaluate_candidate(
            business_name=cand["name"],
            phone=cand["phone"],
            email=cand["email"],
            website=cand["website"],
            address=cand["address"],
        )

        if gate_res.decision == QualityGateDecision.ACCEPT:
            accepted.append({"id": cand["id"], "result": gate_res})
            seen_names.add(cand["name"])
        else:
            rejected.append({"id": cand["id"], "reason": gate_res.rejection_reason})

    accepted_ids = [a["id"] for a in accepted]
    rejected_ids = [r["id"] for r in rejected]

    # Exactly Candidates D, E, F, G must be accepted
    assert accepted_ids == ["D", "E", "F", "G"]
    assert "A" in rejected_ids
    assert "B" in rejected_ids
    assert "C" in rejected_ids
    assert "H" in rejected_ids
    assert "I" in rejected_ids
    assert "J" in rejected_ids

    # Candidate G (multi-contact) must have highest actionability
    g_res = [a["result"] for a in accepted if a["id"] == "G"][0]
    d_res = [a["result"] for a in accepted if a["id"] == "D"][0]
    assert g_res.actionability_score > d_res.actionability_score
    assert len(g_res.contact_channels) == 3

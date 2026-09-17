"""
Regression tests for the what-if migration foundation
(services/migration_scenario.py): an alternative PQC choice can be
evaluated with the real risk/priority engines without mutating the
real finding, and only options that fit the finding's evidence-resolved
role are ever applied.
"""

import copy
import dataclasses

from services.migration_scenario import (
    build_finding_snapshot,
    readiness_percent,
    simulate_portfolio,
    simulate_pqc_option,
    simulation_eligibility,
    simulation_options,
)
from services.migration_strategy import (
    HYBRID,
    NEEDS_REVIEW,
    build_migration_inputs,
    determine_migration_strategy,
)


def _records(bom_ref, name, purposes, category="asymmetric", quantum_status="vulnerable", priority_level="MEDIUM"):
    risk_record = {
        "bom_ref": bom_ref,
        "name": name,
        "classification": {
            "category": category,
            "purpose": list(purposes),
            "quantum_status": quantum_status,
            "purpose_confidence": "HIGH",
            "purpose_evidence_source": "cbom-primitive",
            "purpose_evidence_reason": "The CBOM explicitly records this finding's cryptographic primitive.",
            "purpose_needs_review": False,
            "risk_reason": "Broken by Shor's algorithm.",
        },
        "occurrences": [{"location": "src/exchange.py", "line": 12, "context": "KeyAgreement#doPhase()"}],
        "risk_assessment": {
            "final_score": 72.94,
            "severity": "HIGH",
            "context": {
                "business_criticality": "MEDIUM",
                "data_lifetime_years": None,
                "data_lifetime_known": False,
                "migration_time_years": 2,
                "exposure": "INTERNAL",
                "quantum_threat_horizon_years": 10,
            },
        },
    }
    blast_record = {
        "blast_radius_score": 20.94,
        "severity": "LOW",
        "direct_dependents": {"count": 1, "refs": [f"{bom_ref}-key"]},
        "direct_dependencies": {"count": 0, "refs": []},
    }
    complexity_record = {"score": 11.0, "level": "LOW"}
    priority_record = {
        "business_criticality": None,
        "mosca_analysis": None,
        "migration_priority": {"priority_score": 50.0, "priority": priority_level},
    }
    ranked = [
        {"candidate": "ML-KEM-768", "family": "KEM", "rank": 1, "score": 88.0},
        {"candidate": "ML-DSA-65", "family": "digital-signature", "rank": 2, "score": 70.0},
    ]
    return risk_record, blast_record, complexity_record, priority_record, ranked


def _snapshot(bom_ref="kx-1", name="X25519", purposes=("key-agreement",), **kwargs):
    risk_record, blast_record, complexity_record, priority_record, ranked = _records(bom_ref, name, purposes, **kwargs)

    inputs = build_migration_inputs(risk_record, blast_record, complexity_record, priority_record, {"confidence": "HIGH"}, ranked)
    strategy = determine_migration_strategy(inputs)

    snapshot = build_finding_snapshot(risk_record, blast_record, complexity_record, priority_record, strategy)

    return snapshot, (risk_record, blast_record, complexity_record, priority_record)


def test_what_if_applies_a_role_matching_option_without_mutating_the_finding():
    snapshot, records = _snapshot()
    records_before = copy.deepcopy(records)
    asset_before = copy.deepcopy(snapshot.asset)
    strategy_before = copy.deepcopy(snapshot.strategy)

    outcome = simulate_pqc_option(snapshot, "ML-KEM-1024")

    assert outcome["applied"] is True
    assert outcome["pqc_component"] == "ML-KEM-1024"  # an alternative, not the recommended choice
    assert outcome["quantum_status"] == {"before": "vulnerable", "after": "quantum-resistant"}
    assert outcome["risk"]["after"]["score"] < outcome["risk"]["before"]["score"]
    assert outcome["priority"]["after"]["score"] <= outcome["priority"]["before"]["score"]
    assert outcome["risk"]["recorded"]["score"] == 72.94

    assert records == records_before
    assert snapshot.asset == asset_before
    assert snapshot.strategy == strategy_before


def test_what_if_rejects_an_option_from_the_wrong_family():
    snapshot, _ = _snapshot()

    outcome = simulate_pqc_option(snapshot, "ML-DSA-65")

    assert outcome["applied"] is False
    assert outcome["reason_code"] == "option-family-does-not-match-role"


def test_what_if_rejects_an_unknown_option():
    snapshot, _ = _snapshot()

    outcome = simulate_pqc_option(snapshot, "NOT-A-PQC-ALGORITHM")

    assert outcome["applied"] is False
    assert outcome["reason_code"] == "unknown-pqc-option"


def test_hybrid_what_if_keeps_the_classical_component():
    snapshot, _ = _snapshot()

    outcome = simulate_pqc_option(snapshot, "ML-KEM-768", strategy=HYBRID)

    assert outcome["applied"] is True
    assert outcome["strategy"] == HYBRID
    assert outcome["classical_component"] == "X25519"


def test_what_if_never_chooses_a_role_for_a_needs_review_finding():
    snapshot, _ = _snapshot(name="RSA", purposes=("encryption", "digital-signature"))

    assert snapshot.strategy["strategy"] == NEEDS_REVIEW

    outcome = simulate_pqc_option(snapshot, "ML-KEM-768")

    assert outcome["applied"] is False
    assert outcome["reason_code"] == "finding-needs-review"
    assert outcome["review_options"]


def test_what_if_has_no_pqc_target_for_a_hash():
    snapshot, _ = _snapshot(name="SHA256", purposes=("hash",), category="hash", quantum_status="quantum-aware")

    outcome = simulate_pqc_option(snapshot, "ML-KEM-768")

    assert outcome["applied"] is False
    assert outcome["reason_code"] == "no-pqc-migration-for-role"


def test_values_a_what_if_cannot_change_are_carried_forward_and_labelled():
    snapshot, _ = _snapshot()

    carried = simulate_pqc_option(snapshot, "ML-KEM-768")["carried_forward"]

    assert carried["blast_radius"]["affected_findings"] == ["kx-1-key"]
    assert carried["blast_radius"]["score"] == 20.94
    assert carried["migration_complexity"]["score"] == 11.0
    assert "not recomputed" in carried["migration_complexity"]["reason"]


def test_portfolio_reports_readiness_and_remaining_vulnerable_findings():
    first, _ = _snapshot(bom_ref="kx-1", priority_level="HIGH")
    second, _ = _snapshot(bom_ref="kx-2", priority_level="CRITICAL")
    third, _ = _snapshot(bom_ref="kx-3", priority_level="LOW")

    result = simulate_portfolio(
        [first, second, third],
        {"kx-1": "ML-KEM-768", "missing-ref": "ML-KEM-768"},
    )

    assert result["remaining_quantum_vulnerable"] == {"before": 3, "after": 2}
    assert result["readiness_percent"]["before"] == 33
    assert result["readiness_percent"]["after"] == 67
    assert result["applied_count"] == 1
    assert result["rejected"]["missing-ref"]["reason_code"] == "unknown-finding"
    assert first.strategy["strategy"] != NEEDS_REVIEW


def test_eligibility_and_options_follow_the_role_family():
    snapshot, _ = _snapshot()
    registry = {"ML-KEM-512": "KEM", "ML-KEM-768": "KEM", "ML-KEM-1024": "KEM", "ML-DSA-65": "digital-signature"}
    ranked = {"kx-1": [
        {"candidate": "ML-DSA-65", "family": "digital-signature", "rank": 1, "score": 90.0},
        {"candidate": "ML-KEM-1024", "family": "KEM", "rank": 3, "score": 70.0},
        {"candidate": "ML-KEM-768", "family": "KEM", "rank": 2, "score": 80.0},
    ]}

    result = simulation_options(snapshot, ranked, registry)

    assert result["eligibility"] == {"simulatable": True, "target_family": "KEM", "strategy": snapshot.strategy["strategy"]}
    assert [(o["name"], o["rank"], o["ranked"]) for o in result["options"]] == [
        ("ML-KEM-768", 2, True),
        ("ML-KEM-1024", 3, True),
        ("ML-KEM-512", None, False),  # in the family, never ranked: no invented score
    ]
    assert result["options"][2]["score"] is None
    assert ranked["kx-1"][0]["candidate"] == "ML-DSA-65"  # input not reordered


def test_non_simulatable_findings_offer_no_options():
    review, _ = _snapshot(name="RSA", purposes=("encryption", "digital-signature"))
    keep, _ = _snapshot(name="SHA256", purposes=("hash",), category="hash", quantum_status="quantum-aware")

    for snapshot, reason_code in ((review, "finding-needs-review"), (keep, "no-pqc-migration-for-role")):
        assert simulation_eligibility(snapshot)["reason_code"] == reason_code
        result = simulation_options(snapshot, {snapshot.bom_ref: [{"candidate": "ML-KEM-768", "rank": 1}]})
        assert result["eligibility"]["simulatable"] is False
        assert result["options"] == []


def test_key_material_options_come_from_the_governing_finding_by_bom_ref():
    snapshot, _ = _snapshot(bom_ref="key-1")
    inherited = dataclasses.replace(snapshot, strategy=dict(snapshot.strategy, inherited_from="kx-9"))
    ranked = {"kx-9": [{"candidate": "ML-KEM-768", "rank": 1, "score": 80.0}]}

    result = simulation_options(inherited, ranked, {"ML-KEM-768": "KEM"})

    assert result["ranking_source_bom_ref"] == "kx-9"
    assert [option["name"] for option in result["options"]] == ["ML-KEM-768"]


def test_readiness_rounds_half_up_like_the_dashboard():
    # 3 of 8 at HIGH -> 62.5%: JavaScript's Math.round gives 63, Python's
    # round() would give 62.
    assert readiness_percent(["HIGH"] * 3 + ["LOW"] * 5) == 63
    assert readiness_percent([]) == 100


if __name__ == "__main__":
    test_what_if_applies_a_role_matching_option_without_mutating_the_finding()
    test_what_if_rejects_an_option_from_the_wrong_family()
    test_what_if_rejects_an_unknown_option()
    test_hybrid_what_if_keeps_the_classical_component()
    test_what_if_never_chooses_a_role_for_a_needs_review_finding()
    test_what_if_has_no_pqc_target_for_a_hash()
    test_values_a_what_if_cannot_change_are_carried_forward_and_labelled()
    test_portfolio_reports_readiness_and_remaining_vulnerable_findings()
    test_eligibility_and_options_follow_the_role_family()
    test_non_simulatable_findings_offer_no_options()
    test_key_material_options_come_from_the_governing_finding_by_bom_ref()
    test_readiness_rounds_half_up_like_the_dashboard()

    print("All migration-scenario tests passed.")

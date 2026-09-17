"""
Regression tests for purpose-aware hybrid PQC migration strategy
(services/migration_strategy.py, knowledge/migration_strategy_policy.py)
and the strategy-driven migration actions it feeds.

Inputs are built directly as FindingMigrationInputs, so every case
isolates exactly one piece of evidence; the last tests validate the
persisted active-pipeline output.
"""

import copy
import inspect
import json
from pathlib import Path

import knowledge.migration_strategy_policy as policy_module
import services.migration_strategy as strategy_module
from services.migration_action_generator import generate_migration_actions
from services.migration_strategy import (
    DIRECT_PQC,
    HYBRID,
    KEEP,
    NEEDS_REVIEW,
    FindingMigrationInputs,
    RankedCandidate,
    determine_migration_strategy,
    resolve_key_material_strategies,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

KEM_CANDIDATES = (
    RankedCandidate("ML-KEM-768", "KEM", 1, 88.0),
    RankedCandidate("ML-KEM-1024", "KEM", 2, 80.0),
    RankedCandidate("ML-KEM-512", "KEM", 3, 75.0),
)

SIGNATURE_CANDIDATES = (
    RankedCandidate("ML-DSA-65", "digital-signature", 1, 90.0),
    RankedCandidate("ML-DSA-87", "digital-signature", 2, 85.0),
)


def _inputs(**overrides):
    base = dict(
        bom_ref="ref-default",
        name="Finding",
        category="asymmetric",
        purposes=("key-agreement",),
        purpose_confidence="HIGH",
        purpose_evidence_source="cbom-primitive",
        purpose_evidence_reason="The CBOM explicitly records this finding's cryptographic primitive.",
        purpose_needs_review=False,
        quantum_status="vulnerable",
        risk_reason="Broken by Shor's algorithm.",
        mapping_confidence="HIGH",
        ranked_candidates=KEM_CANDIDATES,
        exposure="INTERNAL",
        blast_radius_score=20.0,
        blast_severity="LOW",
        direct_dependents=0,
        complexity_score=11.0,
        complexity_level="LOW",
        mosca_urgency=None,
        governing_refs=(),
    )
    base.update(overrides)
    return FindingMigrationInputs(**base)


def _actions_for(strategy, purposes):
    return generate_migration_actions(
        {"asset": strategy["current_algorithm"], "bom_ref": strategy["bom_ref"], "classification": {"purpose": list(purposes)}},
        {},
        {"migration_strategy": strategy, "migration_type": "pqc-candidate"},
    )


def _action_text(record):
    return " ".join(step["action"] for step in record["actions"])


# 1 ---------------------------------------------------------------

def test_key_agreement_with_network_exposure_is_hybrid_kem():
    strategy = determine_migration_strategy(_inputs(name="X25519", exposure="INTERNET"))

    assert strategy["strategy"] == HYBRID
    assert strategy["pqc_component"] == "ML-KEM-768"
    assert strategy["pqc_family"] == "KEM"
    assert strategy["classical_component"] == "X25519"
    assert strategy["purpose_class"] == "key-establishment"
    assert strategy["harvest_now_decrypt_later"] is True
    assert "KDF combiner" in strategy["construction"]


def test_key_agreement_without_transition_evidence_is_direct_and_not_high_confidence():
    strategy = determine_migration_strategy(_inputs(name="X25519"))

    assert strategy["strategy"] == DIRECT_PQC
    assert strategy["pqc_component"] == "ML-KEM-768"
    assert strategy["classical_component"] is None
    assert strategy["replaces"] == "X25519"
    # "Direct" rests on the absence of transition evidence.
    assert strategy["confidence"] == "MEDIUM"


# 2 ---------------------------------------------------------------

def test_signature_role_gets_signature_family_even_when_kem_ranks_higher():
    ranked = (
        RankedCandidate("ML-KEM-768", "KEM", 1, 95.0),
        RankedCandidate("ML-DSA-65", "digital-signature", 2, 70.0),
    )

    strategy = determine_migration_strategy(
        _inputs(name="Ed25519", purposes=("digital-signature",), ranked_candidates=ranked, blast_severity="HIGH")
    )

    assert strategy["strategy"] == HYBRID
    assert strategy["pqc_component"] == "ML-DSA-65"
    assert strategy["pqc_family"] == "digital-signature"
    assert "composite or dual signatures" in strategy["construction"]

    actions = _action_text(_actions_for(strategy, ["digital-signature"]))

    assert "ML-DSA-65" in actions
    assert "ML-KEM" not in actions


# 3 ---------------------------------------------------------------

def test_rsa_oaep_encryption_never_receives_signature_recommendation():
    # Deliberately rank a signature candidate FIRST: the old
    # implementation's first-ranked / branch-order logic would pick it.
    ranked = (
        RankedCandidate("ML-DSA-65", "digital-signature", 1, 95.0),
        RankedCandidate("ML-KEM-768", "KEM", 2, 75.0),
    )

    oaep = _inputs(
        name="RSA-OAEP",
        purposes=("encryption",),
        purpose_confidence="MEDIUM",
        purpose_evidence_source="source-context",
        purpose_evidence_reason="Source occurrence(s) call a encryption-specific API.",
        ranked_candidates=ranked,
    )

    strategy = determine_migration_strategy(oaep)

    assert strategy["purpose_class"] == "public-key-encryption"
    assert strategy["pqc_component"] == "ML-KEM-768"
    assert strategy["pqc_family"] == "KEM"
    assert "digital-signature" in strategy["explanation"]["pqc_selection"]  # stated as excluded

    actions = _actions_for(strategy, ["encryption"])

    assert actions["pqc_candidate"] == "ML-KEM-768"
    assert "signature" not in _action_text(actions).lower()
    assert "ML-DSA" not in _action_text(actions)

    # The decision is a function of evidence, not of the name.
    for other_name in ("RSA", "Opaque-Algorithm-42"):
        renamed = determine_migration_strategy(
            FindingMigrationInputs(**{**oaep.__dict__, "name": other_name})
        )
        assert renamed["strategy"] == strategy["strategy"]
        assert renamed["pqc_component"] == strategy["pqc_component"]
        assert renamed["purpose_class"] == strategy["purpose_class"]


# 4 ---------------------------------------------------------------

def test_hash_never_receives_kem_or_signature_recommendation():
    strategy = determine_migration_strategy(
        _inputs(
            name="SHA256",
            category="hash",
            purposes=("hash",),
            quantum_status="quantum-aware",
            ranked_candidates=KEM_CANDIDATES + SIGNATURE_CANDIDATES,
            exposure="INTERNET",
            blast_severity="CRITICAL",
        )
    )

    assert strategy["strategy"] == KEEP
    assert strategy["pqc_component"] is None
    assert strategy["pqc_family"] is None
    assert strategy["pqc_migration_required"] is False
    assert strategy["classical_hardening"]["status"] == "not-required"

    actions = _action_text(_actions_for(strategy, ["hash"]))

    assert "ML-KEM" not in actions and "ML-DSA" not in actions


# 5 ---------------------------------------------------------------

def test_mac_kdf_and_symmetric_roles_get_purpose_appropriate_handling():
    mac = determine_migration_strategy(
        _inputs(category="mac", purposes=("message-authentication",), quantum_status="quantum-aware", ranked_candidates=SIGNATURE_CANDIDATES)
    )
    kdf = determine_migration_strategy(
        _inputs(category="key-derivation", purposes=("key-derivation",), quantum_status="contextual")
    )
    weak_hash = determine_migration_strategy(
        _inputs(category="hash", purposes=("hash",), quantum_status="weak")
    )
    aes_128 = determine_migration_strategy(
        _inputs(category="symmetric", purposes=("encryption",), quantum_status="reduced-security-margin")
    )

    for strategy in (mac, kdf, weak_hash, aes_128):
        assert strategy["strategy"] == KEEP
        assert strategy["pqc_component"] is None

    assert mac["purpose_class"] == "message-authentication"
    assert mac["classical_hardening"]["status"] == "not-required"
    assert kdf["classical_hardening"]["status"] == "review"
    assert weak_hash["classical_hardening"]["status"] == "required"
    assert aes_128["purpose_class"] == "symmetric-encryption"
    assert aes_128["classical_hardening"]["status"] == "recommended"


# 6 ---------------------------------------------------------------

def test_same_algorithm_with_different_purposes_gets_different_recommendations():
    ranked = KEM_CANDIDATES + SIGNATURE_CANDIDATES

    encryption = determine_migration_strategy(_inputs(name="RSA", purposes=("encryption",), ranked_candidates=ranked))
    signing = determine_migration_strategy(_inputs(name="RSA", purposes=("digital-signature",), ranked_candidates=ranked))

    assert encryption["pqc_family"] == "KEM"
    assert signing["pqc_family"] == "digital-signature"
    assert encryption["pqc_component"] != signing["pqc_component"]


# 7 ---------------------------------------------------------------

def test_unknown_purpose_needs_review():
    cases = [
        _inputs(purposes=()),
        _inputs(purposes=("hash",), purpose_needs_review=True, purpose_evidence_source="insufficient-evidence"),
        _inputs(purposes=("public-key-cryptography",)),
        _inputs(category="unknown", purposes=("encryption",)),
    ]

    for inputs in cases:
        strategy = determine_migration_strategy(inputs)

        assert strategy["strategy"] == NEEDS_REVIEW, inputs
        assert strategy["pqc_component"] is None
        assert strategy["pqc_migration_required"] is False


def test_resolved_role_with_unconfirmed_quantum_status_needs_review():
    # The role is known from CBOM evidence, but the quantum status is
    # not: no PQC family or component may be assumed from the role alone.
    strategy = determine_migration_strategy(
        _inputs(category="unknown", purposes=("digital-signature",), quantum_status="unknown", ranked_candidates=SIGNATURE_CANDIDATES)
    )

    assert strategy["strategy"] == NEEDS_REVIEW
    assert strategy["reason_code"] == "quantum-status-unconfirmed"
    assert strategy["purpose_class"] == "digital-signature"
    assert strategy["pqc_family"] is None
    assert strategy["pqc_component"] is None
    assert strategy["confidence"] in {"LOW", "MEDIUM"}

    actions = _actions_for(strategy, ["digital-signature"])
    text = " ".join(step["action"] for step in actions["actions"])

    assert actions["pqc_candidate"] is None
    assert "ML-" not in text
    assert "quantum-vulnerable" in text
    assert "confirmed purpose" not in text


# 8 ---------------------------------------------------------------

def test_conflicting_evidence_needs_review():
    strategy = determine_migration_strategy(
        _inputs(purposes=("hash", "digital-signature"), purpose_evidence_source="conflicting", purpose_needs_review=True)
    )

    assert strategy["strategy"] == NEEDS_REVIEW
    assert strategy["reason_code"] == "conflicting-purpose-evidence"
    assert strategy["pqc_component"] is None


def test_multiple_possible_roles_need_review_with_options_not_a_choice():
    strategy = determine_migration_strategy(
        _inputs(
            name="RSA",
            purposes=("encryption", "digital-signature"),
            purpose_confidence="LOW",
            purpose_evidence_source="algorithm-family-fallback",
            ranked_candidates=SIGNATURE_CANDIDATES + KEM_CANDIDATES,
        )
    )

    assert strategy["strategy"] == NEEDS_REVIEW
    assert strategy["reason_code"] == "ambiguous-purpose"
    assert strategy["pqc_component"] is None
    assert {option["pqc_family"] for option in strategy["review_options"]} == {"KEM", "digital-signature"}

    actions = _actions_for(strategy, ["encryption", "digital-signature"])

    assert actions["pqc_candidate"] is None

    # Candidate names only ever appear as conditional options.
    for step in actions["actions"]:
        if "ML-" in step["action"]:
            assert step["action"].startswith("If it performs"), step["action"]


# 9 ---------------------------------------------------------------

def test_duplicate_algorithm_names_with_different_bom_refs_stay_independent():
    ranked = KEM_CANDIDATES + SIGNATURE_CANDIDATES

    first = _inputs(bom_ref="rsa-2048-a", name="RSA-2048", purposes=("encryption",), ranked_candidates=ranked)
    second = _inputs(bom_ref="rsa-2048-b", name="RSA-2048", purposes=("digital-signature",), ranked_candidates=ranked, exposure="INTERNET")
    key_a = _inputs(bom_ref="key-a", name="private-key@a", category="crypto-material", purposes=("private-key",), purpose_confidence="LOW", purpose_evidence_source="algorithm-family-fallback", quantum_status="contextual", governing_refs=("rsa-2048-a",))
    key_b = _inputs(bom_ref="key-b", name="private-key@b", category="crypto-material", purposes=("private-key",), purpose_confidence="LOW", purpose_evidence_source="algorithm-family-fallback", quantum_status="contextual", governing_refs=("rsa-2048-b",))

    inputs_by_ref = {i.bom_ref: i for i in (first, second, key_a, key_b)}
    strategies = {ref: determine_migration_strategy(i) for ref, i in inputs_by_ref.items()}
    original = copy.deepcopy(strategies)

    resolved = resolve_key_material_strategies(strategies, inputs_by_ref)

    assert strategies == original  # inputs never mutated

    assert resolved["rsa-2048-a"]["strategy"] == DIRECT_PQC
    assert resolved["rsa-2048-a"]["pqc_family"] == "KEM"
    assert resolved["rsa-2048-b"]["strategy"] == HYBRID
    assert resolved["rsa-2048-b"]["pqc_family"] == "digital-signature"

    assert resolved["key-a"]["inherited_from"] == "rsa-2048-a"
    assert resolved["key-a"]["strategy"] == DIRECT_PQC
    assert resolved["key-a"]["pqc_component"] == "ML-KEM-768"
    assert resolved["key-b"]["inherited_from"] == "rsa-2048-b"
    assert resolved["key-b"]["strategy"] == HYBRID
    assert resolved["key-b"]["classical_component"] == "private-key@b"

    for ref, strategy in resolved.items():
        assert strategy["bom_ref"] == ref


# 10 --------------------------------------------------------------

def test_evidence_and_confidence_propagate_into_the_recommendation():
    low_purpose = determine_migration_strategy(_inputs(purpose_confidence="LOW", exposure="INTERNET"))
    capped_by_mapping = determine_migration_strategy(_inputs(mapping_confidence="MEDIUM", exposure="INTERNET"))
    evidence = determine_migration_strategy(_inputs(exposure="INTERNET"))

    assert low_purpose["strategy"] == HYBRID and low_purpose["confidence"] == "LOW"
    assert capped_by_mapping["confidence"] == "MEDIUM"
    assert evidence["confidence"] == "HIGH"

    explanation = evidence["explanation"]

    assert "cbom-primitive" in explanation["purpose_evidence"]
    assert "explicitly records" in explanation["purpose_evidence"]
    assert explanation["classification_confidence"] == "HIGH"
    assert set(explanation) == {
        "detected", "resolved_purpose", "purpose_evidence", "classification_confidence",
        "quantum_relevance", "pqc_selection", "strategy_rationale", "expected_impact",
    }
    assert {factor["signal"] for factor in evidence["decision_factors"]} >= {
        "external_interoperability", "migration_complexity", "blast_radius",
    }


def test_decision_logic_never_branches_on_algorithm_names():
    decision_source = "".join(
        inspect.getsource(function)
        for function in (
            strategy_module.determine_migration_strategy,
            strategy_module.resolve_key_material_strategies,
            strategy_module._family_candidates,
            strategy_module._purpose_classes,
            policy_module.classify_purpose,
        )
    )

    for token in ("RSA", "OAEP", "25519", "448", "ECDH", "ECDSA", "EdDSA", "Diffie"):
        assert token not in decision_source, token


# 11 --------------------------------------------------------------

def _load(filename):
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return {record["bom_ref"]: record for record in json.load(file)["assets"]}


def test_pipeline_strategy_does_not_drive_priority_and_preserves_identity():
    priority = _load("ecdat-migration-priority.json")
    plan = _load("ecdat-pqc-migration-plan.json")
    report = _load("ecdat-migration-report.json")

    assert set(priority) == set(plan) == set(report)

    for bom_ref, record in report.items():
        strategy = record["migration_strategy"]

        assert strategy["bom_ref"] == bom_ref
        assert strategy["strategy"] in {KEEP, DIRECT_PQC, HYBRID, NEEDS_REVIEW}
        assert "migration_strategy" not in priority[bom_ref]
        assert record["migration_impact"]["priority"]["score"] == priority[bom_ref]["migration_priority"]["priority_score"]


def test_pipeline_strategies_are_purpose_consistent():
    report = _load("ecdat-migration-report.json")

    for bom_ref, record in report.items():
        strategy = record["migration_strategy"]
        role = strategy["purpose_class"]
        expected_family = policy_module.POLICIES.get(role, {}).get("pqc_family")

        # Key material has no family of its own; it follows the algorithm
        # that uses it (a single governing bom_ref).
        if strategy["inherited_from"]:
            expected_family = report[strategy["inherited_from"]]["migration_strategy"]["pqc_family"]

        # A selected family must always be the role's family. A resolved
        # role may still carry no family when the finding is under review
        # (e.g. its quantum status is not confirmed vulnerable).
        if strategy["pqc_family"] is not None:
            assert strategy["pqc_family"] == expected_family, bom_ref

        if strategy["strategy"] in {DIRECT_PQC, HYBRID} and strategy["inherited_from"] is None:
            assert expected_family and strategy["pqc_family"] == expected_family, bom_ref

        if role in policy_module.NO_PQC_REPLACEMENT_ROLES:
            assert strategy["strategy"] == KEEP and strategy["pqc_component"] is None, bom_ref

        if strategy["strategy"] == NEEDS_REVIEW:
            assert strategy["pqc_component"] is None, bom_ref


if __name__ == "__main__":
    test_key_agreement_with_network_exposure_is_hybrid_kem()
    test_key_agreement_without_transition_evidence_is_direct_and_not_high_confidence()
    test_signature_role_gets_signature_family_even_when_kem_ranks_higher()
    test_rsa_oaep_encryption_never_receives_signature_recommendation()
    test_hash_never_receives_kem_or_signature_recommendation()
    test_mac_kdf_and_symmetric_roles_get_purpose_appropriate_handling()
    test_same_algorithm_with_different_purposes_gets_different_recommendations()
    test_unknown_purpose_needs_review()
    test_resolved_role_with_unconfirmed_quantum_status_needs_review()
    test_conflicting_evidence_needs_review()
    test_multiple_possible_roles_need_review_with_options_not_a_choice()
    test_duplicate_algorithm_names_with_different_bom_refs_stay_independent()
    test_evidence_and_confidence_propagate_into_the_recommendation()
    test_decision_logic_never_branches_on_algorithm_names()
    test_pipeline_strategy_does_not_drive_priority_and_preserves_identity()
    test_pipeline_strategies_are_purpose_consistent()

    print("All migration-strategy tests passed.")

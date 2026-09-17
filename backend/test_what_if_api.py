"""
What-If Migration Simulator API (backend/main.py /api/what-if/*),
exercised against the real ECDAT dataset by calling the route functions
directly -- no running server or HTTP client dependency required.

Findings are always chosen by bom_ref and by their decided strategy,
never by algorithm name.
"""

import copy
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

import main
from models.risk_factors import RiskContext
from services.contextual_risk import calculate_contextual_risk
from services.migration_priority import calculate_migration_priority
from services.migration_scenario import load_finding_snapshots, readiness_percent
from services.pqc_registry import get_pqc_algorithms


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(filename):
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)


def _plan_by_ref():
    return {record["bom_ref"]: record for record in _load("ecdat-pqc-migration-plan.json")["assets"]}


def _ref_with_strategy(strategy, inherited=False):
    for bom_ref, record in _plan_by_ref().items():
        decided = record["migration_strategy"]
        if decided["strategy"] == strategy and bool(decided.get("inherited_from")) == inherited:
            return bom_ref
    raise AssertionError(f"The dataset must contain a {strategy} finding (inherited={inherited}).")


def _registry():
    return {algorithm["name"]: algorithm["family"] for algorithm in get_pqc_algorithms()}


def _data_fingerprint():
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(DATA_DIR.glob("*.json"))
    }


def _simulate(bom_ref, option):
    return main.simulate_what_if(main.WhatIfSimulationRequest(bom_ref=bom_ref, pqc_option=option))


def _rejection(bom_ref, option):
    try:
        _simulate(bom_ref, option)
    except HTTPException as exc:
        return exc
    raise AssertionError(f"Simulating {option} on {bom_ref} should have been rejected.")


def _other_family_option(family):
    return next(name for name, other in _registry().items() if other != family)


def test_valid_option_returns_before_after_and_delta():
    bom_ref = _ref_with_strategy("DIRECT_PQC")
    finding = main.get_what_if_finding(bom_ref)

    assert finding["simulatable"] is True
    assert finding["options"], "A simulatable finding must offer PQC options."
    assert all(_registry()[option["name"]] == finding["target_family"] for option in finding["options"])

    ranked = [option for option in finding["options"] if option["ranked"]]
    assert [option["rank"] for option in ranked] == sorted(option["rank"] for option in ranked)

    option = finding["options"][-1]["name"]
    result = _simulate(bom_ref, option)

    assert result["simulation_mode"] == "what-if"
    assert result["persisted"] is False
    assert result["finding"]["applied"] is True
    assert result["finding"]["bom_ref"] == bom_ref
    assert result["finding"]["pqc_component"] == option

    for metric in ("risk", "priority"):
        block = result["finding"][metric]
        key = "score"
        assert block["delta"] == round(block["after"][key] - block["before"][key], 2)

    assert result["finding"]["risk"]["delta"] < 0


def test_before_after_uses_the_real_engines_and_matches_the_recorded_finding():
    bom_ref = _ref_with_strategy("HYBRID")
    risk_record = next(r for r in _load("ecdat-explainable-risk.json")["assets"] if r["bom_ref"] == bom_ref)
    priority_record = next(r for r in _load("ecdat-migration-priority.json")["assets"] if r["bom_ref"] == bom_ref)
    blast_record = next(r for r in _load("ecdat-blast-radius.json")["assets"] if r["bom_ref"] == bom_ref)
    complexity_record = next(r for r in _load("ecdat-migration-complexity.json")["assets"] if r["bom_ref"] == bom_ref)

    option = main.get_what_if_finding(bom_ref)["options"][0]["name"]
    result = _simulate(bom_ref, option)["finding"]

    # "before" reproduces the pipeline's recorded, authoritative values.
    assert result["risk"]["before"]["score"] == risk_record["risk_assessment"]["final_score"]
    assert result["priority"]["before"]["score"] == priority_record["migration_priority"]["priority_score"]
    assert result["priority"]["before"]["level"] == priority_record["migration_priority"]["priority"]

    # "after" is the same engines with only the quantum status migrated.
    context = risk_record["risk_assessment"]["context"]
    risk_context = RiskContext(**{
        key: context[key]
        for key in (
            "business_criticality",
            "data_lifetime_years",
            "migration_time_years",
            "exposure",
            "quantum_threat_horizon_years",
        )
        if key in context
    })
    migrated = {
        "name": risk_record["name"],
        "classification": dict(risk_record["classification"], quantum_status="quantum-resistant"),
        "occurrences": risk_record.get("occurrences") or [],
    }
    expected_risk = calculate_contextual_risk(migrated, risk_context)
    expected_priority = calculate_migration_priority(
        expected_risk["final_score"],
        blast_record["blast_radius_score"],
        complexity_record["score"],
        business_criticality=priority_record.get("business_criticality"),
        mosca_urgency=(priority_record.get("mosca_analysis") or {}).get("migration_urgency"),
    )

    assert result["risk"]["after"]["score"] == expected_risk["final_score"]
    assert result["risk"]["after"]["severity"] == expected_risk["severity"]
    assert result["priority"]["after"]["score"] == expected_priority["priority_score"]
    assert result["strategy"] == "HYBRID"
    assert result["classical_component"] == risk_record["name"]


def test_wrong_family_option_is_rejected():
    bom_ref = _ref_with_strategy("DIRECT_PQC")
    family = main.get_what_if_finding(bom_ref)["target_family"]

    exc = _rejection(bom_ref, _other_family_option(family))

    assert exc.status_code == 422
    assert exc.detail["reason_code"] == "option-family-does-not-match-role"


def test_unknown_option_is_rejected():
    exc = _rejection(_ref_with_strategy("DIRECT_PQC"), "NOT-A-PQC-ALGORITHM")

    assert exc.status_code == 422
    assert exc.detail["reason_code"] == "unknown-pqc-option"


def test_needs_review_finding_is_not_simulatable():
    bom_ref = _ref_with_strategy("NEEDS_REVIEW")
    finding = main.get_what_if_finding(bom_ref)

    assert finding["simulatable"] is False
    assert finding["reason_code"] == "finding-needs-review"
    assert finding["options"] == []

    for option in _registry():
        exc = _rejection(bom_ref, option)
        assert exc.detail["reason_code"] == "finding-needs-review"


def test_keep_finding_is_not_simulatable():
    bom_ref = _ref_with_strategy("KEEP")
    finding = main.get_what_if_finding(bom_ref)

    assert finding["simulatable"] is False
    assert finding["reason_code"] == "no-pqc-migration-for-role"
    assert finding["options"] == []

    for option in _registry():
        exc = _rejection(bom_ref, option)
        assert exc.detail["reason_code"] == "no-pqc-migration-for-role"


def test_findings_are_addressed_by_bom_ref_only():
    assets = _load("ecdat-assets.json")["assets"]
    names = [asset["name"] for asset in assets]
    duplicate_name = next(name for name in names if names.count(name) > 1)
    duplicate_refs = [asset["bom_ref"] for asset in assets if asset["name"] == duplicate_name]

    # Same algorithm name, distinct findings: each ref resolves to itself.
    for bom_ref in duplicate_refs:
        assert main.get_what_if_finding(bom_ref)["bom_ref"] == bom_ref

    # An algorithm name is not a finding identity.
    for call in (
        lambda: main.get_what_if_finding(duplicate_name),
        lambda: _simulate(duplicate_name, "ML-KEM-768"),
    ):
        try:
            call()
        except HTTPException as exc:
            assert exc.status_code == 404
            assert exc.detail["reason_code"] == "unknown-finding"
        else:
            raise AssertionError("An algorithm name must not resolve to a finding.")

    # ...and cannot be smuggled in as an extra request field.
    try:
        main.WhatIfSimulationRequest(asset=duplicate_name, bom_ref=duplicate_refs[0], pqc_option="ML-KEM-768")
    except ValidationError:
        pass
    else:
        raise AssertionError("Unknown request fields must be rejected.")

    # Key material reads its ranking from its governing finding by bom_ref.
    inherited_ref = _ref_with_strategy("HYBRID", inherited=True)
    inherited = main.get_what_if_finding(inherited_ref)
    assert inherited["ranking_source_bom_ref"] == _plan_by_ref()[inherited_ref]["migration_strategy"]["inherited_from"]
    assert inherited["options"]


def test_portfolio_readiness_matches_the_dashboard_definition():
    summary = main.get_summary()
    dashboard_readiness = readiness_percent(
        ["HIGH"] * summary["high_or_critical_priority_assets"]
        + ["LOW"] * (summary["total_assets"] - summary["high_or_critical_priority_assets"])
    )

    bom_ref = _ref_with_strategy("DIRECT_PQC")
    option = main.get_what_if_finding(bom_ref)["options"][0]["name"]
    single = _simulate(bom_ref, option)["portfolio"]

    assert single["finding_count"] == summary["total_assets"]
    assert single["readiness_percent"]["before"] == dashboard_readiness
    assert single["readiness_percent"]["delta"] == (
        single["readiness_percent"]["after"] - single["readiness_percent"]["before"]
    )
    assert single["remaining_quantum_vulnerable"]["after"] == single["remaining_quantum_vulnerable"]["before"] - 1

    simulatable = {}
    for bom_ref in _plan_by_ref():
        finding = main.get_what_if_finding(bom_ref)
        if finding["simulatable"]:
            simulatable[bom_ref] = finding["options"][0]["name"]

    replacements = dict(simulatable, **{_ref_with_strategy("NEEDS_REVIEW"): "ML-KEM-768", "no-such-ref": "ML-KEM-768"})
    portfolio = main.simulate_what_if_portfolio(main.WhatIfPortfolioRequest(replacements=replacements))

    assert portfolio["persisted"] is False
    assert portfolio["applied_count"] == len(simulatable)
    assert portfolio["rejected"]["no-such-ref"]["reason_code"] == "unknown-finding"
    assert portfolio["readiness_percent"]["before"] == dashboard_readiness
    assert portfolio["readiness_percent"]["after"] >= portfolio["readiness_percent"]["before"]

    try:
        main.WhatIfPortfolioRequest(replacements={})
    except ValidationError:
        pass
    else:
        raise AssertionError("An empty portfolio simulation must be rejected.")


def test_simulation_never_changes_the_real_finding_or_dataset():
    fingerprint = _data_fingerprint()
    snapshots_before = copy.deepcopy(load_finding_snapshots())

    bom_ref = _ref_with_strategy("DIRECT_PQC")
    detail_before = main.get_asset(bom_ref)

    for option in main.get_what_if_finding(bom_ref)["options"]:
        _simulate(bom_ref, option["name"])
    _rejection(bom_ref, "NOT-A-PQC-ALGORITHM")
    main.simulate_what_if_portfolio(main.WhatIfPortfolioRequest(replacements={bom_ref: "ML-KEM-1024"}))

    assert _data_fingerprint() == fingerprint
    assert load_finding_snapshots() == snapshots_before
    assert main.get_asset(bom_ref) == detail_before


if __name__ == "__main__":
    test_valid_option_returns_before_after_and_delta()
    test_before_after_uses_the_real_engines_and_matches_the_recorded_finding()
    test_wrong_family_option_is_rejected()
    test_unknown_option_is_rejected()
    test_needs_review_finding_is_not_simulatable()
    test_keep_finding_is_not_simulatable()
    test_findings_are_addressed_by_bom_ref_only()
    test_portfolio_readiness_matches_the_dashboard_definition()
    test_simulation_never_changes_the_real_finding_or_dataset()

    print("All what-if API tests passed.")

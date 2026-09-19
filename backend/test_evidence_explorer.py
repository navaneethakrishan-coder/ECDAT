"""
Evidence Explorer (services/evidence_explorer.py, GET /api/evidence/{bom_ref}).
Findings are chosen by bom_ref and by their recorded strategy -- the only
name-based lookup is the one that finds the duplicate-name findings the
identity tests need.

Runs against the fixture dataset (fixture_dataset.py) rather than `data/`,
so the two same-named findings it relies on are guaranteed to be there
whatever repository ECDAT last scanned.
"""

import copy
import hashlib
import json
from collections import Counter

from fastapi import HTTPException

import fixture_dataset
import main
from services import evidence_explorer
from services.evidence_explorer import build_finding_evidence, load_evidence_records


DATA_DIR = fixture_dataset.use_fixture_data(main, evidence_explorer)


def _load(filename):
    return fixture_dataset.load(filename)


def _by_ref(filename):
    return {record["bom_ref"]: record for record in _load(filename)["assets"]}


def _ref_with_strategy(strategy):
    for bom_ref, record in _by_ref("ecdat-pqc-migration-plan.json").items():
        if record["migration_strategy"]["strategy"] == strategy:
            return bom_ref
    raise AssertionError(f"The dataset must contain a {strategy} finding.")


def _duplicate_name_refs():
    assets = _load("ecdat-assets.json")["assets"]
    counts = Counter(asset["name"] for asset in assets)
    name = next(name for name, count in counts.items() if count > 1)
    return name, [asset["bom_ref"] for asset in assets if asset["name"] == name]


def _fingerprint():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(DATA_DIR.glob("*.json"))}


def test_evidence_response_exposes_every_section_for_every_finding():
    sources = _by_ref("ecdat-assets.json")

    for bom_ref, source in sources.items():
        evidence = main.get_finding_evidence(bom_ref)

        assert evidence["bom_ref"] == bom_ref
        assert set(evidence) == {"bom_ref", "identity", "purpose", "source", "quantum", "risk", "migration", "chain"}
        assert set(evidence["migration"]) == {"blast_radius", "complexity", "priority", "strategy", "pqc"}
        assert [step["key"] for step in evidence["chain"]] == [
            "evidence", "purpose", "quantum", "risk", "priority", "strategy", "pqc",
        ]
        assert evidence["identity"]["name"] == source["name"]
        assert evidence["source"]["occurrence_count"] == len(source["occurrences"])
        json.dumps(evidence)  # serializable as an API response


def test_evidence_values_are_copied_from_the_pipeline_not_recomputed():
    bom_ref = _ref_with_strategy("HYBRID")
    evidence = main.get_finding_evidence(bom_ref)

    risk = _by_ref("ecdat-explainable-risk.json")[bom_ref]
    blast = _by_ref("ecdat-blast-radius.json")[bom_ref]
    complexity = _by_ref("ecdat-migration-complexity.json")[bom_ref]
    priority = _by_ref("ecdat-migration-priority.json")[bom_ref]["migration_priority"]
    strategy = _by_ref("ecdat-pqc-migration-plan.json")[bom_ref]["migration_strategy"]

    assert evidence["risk"]["final_score"] == risk["risk_assessment"]["final_score"]
    assert evidence["risk"]["contributions"] == risk["explanation"]["contributions"]
    assert evidence["migration"]["blast_radius"]["score"] == blast["blast_radius_score"]
    assert evidence["migration"]["complexity"]["score"] == complexity["score"]
    assert evidence["migration"]["complexity"]["factors"] == complexity["factors"]
    assert evidence["migration"]["priority"]["score"] == priority["priority_score"]
    assert evidence["migration"]["priority"]["level"] == priority["priority"]
    assert evidence["migration"]["strategy"]["strategy"] == strategy["strategy"]
    assert evidence["migration"]["strategy"]["rationale"] == strategy["rationale"]
    assert evidence["migration"]["pqc"]["status"] == "selected"
    assert evidence["migration"]["pqc"]["selected_component"] == strategy["pqc_component"]


def test_findings_are_addressed_by_bom_ref_only():
    name, refs = _duplicate_name_refs()

    try:
        main.get_finding_evidence(name)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail["reason_code"] == "unknown-finding"
    else:
        raise AssertionError("An algorithm name must not resolve to a finding.")

    for bom_ref in refs:
        assert main.get_finding_evidence(bom_ref)["identity"]["bom_ref"] == bom_ref


def test_duplicate_rsa_2048_findings_keep_their_own_evidence():
    name, refs = _duplicate_name_refs()
    assert name == "RSA-2048" and len(refs) == 2, "The fixture's duplicate-name findings are the two RSA-2048 findings."

    sources = _by_ref("ecdat-assets.json")
    blast = _by_ref("ecdat-blast-radius.json")
    components = {c["bom-ref"]: c for c in _load("keycloak-cbom.json")["components"]}
    first, second = (main.get_finding_evidence(ref) for ref in refs)

    assert first["bom_ref"] != second["bom_ref"]

    for evidence in (first, second):
        ref = evidence["bom_ref"]
        other = second if evidence is first else first

        # Source evidence is this finding's own CBOM occurrences...
        own_locations = [(o["location"], o["line"]) for o in sources[ref]["occurrences"]]
        assert [(o["location"], o["line"]) for o in evidence["source"]["occurrences"]] == own_locations
        raw = [(o["location"], o["line"]) for o in components[ref]["evidence"]["occurrences"]]
        assert own_locations == raw

        # ...its own dependency edges...
        assert [d["bom_ref"] for d in evidence["source"]["dependencies"]["direct_dependents"]] == blast[ref]["direct_dependents"]["refs"]

        # ...and nothing identifying the other finding leaks in.
        text = json.dumps(evidence)
        assert other["bom_ref"] not in text
        for occurrence in other["source"]["occurrences"]:
            if (occurrence["location"], occurrence["line"]) not in own_locations:
                assert occurrence["location"] not in text

    assert first["source"]["occurrences"] != second["source"]["occurrences"]
    assert first["source"]["dependencies"] != second["source"]["dependencies"]


def test_unknown_evidence_stays_unknown():
    for bom_ref, risk in _by_ref("ecdat-explainable-risk.json").items():
        evidence = main.get_finding_evidence(bom_ref)
        context = risk["risk_assessment"]["context"]
        lifetime = next(f for f in evidence["risk"]["context"] if f["factor"] == "data_lifetime_years")

        if not context.get("data_lifetime_known"):
            assert lifetime == {**lifetime, "known": False, "value": None}
            assert "data_lifetime" in [f["factor"] for f in evidence["risk"]["unknown_factors"]]
            assert evidence["risk"]["mosca"]["performed"] is False
            assert evidence["risk"]["mosca"]["reason"]

        unknown_contributions = [c for c in evidence["risk"]["contributions"] if c.get("known") is False]
        assert all("weighted_score" not in c for c in unknown_contributions)

        priority = evidence["migration"]["priority"]
        for factor in priority["unknown_factors"]:
            block = next(c for c in priority["contributions"] if c["factor"] == factor)
            assert block["known"] is False
            assert block["weighted_score"] is None and block["raw_score"] is None


def test_missing_records_are_reported_as_absent_not_filled_in():
    records = load_evidence_records(DATA_DIR)
    bom_ref = _ref_with_strategy("DIRECT_PQC")
    stripped = copy.deepcopy(records)
    for key in ("blast", "complexity", "priority", "plan"):
        stripped[key].pop(bom_ref)
    stripped["cbom_components"].pop(bom_ref)

    evidence = build_finding_evidence(bom_ref, stripped)

    assert evidence["migration"]["blast_radius"] is None
    assert evidence["migration"]["complexity"] is None
    assert evidence["migration"]["priority"] is None
    assert evidence["migration"]["strategy"] is None
    assert evidence["migration"]["pqc"]["status"] == "unknown"
    assert evidence["migration"]["pqc"]["ranked_candidates"] == []
    assert evidence["identity"]["in_raw_cbom"] is False
    assert evidence["identity"]["cbom_crypto_properties"] is None
    assert evidence["source"]["dependencies"] is None
    assert {step["key"]: step["status"] for step in evidence["chain"]}["strategy"] == "unknown"
    assert build_finding_evidence("no-such-ref", records) is None


def test_purpose_confidence_and_source_are_reported_as_recorded():
    seen_sources = set()

    for bom_ref, risk in _by_ref("ecdat-explainable-risk.json").items():
        classification = risk["classification"]
        purpose = main.get_finding_evidence(bom_ref)["purpose"]

        assert purpose["resolved_purposes"] == classification["purpose"]
        assert purpose["confidence"] == classification["purpose_confidence"]
        assert purpose["evidence_source"] == classification["purpose_evidence_source"]
        assert purpose["evidence_reason"] == classification["purpose_evidence_reason"]
        assert purpose["supporting_evidence"] == classification.get("purpose_evidence")
        seen_sources.add(purpose["evidence_source"])

        if purpose["evidence_source"] == "algorithm-family-fallback":
            assert purpose["repository_evidence"] is False
            assert purpose["confidence"] == "LOW"
            purpose_step = next(s for s in main.get_finding_evidence(bom_ref)["chain"] if s["key"] == "purpose")
            assert purpose_step["status"] in ("low-confidence", "unresolved")
        elif purpose["evidence_source"] in ("cbom-primitive", "source-context"):
            assert purpose["repository_evidence"] is True

    assert {"cbom-primitive", "algorithm-family-fallback"} <= seen_sources


def test_risk_contributions_reconcile_with_the_score():
    for bom_ref in _by_ref("ecdat-assets.json"):
        risk = main.get_finding_evidence(bom_ref)["risk"]
        known = [c for c in risk["contributions"] if c.get("known")]

        assert round(sum(c["weighted_score"] for c in known), 2) == risk["contribution_total"]
        assert abs(risk["contribution_total"] - risk["final_score"]) <= 0.05
        assert abs(sum(c["weight"] for c in known) - 1.0) <= 0.001


def test_needs_review_finding_stays_unresolved_and_never_shows_a_selected_pqc():
    for bom_ref, record in _by_ref("ecdat-pqc-migration-plan.json").items():
        if record["migration_strategy"]["strategy"] != "NEEDS_REVIEW":
            continue

        evidence = main.get_finding_evidence(bom_ref)
        pqc = evidence["migration"]["pqc"]
        steps = {step["key"]: step for step in evidence["chain"]}

        assert evidence["migration"]["strategy"]["resolved"] is False
        assert pqc["status"] == "unresolved"
        assert pqc["selected_component"] is None
        assert pqc["role_family"] is None
        assert all(candidate["fits_role"] is None for candidate in pqc["ranked_candidates"])
        assert "not a confirmed recommendation" in pqc["note"]
        assert steps["strategy"]["status"] == "unresolved"
        assert steps["pqc"]["status"] == "unresolved"
        for candidate in pqc["ranked_candidates"]:
            assert candidate["candidate"] not in steps["pqc"]["statement"]


def test_keep_finding_has_no_pqc_path():
    evidence = main.get_finding_evidence(_ref_with_strategy("KEEP"))
    pqc = evidence["migration"]["pqc"]

    assert pqc["status"] == "not-applicable"
    assert pqc["selected_component"] is None
    assert {step["key"]: step["status"] for step in evidence["chain"]}["pqc"] == "not-applicable"


def test_evidence_explorer_is_read_only():
    fingerprint = _fingerprint()

    for bom_ref in _by_ref("ecdat-assets.json"):
        main.get_finding_evidence(bom_ref)

    assert _fingerprint() == fingerprint


if __name__ == "__main__":
    test_evidence_response_exposes_every_section_for_every_finding()
    test_evidence_values_are_copied_from_the_pipeline_not_recomputed()
    test_findings_are_addressed_by_bom_ref_only()
    test_duplicate_rsa_2048_findings_keep_their_own_evidence()
    test_unknown_evidence_stays_unknown()
    test_missing_records_are_reported_as_absent_not_filled_in()
    test_purpose_confidence_and_source_are_reported_as_recorded()
    test_risk_contributions_reconcile_with_the_score()
    test_needs_review_finding_stays_unresolved_and_never_shows_a_selected_pqc()
    test_keep_finding_has_no_pqc_path()
    test_evidence_explorer_is_read_only()

    print("All evidence-explorer tests passed.")

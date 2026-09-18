"""
Regression tests: a NEEDS_REVIEW finding's ranking-model candidate must
never be presented as a PQC recommendation -- in the plan/report data,
the API, the dashboard count, or the AI advisor context -- while
DIRECT_PQC / HYBRID keep their strategy-selected component and KEEP
stays recommendation-free (services/recommendation_state.py).

Fixture findings are addressed by bom_ref only.
"""

import copy
import json

import fixture_dataset

import main
from services import ai_advisor
from services.ai_advisor import build_context
from services.recommendation_state import (
    count_selected_pqc_paths,
    reconcile_recommendation,
)

# The API and AI-context layers are exercised in-process here, so they read
# the fixture dataset too rather than whatever is in data/.
fixture_dataset.use_fixture_data(main, ai_advisor)


# Findings come from the fixture dataset (fixture_dataset.py), not from
# data/, so this test says the same thing whatever ECDAT last scanned.
# Addressed by bom_ref -- the canonical finding identity -- never by name.
RSA_2048_REFS = (                                            # NEEDS_REVIEW, duplicate name
    fixture_dataset.ref("rsa2048_java"),
    fixture_dataset.ref("rsa2048_python"),
)
RSA_REF = RSA_2048_REFS[0]                                   # NEEDS_REVIEW
NEEDS_REVIEW_ALGORITHMS = RSA_2048_REFS
X25519_REF = fixture_dataset.ref("x25519")                   # DIRECT_PQC -> ML-KEM
DSA_REF = fixture_dataset.ref("dsa")                         # HYBRID -> ML-DSA
SHA256_REF = fixture_dataset.ref("sha256")                   # KEEP


def _records(filename):
    return {record["bom_ref"]: record for record in fixture_dataset.load(filename)["assets"]}


def _all_needs_review_refs():
    return [
        ref for ref, record in _records("ecdat-migration-report.json").items()
        if record["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
    ]


# ---------------------------------------------------------------------
# Unit: reconciliation rules
# ---------------------------------------------------------------------

RANKING = {
    "decision": "RECOMMENDED",
    "candidate": "ML-DSA-65",
    "candidate_rank": 1,
    "candidate_score": 84.93,
    "confidence": "LOW",
    "reason": "Highest-ranked candidate.",
}


def test_needs_review_clears_the_candidate_but_keeps_ranking_output():
    strategy = {"strategy": "NEEDS_REVIEW", "pqc_component": None, "confidence": "LOW"}
    original = copy.deepcopy(RANKING)

    record = reconcile_recommendation(RANKING, strategy)

    assert RANKING == original  # input not mutated
    assert record["decision"] == "NEEDS_REVIEW"
    assert record["candidate"] is None
    assert record["candidate_rank"] is None and record["candidate_score"] is None
    assert record["confirmed"] is False
    assert record["selected_component"] is None
    assert {k: record["ranking_model"][k] for k in RANKING} == RANKING
    assert "ranking model" in record["ranking_model"]["note"].lower()
    assert reconcile_recommendation(record, strategy) == record  # idempotent


def test_direct_and_hybrid_keep_the_strategy_selected_component():
    for name, component in (("DIRECT_PQC", "ML-KEM-768"), ("HYBRID", "ML-DSA-65")):
        ranking = dict(RANKING, candidate=component)
        strategy = {"strategy": name, "pqc_component": component}

        record = reconcile_recommendation(ranking, strategy)

        assert record["candidate"] == component
        assert record["selected_component"] == component
        assert record["confirmed"] is True
        assert record["decision"] == "RECOMMENDED"
        assert reconcile_recommendation(record, strategy) == record

    # A ranking candidate the strategy did not select is never shown as the candidate.
    mismatch = reconcile_recommendation(RANKING, {"strategy": "DIRECT_PQC", "pqc_component": "ML-KEM-768"})
    assert mismatch["candidate"] is None
    assert mismatch["selected_component"] == "ML-KEM-768"


def test_keep_has_no_candidate_and_legacy_records_pass_through():
    keep = reconcile_recommendation(dict(RANKING, decision="NO_DIRECT_REPLACEMENT"), {"strategy": "KEEP"})
    assert keep["candidate"] is None and keep["confirmed"] is False

    assert reconcile_recommendation(RANKING, None) == RANKING
    assert count_selected_pqc_paths([
        {"strategy": "DIRECT_PQC", "pqc_component": "ML-KEM-768"},
        {"strategy": "HYBRID", "pqc_component": "ML-DSA-65"},
        {"strategy": "HYBRID", "pqc_component": None},
        {"strategy": "NEEDS_REVIEW"},
        {"strategy": "KEEP"},
        None,
    ]) == 2


# ---------------------------------------------------------------------
# Data + API: RSA NEEDS_REVIEW
# ---------------------------------------------------------------------

def test_rsa_needs_review_has_no_confirmed_recommendation_anywhere():
    plan = _records("ecdat-pqc-migration-plan.json")
    report = _records("ecdat-migration-report.json")
    listing = {item["bom_ref"]: item for item in main.get_report_assets()["assets"]}

    for ref in _all_needs_review_refs():
        for source, record in (
            ("plan", plan[ref]["recommendation"]),
            ("report", report[ref]["recommendation"]),
            ("/api/asset", main.get_asset(ref)["recommendation"]),
            ("/api/migration-report/assets/{ref}", main.get_report_asset(ref)["recommendation"]),
        ):
            assert record["decision"] == "NEEDS_REVIEW", (source, ref)
            assert record["candidate"] is None, (source, ref)
            assert record["confirmed"] is False, (source, ref)
            assert record["selected_component"] is None, (source, ref)

        assert listing[ref]["candidate"] is None
        assert listing[ref]["recommendation"] == "NEEDS_REVIEW"

    # The ranking output for the RSA algorithms is kept, but only labelled.
    for ref in NEEDS_REVIEW_ALGORITHMS:
        ranking = report[ref]["recommendation"]["ranking_model"]
        assert ranking["candidate"] == report[ref]["ranked_candidates"][0]["candidate"] == "ML-DSA-65"
        assert "ranking model" in ranking["note"].lower()


def test_ai_context_never_gives_needs_review_a_recommended_candidate():
    for ref in _all_needs_review_refs():
        context = build_context(ref)
        pqc = context["pqc"]

        assert context["bom_ref"] == ref
        assert "recommended_candidate" not in pqc
        assert context["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
        assert context["migration_strategy"]["pqc_component"] is None

    for ref in NEEDS_REVIEW_ALGORITHMS:
        ranking = build_context(ref)["pqc"]["ranking_model_output"]
        assert ranking["top_ranked_candidate"] == "ML-DSA-65"
        assert ranking["status"] == "NOT A RECOMMENDATION"


def test_dashboard_pqc_candidate_count_excludes_needs_review_and_keep():
    report = _records("ecdat-migration-report.json")
    expected = sum(
        1 for record in report.values()
        if record["migration_strategy"]["strategy"] in ("DIRECT_PQC", "HYBRID")
        and record["migration_strategy"]["pqc_component"]
    )

    summary = main.get_summary()
    status = main.get_status()

    # The dashboard count is exactly the strategy-selected paths -- derived
    # from the data under test, not a number copied from one scan.
    assert expected > 0, "the dataset must contain at least one selected PQC path"
    assert summary["assets_with_pqc_candidates"] == status["assets_with_pqc_candidates"] == expected
    # Ranking-model candidates alone would have produced a different answer:
    # compare the sets, not their sizes, so this states the real property
    # (some ranked findings are deliberately not counted) on any dataset.
    ranked_refs = {ref for ref, record in report.items() if record["ranked_candidates"]}
    selected_refs = {
        ref for ref, record in report.items()
        if record["migration_strategy"]["strategy"] in ("DIRECT_PQC", "HYBRID")
        and record["migration_strategy"]["pqc_component"]
    }
    assert ranked_refs != selected_refs
    assert any(
        report[ref]["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
        for ref in ranked_refs
    ), "a ranked NEEDS_REVIEW finding is what this count has to exclude"
    assert summary["recommendation_distribution"].get("NEEDS_REVIEW") == len(_all_needs_review_refs())


# ---------------------------------------------------------------------
# DIRECT_PQC / HYBRID / KEEP
# ---------------------------------------------------------------------

def test_direct_pqc_x25519_keeps_its_selected_path():
    record = main.get_asset(X25519_REF)["recommendation"]
    assert (record["candidate"], record["selected_component"], record["confirmed"]) == ("ML-KEM-768", "ML-KEM-768", True)

    recommended = build_context(X25519_REF)["pqc"]["recommended_candidate"]
    assert recommended["candidate"] == "ML-KEM-768"
    assert recommended["strategy"] == "DIRECT_PQC"
    assert "ranking_model_output" not in build_context(X25519_REF)["pqc"]


def test_hybrid_dsa_keeps_its_selected_ml_dsa_path():
    record = main.get_asset(DSA_REF)["recommendation"]
    assert (record["candidate"], record["selected_component"], record["confirmed"]) == ("ML-DSA-65", "ML-DSA-65", True)

    recommended = build_context(DSA_REF)["pqc"]["recommended_candidate"]
    assert recommended["candidate"] == "ML-DSA-65"
    assert recommended["strategy"] == "HYBRID"


def test_keep_sha256_has_no_migration_recommendation():
    record = main.get_asset(SHA256_REF)["recommendation"]
    assert record["candidate"] is None
    assert record["selected_component"] is None
    assert record["confirmed"] is False
    assert record["decision"] == "NO_DIRECT_REPLACEMENT"

    pqc = build_context(SHA256_REF)["pqc"]
    assert "recommended_candidate" not in pqc
    assert "ranking_model_output" not in pqc


# ---------------------------------------------------------------------
# bom_ref isolation of the duplicate RSA-2048 findings
# ---------------------------------------------------------------------

def test_duplicate_rsa_2048_findings_remain_isolated():
    assets = _records("ecdat-assets.json")

    for ref in RSA_2048_REFS:
        other = next(r for r in RSA_2048_REFS if r != ref)
        other_files = {o["location"] for o in assets[other]["occurrences"]} - {
            o["location"] for o in assets[ref]["occurrences"]
        }

        for payload in (main.get_asset(ref), build_context(ref), main.get_report_asset(ref)):
            text = json.dumps(payload)
            assert ref in text
            assert other not in text
            assert not any(location in text for location in other_files)

        assert build_context(ref)["bom_ref"] == ref
        assert main.get_asset(ref)["recommendation"]["candidate"] is None


if __name__ == "__main__":
    test_needs_review_clears_the_candidate_but_keeps_ranking_output()
    test_direct_and_hybrid_keep_the_strategy_selected_component()
    test_keep_has_no_candidate_and_legacy_records_pass_through()
    test_rsa_needs_review_has_no_confirmed_recommendation_anywhere()
    test_ai_context_never_gives_needs_review_a_recommended_candidate()
    test_dashboard_pqc_candidate_count_excludes_needs_review_and_keep()
    test_direct_pqc_x25519_keeps_its_selected_path()
    test_hybrid_dsa_keeps_its_selected_ml_dsa_path()
    test_keep_sha256_has_no_migration_recommendation()
    test_duplicate_rsa_2048_findings_remain_isolated()

    print("All recommendation-state tests passed.")

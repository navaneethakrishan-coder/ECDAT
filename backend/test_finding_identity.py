"""Regression coverage for bom-ref identity preservation across ECDAT.

Runs against the fixture dataset (fixture_dataset.py), which is built by the
real 13-stage pipeline and deliberately contains two *different* findings
sharing the name "RSA-2048". That shape is the whole point of this file, and
reading `data/` instead made it depend on whichever repository ECDAT had
scanned last -- a scan of a repository without repeated algorithm names left
the suite asserting nothing.
"""

from collections import Counter

import fixture_dataset
from generate_migration_report import index_by_asset


PIPELINE_FILES = (
    "ecdat-explainable-risk.json",
    "ecdat-blast-radius.json",
    "ecdat-migration-complexity.json",
    "ecdat-migration-priority.json",
    "ecdat-pqc-migration.json",
    "ecdat-pqc-ranked.json",
    "ecdat-pqc-migration-plan.json",
    "ecdat-migration-actions.json",
    "ecdat-migration-report.json",
)


def load_assets(filename):
    return fixture_dataset.load(filename)["assets"]


def finding_id(record):
    return record.get("bom_ref") or record.get("asset_ref")


def test_duplicate_algorithm_names_do_not_overwrite_each_other():
    source_assets = load_assets("ecdat-assets.json")
    source_ids = {item["bom_ref"] for item in source_assets}
    duplicate_names = {
        name
        for name, count in Counter(item["name"] for item in source_assets).items()
        if count > 1
    }

    assert duplicate_names == {"RSA-2048"}, (
        "The fixture is built around two distinct RSA-2048 findings; without them "
        "this file cannot test identity preservation at all."
    )
    assert len(source_ids) == len(source_assets), "Ingestion must merge only exact bom-ref duplicates."

    for filename in PIPELINE_FILES:
        assets = load_assets(filename)
        ids = {finding_id(item) for item in assets}
        assert len(assets) == len(source_assets), filename
        assert ids == source_ids, filename

    report_assets = load_assets("ecdat-migration-report.json")
    for name in duplicate_names:
        source_matches = [item for item in source_assets if item["name"] == name]
        report_matches = [item for item in report_assets if item["asset"] == name]
        assert {item["bom_ref"] for item in report_matches} == {
            item["bom_ref"] for item in source_matches
        }


def test_report_index_uses_bom_ref_not_algorithm_name():
    records = [
        {"name": "RSA-2048", "bom_ref": "finding-a"},
        {"name": "RSA-2048", "bom_ref": "finding-b"},
    ]

    indexed = index_by_asset({"assets": records})

    assert set(indexed) == {"finding-a", "finding-b"}
    assert indexed["finding-a"] is records[0]
    assert indexed["finding-b"] is records[1]


def test_every_stage_joins_upstream_values_by_its_own_bom_ref():
    # Regression: generate_migration_complexity.py once reused a stale
    # bom_ref loop variable, so every finding's complexity was computed
    # from the last finding's risk and blast records.
    def by_ref(filename):
        return {finding_id(item): item for item in load_assets(filename)}

    sources = by_ref("ecdat-assets.json")
    risk = by_ref("ecdat-explainable-risk.json")
    blast = by_ref("ecdat-blast-radius.json")
    complexity = by_ref("ecdat-migration-complexity.json")
    priority = by_ref("ecdat-migration-priority.json")
    ranked = by_ref("ecdat-pqc-ranked.json")

    for ref, source in sources.items():
        classification = risk[ref]["classification"]
        final_score = risk[ref]["risk_assessment"]["final_score"]
        context = complexity[ref]["context"]

        assert context["category"] == classification["category"], ref
        assert context["purpose"] == classification["purpose"], ref
        assert context["quantum_status"] == classification["quantum_status"], ref
        assert context["evidence_count"] == len(source["occurrences"]), ref
        assert context["direct_dependents"] == blast[ref]["direct_dependents"]["count"], ref

        assert blast[ref]["risk"]["score"] == final_score, ref
        assert priority[ref]["quantum_risk"]["score"] == final_score, ref
        assert priority[ref]["blast_radius"]["score"] == blast[ref]["blast_radius_score"], ref
        assert priority[ref]["migration_complexity"]["score"] == complexity[ref]["score"], ref
        assert ranked[ref]["current_context"]["migration_complexity"] == complexity[ref]["score"], ref
        assert ranked[ref]["current_context"]["migration_priority"] == (
            priority[ref]["migration_priority"]["priority_score"]
        ), ref


if __name__ == "__main__":
    test_duplicate_algorithm_names_do_not_overwrite_each_other()
    test_report_index_uses_bom_ref_not_algorithm_name()
    test_every_stage_joins_upstream_values_by_its_own_bom_ref()
    print("All finding-identity tests passed.")

"""Regression coverage for bom-ref identity preservation across ECDAT."""

import json
from collections import Counter
from pathlib import Path

from generate_migration_report import index_by_asset


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)["assets"]


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

    assert duplicate_names, "The fixture must contain repeated algorithm names."
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


if __name__ == "__main__":
    test_duplicate_algorithm_names_do_not_overwrite_each_other()
    test_report_index_uses_bom_ref_not_algorithm_name()
    print("All finding-identity tests passed.")

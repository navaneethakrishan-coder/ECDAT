"""CBOM validation and normalization between the scanner and the pipeline."""

import json
from pathlib import Path

from services.scanning.validation import normalize_cbom, validate_cbom

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def crypto_component(ref, asset_type="algorithm"):
    return {"bom-ref": ref, "name": ref, "cryptoProperties": {"assetType": asset_type}}


def test_the_real_scanned_cbom_validates():
    with (DATA_DIR / "keycloak-cbom.json").open(encoding="utf-8") as file:
        cbom = json.load(file)

    report = validate_cbom(cbom)

    assert report["ok"], report["errors"]
    assert report["stats"]["crypto_components"] > 0
    # Findings are unique bom_refs, which is what the dashboard shows.
    assert report["stats"]["findings"] == 30
    # CBOMKit repeats identical entries; findings are keyed by bom_ref.
    assert report["stats"]["unique_bom_refs"] <= report["stats"]["components"]
    assert report["stats"]["unique_bom_refs"] == 30


def test_repeated_identical_entries_are_normal_but_conflicting_refs_are_rejected():
    # CBOMKit repeats a component entry verbatim per observation.
    repeated = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [crypto_component("same"), crypto_component("same")],
    }
    report = validate_cbom(repeated)
    assert report["ok"], report["errors"]
    assert "repeated-component-entry" in {warning["code"] for warning in report["warnings"]}
    assert report["stats"]["unique_bom_refs"] == 1

    # Two different findings may never share one bom_ref.
    conflicting = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [crypto_component("same"), crypto_component("same", asset_type="certificate")],
    }
    codes = {error["code"] for error in validate_cbom(conflicting)["errors"]}
    assert "conflicting-bom-ref" in codes

def test_missing_bom_refs_are_rejected():
    missing = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"name": "no ref", "cryptoProperties": {"assetType": "algorithm"}}],
    }
    codes = {error["code"] for error in validate_cbom(missing)["errors"]}
    assert "missing-bom-ref" in codes


def test_a_cbom_without_cryptography_fails_instead_of_producing_an_empty_dashboard():
    report = validate_cbom(
        {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [{"bom-ref": "a", "name": "lib"}]}
    )
    assert not report["ok"]
    assert {error["code"] for error in report["errors"]} == {"no-crypto-components"}


def test_wrong_format_and_shape_are_rejected():
    assert not validate_cbom("not a cbom")["ok"]
    assert "unsupported-bom-format" in {
        error["code"] for error in validate_cbom({"bomFormat": "SPDX", "components": []})["errors"]
    }
    assert "missing-components" in {
        error["code"] for error in validate_cbom({"bomFormat": "CycloneDX"})["errors"]
    }


def test_dangling_dependency_refs_warn_but_do_not_fabricate_relationships():
    cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [crypto_component("a")],
        "dependencies": [{"ref": "a", "dependsOn": ["ghost"]}],
    }
    report = validate_cbom(cbom)

    assert report["ok"], report["errors"]
    assert "dangling-dependency-ref" in {warning["code"] for warning in report["warnings"]}
    assert report["stats"]["dependency_edges"] == 1

    normalized, _ = normalize_cbom(cbom)
    assert normalized["dependencies"] == cbom["dependencies"]


def test_normalization_only_adds_missing_containers():
    cbom = {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [crypto_component("a")]}
    normalized, notes = normalize_cbom(cbom)

    assert normalized["components"] == cbom["components"]
    assert normalized["dependencies"] == []
    assert len(notes) == 1

    # The scanner's document is never mutated in place.
    assert "dependencies" not in cbom

    unchanged, notes = normalize_cbom({**cbom, "dependencies": []})
    assert notes == []
    assert unchanged["components"] == cbom["components"]


def test_stats_count_what_the_cbom_actually_contains():
    cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [
            crypto_component("a", "algorithm"),
            crypto_component("b", "related-crypto-material"),
            {"bom-ref": "c", "name": "plain library"},
        ],
        "dependencies": [{"ref": "a", "dependsOn": ["b", "c"]}],
    }
    stats = validate_cbom(cbom)["stats"]

    assert stats == {
        "components": 3,
        "crypto_components": 2,
        "findings": 2,
        "dependency_entries": 1,
        "dependency_edges": 2,
        "unique_bom_refs": 3,
        "asset_types": {"algorithm": 1, "related-crypto-material": 1},
    }


if __name__ == "__main__":
    test_the_real_scanned_cbom_validates()
    test_repeated_identical_entries_are_normal_but_conflicting_refs_are_rejected()
    test_missing_bom_refs_are_rejected()
    test_a_cbom_without_cryptography_fails_instead_of_producing_an_empty_dashboard()
    test_wrong_format_and_shape_are_rejected()
    test_dangling_dependency_refs_warn_but_do_not_fabricate_relationships()
    test_normalization_only_adds_missing_containers()
    test_stats_count_what_the_cbom_actually_contains()
    print("All CBOM validation tests passed.")

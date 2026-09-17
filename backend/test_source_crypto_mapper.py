import json

from services.source_crypto_mapper import (
    map_asset_source_usage,
    map_assets_to_source,
    summarize_source_mapping,
)


# Fixture findings in the current CBOM (pyca/cryptography scan), addressed
# by bom_ref -- the canonical finding identity -- never by algorithm name.
X25519_REF = "a4c88095-ebd8-41ab-8acd-2b1e6b55fc3c"  # key agreement, 2 occurrences in 1 file


def load_assets():
    with open(
        "../data/ecdat-explainable-risk.json",
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data["assets"]


def test_single_asset():
    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["bom_ref"] == X25519_REF
    )

    result = map_asset_source_usage(asset)

    assert result["asset"] == asset["name"]
    assert result["bom_ref"] == X25519_REF

    assert (
        result["classification"]["category"]
        == "asymmetric"
    )

    assert (
        "key-agreement"
        in result["classification"]["purpose"]
    )

    assert result["evidence_count"] == 2

    assert result["affected_file_count"] == 1

    assert (
        result["migration_surface"]
        == "MEDIUM"
    )

    assert len(result["source_usage"]) == 2

    for usage in result["source_usage"]:
        assert usage["file"]
        assert usage["line"] is not None
        assert usage["context"]


def test_key_agreement_detection():
    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["bom_ref"] == X25519_REF
    )

    result = map_asset_source_usage(asset)

    usages = {
        item["usage"]
        for item in result["source_usage"]
    }

    assert "key-agreement" in usages


def test_all_assets():
    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    assert len(mappings) == len(assets)

    for mapping in mappings:
        assert "asset" in mapping
        assert "source_usage" in mapping
        assert "evidence_count" in mapping
        assert "affected_files" in mapping
        assert "migration_surface" in mapping


def test_summary():
    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    summary = summarize_source_mapping(
        mappings
    )

    assert summary["total_assets"] == len(assets)

    assert (
        summary["assets_with_source_evidence"]
        > 0
    )

    assert (
        summary["total_evidence_locations"]
        > 0
    )

    assert (
        summary["unique_source_files"]
        > 0
    )


def test_empty_asset():
    result = map_asset_source_usage(
        {
            "name": "TEST",
            "classification": {},
        }
    )

    assert result["asset"] == "TEST"

    assert result["evidence_count"] == 0

    assert (
        result["affected_file_count"]
        == 0
    )

    assert (
        result["migration_surface"]
        == "UNKNOWN"
    )


def test_source_mapping():
    print("================================")
    print("SOURCE-TO-CRYPTO MAPPING TEST")
    print("================================")

    print(
        "Running key-agreement source mapping...",
        end=" ",
    )
    test_single_asset()
    print("PASSED")

    print(
        "Running key-agreement detection...",
        end=" ",
    )
    test_key_agreement_detection()
    print("PASSED")

    print(
        "Running all asset mapping...",
        end=" ",
    )
    test_all_assets()
    print("PASSED")

    print(
        "Running mapping summary...",
        end=" ",
    )
    test_summary()
    print("PASSED")

    print(
        "Running empty asset handling...",
        end=" ",
    )
    test_empty_asset()
    print("PASSED")

    print()
    print(
        "================================"
    )
    print(
        "SOURCE-TO-CRYPTO MAPPING TEST PASSED"
    )
    print(
        "================================"
    )


if __name__ == "__main__":
    test_source_mapping()

import json

from services.source_crypto_mapper import (
    map_assets_to_source,
)

from services.source_impact_analyzer import (
    analyze_source_usage,
    analyze_all_source_usage,
    summarize_source_impact,
)


# Fixture findings in the current CBOM (pyca/cryptography scan), addressed
# by bom_ref -- the canonical finding identity -- never by algorithm name.
X25519_REF = "a4c88095-ebd8-41ab-8acd-2b1e6b55fc3c"    # key agreement, 2 occurrences in 1 file
RSA_2048_REF = "e87e3bf2-5f46-477d-b159-8ac582608a25"  # Java KeyFactory#getInstance context


def load_assets():
    with open(
        "../data/ecdat-explainable-risk.json",
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data["assets"]


def test_echd_source_impact():

    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["bom_ref"] == X25519_REF
    )

    mappings = map_assets_to_source(
        [asset]
    )

    result = analyze_source_usage(
        mappings[0]
    )

    assert result["asset"] == asset["name"]
    assert result["bom_ref"] == X25519_REF

    assert (
        result["affected_file_count"]
        == 1
    )

    assert (
        result["source_location_count"]
        == 2
    )

    assert (
        result["impact_level"]
        == "HIGH"
    )

    assert len(
        result["affected_files"]
    ) == 1


def test_api_function_detection():

    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["bom_ref"] == RSA_2048_REF
    )

    mappings = map_assets_to_source(
        [asset]
    )

    result = analyze_source_usage(
        mappings[0]
    )

    functions = (
        result["affected_functions"]
    )

    assert (
        "getInstance"
        in functions
    )


def test_all_assets():

    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    analyses = analyze_all_source_usage(
        mappings
    )

    assert len(analyses) == len(assets)

    for analysis in analyses:

        assert "asset" in analysis

        assert (
            "affected_files"
            in analysis
        )

        assert (
            "affected_classes"
            in analysis
        )

        assert (
            "affected_functions"
            in analysis
        )

        assert (
            "impact_level"
            in analysis
        )


def test_summary():

    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    analyses = analyze_all_source_usage(
        mappings
    )

    summary = summarize_source_impact(
        analyses
    )

    assert (
        summary["total_assets"]
        == len(assets)
    )

    assert (
        summary[
            "unique_affected_files"
        ]
        > 0
    )

    assert (
        summary[
            "assets_with_affected_files"
        ]
        > 0
    )


def test_empty_mapping():

    result = analyze_source_usage(
        {
            "asset": "TEST",
            "classification": {},
            "source_usage": [],
        }
    )

    assert (
        result["asset"]
        == "TEST"
    )

    assert (
        result["affected_file_count"]
        == 0
    )

    assert (
        result["affected_function_count"]
        == 0
    )

    assert (
        result["impact_level"]
        == "UNKNOWN"
    )


def test_source_impact():

    print(
        "================================"
    )

    print(
        "SOURCE IMPACT ANALYSIS TEST"
    )

    print(
        "================================"
    )

    print(
        "Running key-agreement source impact...",
        end=" ",
    )

    test_echd_source_impact()

    print("PASSED")

    print(
        "Running function detection...",
        end=" ",
    )

    test_api_function_detection()

    print("PASSED")

    print(
        "Running all asset analysis...",
        end=" ",
    )

    test_all_assets()

    print("PASSED")

    print(
        "Running impact summary...",
        end=" ",
    )

    test_summary()

    print("PASSED")

    print(
        "Running empty mapping...",
        end=" ",
    )

    test_empty_mapping()

    print("PASSED")

    print()

    print(
        "================================"
    )

    print(
        "SOURCE IMPACT ANALYSIS TEST PASSED"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    test_source_impact()

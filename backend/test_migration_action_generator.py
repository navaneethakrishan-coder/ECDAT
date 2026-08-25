import json

from services.source_crypto_mapper import (
    map_assets_to_source,
)

from services.source_impact_analyzer import (
    analyze_all_source_usage,
)

from services.migration_action_generator import (
    generate_migration_actions,
    generate_all_migration_actions,
    summarize_migration_actions,
)


def load_json(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_assets():
    data = load_json(
        "../data/ecdat-explainable-risk.json"
    )

    return data["assets"]


def load_migration():
    data = load_json(
        "../data/ecdat-pqc-migration-plan.json"
    )

    return data["assets"]


def test_echd_actions():

    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["name"] == "ECDH"
    )

    mappings = map_assets_to_source(
        [asset]
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migrations = load_migration()

    migration = next(
        item
        for item in migrations
        if item["asset"] == "ECDH"
    )

    result = generate_migration_actions(
        mappings[0],
        impacts[0],
        migration,
    )

    assert (
        result["asset"]
        == "ECDH"
    )

    assert (
        result["pqc_candidate"]
        == "ML-KEM-768"
    )

    assert (
        result["pqc_family"]
        == "KEM"
    )

    assert (
        result["affected_file_count"]
        == 2
    )

    assert (
        result["action_count"]
        > 0
    )

    actions = [
        item["action"]
        for item in result["actions"]
    ]

    assert any(
        "key-establishment"
        in action.lower()
        for action in actions
    )

    assert any(
        "ML-KEM-768"
        in action
        for action in actions
    )


def test_architectural_migration():

    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["name"] == "EC"
    )

    mappings = map_assets_to_source(
        [asset]
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migrations = load_migration()

    migration = next(
        item
        for item in migrations
        if item["asset"] == "EC"
    )

    result = generate_migration_actions(
        mappings[0],
        impacts[0],
        migration,
    )

    assert (
        result["migration_type"]
        == "architectural-migration"
    )

    actions = [
        item["action"]
        for item in result["actions"]
    ]

    assert any(
        "architectural"
        in action.lower()
        for action in actions
    )

    assert any(
        "blind direct"
        in action.lower()
        for action in actions
    )


def test_signature_migration():

    assets = load_assets()

    asset = next(
        item
        for item in assets
        if item["name"] == "RSA-2048"
    )

    mappings = map_assets_to_source(
        [asset]
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migrations = load_migration()

    migration = next(
        item
        for item in migrations
        if item["asset"] == "RSA-2048"
    )

    result = generate_migration_actions(
        mappings[0],
        impacts[0],
        migration,
    )

    assert (
        result["pqc_candidate"]
        == "ML-DSA-65"
    )

    actions = [
        item["action"]
        for item in result["actions"]
    ]

    assert any(
        "digital-signature"
        in action.lower()
        for action in actions
    )

    assert any(
        "ML-DSA-65"
        in action
        for action in actions
    )


def test_all_assets():

    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migrations = load_migration()

    results = generate_all_migration_actions(
        mappings,
        impacts,
        migrations,
    )

    assert (
        len(results)
        == 59
    )

    for result in results:

        assert "asset" in result

        assert (
            "actions"
            in result
        )

        assert (
            "action_count"
            in result
        )

        assert (
            result["action_count"]
            > 0
        )


def test_summary():

    assets = load_assets()

    mappings = map_assets_to_source(
        assets
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migrations = load_migration()

    results = generate_all_migration_actions(
        mappings,
        impacts,
        migrations,
    )

    summary = summarize_migration_actions(
        results
    )

    assert (
        summary["total_assets"]
        == 59
    )

    assert (
        summary[
            "total_migration_actions"
        ]
        > 0
    )

    assert (
        summary[
            "assets_with_pqc_candidates"
        ]
        > 0
    )


def test_empty_inputs():

    result = generate_migration_actions(
        {
            "asset": "TEST",
            "classification": {},
            "source_usage": [],
        },
        {
            "asset": "TEST",
            "affected_files": [],
            "affected_classes": [],
            "affected_functions": [],
            "impact_level": "UNKNOWN",
        },
        {
            "asset": "TEST",
            "migration_type": None,
            "ranked_candidates": [],
        },
    )

    assert (
        result["asset"]
        == "TEST"
    )

    assert (
        result["pqc_candidate"]
        is None
    )

    assert (
        result["action_count"]
        > 0
    )


def test_migration_actions():

    print(
        "================================"
    )

    print(
        "MIGRATION ACTION GENERATOR TEST"
    )

    print(
        "================================"
    )

    print(
        "Running ECDH actions...",
        end=" ",
    )

    test_echd_actions()

    print("PASSED")

    print(
        "Running EC architectural actions...",
        end=" ",
    )

    test_architectural_migration()

    print("PASSED")

    print(
        "Running RSA signature actions...",
        end=" ",
    )

    test_signature_migration()

    print("PASSED")

    print(
        "Running all asset actions...",
        end=" ",
    )

    test_all_assets()

    print("PASSED")

    print(
        "Running action summary...",
        end=" ",
    )

    test_summary()

    print("PASSED")

    print(
        "Running empty input handling...",
        end=" ",
    )

    test_empty_inputs()

    print("PASSED")

    print()

    print(
        "================================"
    )

    print(
        "MIGRATION ACTION GENERATOR TEST PASSED"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    test_migration_actions()


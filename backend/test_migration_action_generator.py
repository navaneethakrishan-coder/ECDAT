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


# Fixture findings in the current CBOM (pyca/cryptography scan), addressed
# by bom_ref -- the canonical finding identity -- never by algorithm name.
X25519_REF = "a4c88095-ebd8-41ab-8acd-2b1e6b55fc3c"          # key agreement, DIRECT_PQC
DSA_REF = "f3bf7d4c-7f24-46db-b416-0a30e8b487ea"             # digital signature, HYBRID
DSA_PUBLIC_KEY_REF = "1da1d50f-f071-451b-bcc2-4de220801c61"  # key material, architectural-migration
RSA_2048_REF = "e87e3bf2-5f46-477d-b159-8ac582608a25"        # ambiguous purpose, NEEDS_REVIEW


def _actions_for(bom_ref, strip_strategy=False):
    asset = next(
        item
        for item in load_assets()
        if item["bom_ref"] == bom_ref
    )

    mappings = map_assets_to_source(
        [asset]
    )

    impacts = analyze_all_source_usage(
        mappings
    )

    migration = dict(next(
        item
        for item in load_migration()
        if item["bom_ref"] == bom_ref
    ))

    if strip_strategy:
        migration.pop("migration_strategy", None)

    return asset, generate_migration_actions(
        mappings[0],
        impacts[0],
        migration,
    )


def test_echd_actions():

    asset, result = _actions_for(X25519_REF)

    assert (
        result["asset"]
        == asset["name"]
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
        == 1
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

    # Architectural-migration key material follows its purpose-aware
    # strategy (HYBRID, inherited from DSA) ...
    _, result = _actions_for(DSA_PUBLIC_KEY_REF)

    assert (
        result["migration_type"]
        == "architectural-migration"
    )

    assert result["pqc_candidate"] == "ML-DSA-65"

    actions = [
        item["action"]
        for item in result["actions"]
    ]

    assert any(
        "hybrid"
        in action.lower()
        for action in actions
    )

    # ... and without a strategy the legacy path still refuses a blind
    # direct replacement.
    _, legacy = _actions_for(DSA_PUBLIC_KEY_REF, strip_strategy=True)

    legacy_actions = [
        item["action"]
        for item in legacy["actions"]
    ]

    assert any(
        "architectural"
        in action.lower()
        for action in legacy_actions
    )

    assert any(
        "blind direct"
        in action.lower()
        for action in legacy_actions
    )


def test_signature_migration():

    _, result = _actions_for(DSA_REF)

    assert (
        result["pqc_candidate"]
        == "ML-DSA-65"
    )

    actions = [
        item["action"]
        for item in result["actions"]
    ]

    assert any(
        "signature"
        in action.lower()
        for action in actions
    )

    assert any(
        "ML-DSA-65"
        in action
        for action in actions
    )

    # An RSA-2048 finding whose evidence leaves its role ambiguous is
    # NEEDS_REVIEW: no candidate is selected and no replacement is
    # instructed until the review is resolved.
    _, review = _actions_for(RSA_2048_REF)

    assert review["pqc_candidate"] is None
    assert review["migration_strategy"] == "NEEDS_REVIEW"
    assert "review is resolved" in review["actions"][0]["action"]


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
        == 30
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
        == 30
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
        "Running key-agreement actions...",
        end=" ",
    )

    test_echd_actions()

    print("PASSED")

    print(
        "Running architectural actions...",
        end=" ",
    )

    test_architectural_migration()

    print("PASSED")

    print(
        "Running signature and review actions...",
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


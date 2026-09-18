import fixture_dataset


# Findings come from the fixture dataset (fixture_dataset.py), not from
# data/, so this test says the same thing whatever ECDAT last scanned.
EXPECTED_ASSETS = fixture_dataset.expected_assets()

# Addressed by bom_ref -- the canonical finding identity -- never by name.
X25519_REF = fixture_dataset.ref("x25519")                  # key agreement, DIRECT_PQC
DSA_REF = fixture_dataset.ref("dsa")                        # digital signature, HYBRID
DSA_PUBLIC_KEY_REF = fixture_dataset.ref("dsa_public_key")  # key material, inherits its strategy
RSA_2048_REF = fixture_dataset.ref("rsa2048_java")          # ambiguous purpose, NEEDS_REVIEW

MIGRATING_STRATEGIES = {"DIRECT_PQC", "HYBRID"}

VALID_MIGRATION_TYPES = {
    "pqc-candidate",
    "no-direct-pqc-replacement",
    "architectural-migration",
}

VALID_IMPACT_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    "UNKNOWN",
}


def load_data():
    return fixture_dataset.load("ecdat-migration-actions.json")


def test_total_assets(data):
    assert len(data["assets"]) == EXPECTED_ASSETS


def test_unique_assets(data):
    # Findings are unique by bom_ref; algorithm names legitimately repeat
    # (e.g. two distinct RSA-2048 findings).
    refs = [asset["bom_ref"] for asset in data["assets"]]

    assert all(refs)
    assert len(refs) == len(set(refs))


def _asset(data, bom_ref):
    return next(
        item
        for item in data["assets"]
        if item["bom_ref"] == bom_ref
    )


def test_migration_types(data):
    for asset in data["assets"]:
        migration_type = asset["migration_type"]

        assert migration_type in VALID_MIGRATION_TYPES


def test_action_structure(data):
    for asset in data["assets"]:

        assert isinstance(asset["actions"], list)
        assert asset["action_count"] == len(asset["actions"])
        assert asset["action_count"] > 0

        for index, action in enumerate(
            asset["actions"],
            start=1,
        ):
            assert isinstance(action, dict)

            assert action["step"] == index

            assert isinstance(
                action["action"],
                str,
            )

            assert action["action"].strip() != ""


def test_candidate_consistency(data):
    pqc_count = 0

    for asset in data["assets"]:

        candidate = asset["pqc_candidate"]
        migration_type = asset["migration_type"]

        if candidate:
            pqc_count += 1

            assert migration_type in {
                "pqc-candidate",
                "architectural-migration",
            }

            assert asset["pqc_family"] is not None

        # The purpose-aware strategy decides whether a PQC component is
        # selected: only DIRECT_PQC / HYBRID ever carry one.
        assert bool(candidate) == (
            asset["migration_strategy"] in MIGRATING_STRATEGIES
        )

    assert pqc_count == sum(
        1
        for asset in data["assets"]
        if asset["migration_strategy"] in MIGRATING_STRATEGIES
    )


def test_ecd_h_validation(data):
    asset = _asset(data, X25519_REF)

    assert asset["migration_type"] == "pqc-candidate"
    assert asset["pqc_candidate"] == "ML-KEM-768"
    assert asset["pqc_family"] == "KEM"

    actions = [
        item["action"].lower()
        for item in asset["actions"]
    ]

    assert any(
        "key-establishment" in action
        for action in actions
    )

    assert any(
        "key-agreement" in action
        for action in actions
    )

    assert any(
        "pqc kem" in action
        for action in actions
    )

    assert any(
        "ml-kem-768" in action
        for action in actions
    )


def test_ec_architectural_validation(data):
    asset = _asset(data, DSA_PUBLIC_KEY_REF)

    assert asset["migration_type"] == "architectural-migration"

    # Key material follows the HYBRID strategy of the algorithm it
    # belongs to (DSA).
    assert asset["migration_strategy"] == "HYBRID"
    assert asset["pqc_candidate"] == "ML-DSA-65"

    actions = [
        item["action"].lower()
        for item in asset["actions"]
    ]

    assert any(
        "hybrid" in action
        for action in actions
    )

    assert any(
        "affected source files" in action
        for action in actions
    )


def test_rsa_signature_validation(data):
    asset = _asset(data, DSA_REF)

    assert asset["migration_type"] == "pqc-candidate"
    assert asset["pqc_candidate"] == "ML-DSA-65"

    actions = [
        item["action"].lower()
        for item in asset["actions"]
    ]

    assert any(
        "signature" in action
        for action in actions
    )

    assert any(
        "ml-dsa-65" in action
        for action in actions
    )

    # An RSA-2048 finding with ambiguous purpose evidence is NEEDS_REVIEW:
    # no candidate, and both possible roles are named for the reviewer.
    review = _asset(data, RSA_2048_REF)

    assert review["migration_type"] == "pqc-candidate"
    assert review["migration_strategy"] == "NEEDS_REVIEW"
    assert review["pqc_candidate"] is None

    review_actions = [
        item["action"].lower()
        for item in review["actions"]
    ]

    assert "review is resolved" in review_actions[0]
    assert any("digital signature" in action for action in review_actions)
    assert any("public-key encryption" in action for action in review_actions)


def test_no_direct_replacement(data):
    no_direct_assets = [
        asset
        for asset in data["assets"]
        if asset["migration_type"]
        == "no-direct-pqc-replacement"
    ]

    assert len(no_direct_assets) == data["summary"][
        "migration_type_distribution"
    ].get("no-direct-pqc-replacement", 0)

    for asset in no_direct_assets:
        assert asset["pqc_candidate"] is None

        actions = [
            item["action"].lower()
            for item in asset["actions"]
        ]

        assert any(
            "no direct" in action
            or "blind direct replacement" in action
            or "no post-quantum algorithm replacement" in action
            for action in actions
        )


def test_impact_levels(data):
    for asset in data["assets"]:
        assert (
            asset["impact_level"]
            in VALID_IMPACT_LEVELS
        )


def test_action_count_summary(data):
    calculated_total = sum(
        asset["action_count"]
        for asset in data["assets"]
    )

    assert (
        calculated_total
        == data["summary"]["total_migration_actions"]
    )


def test_candidate_summary(data):
    calculated_candidates = sum(
        1
        for asset in data["assets"]
        if asset["pqc_candidate"]
    )

    assert (
        calculated_candidates
        == data["summary"]["assets_with_pqc_candidates"]
    )


def test_summary_asset_count(data):
    assert (
        data["summary"]["total_assets"]
        == len(data["assets"])
    )


def test_no_empty_actions(data):
    for asset in data["assets"]:
        for action in asset["actions"]:
            assert action["action"].strip()


def run_test(name, function, data):
    print(
        f"Running {name}...",
        end=" ",
    )

    function(data)

    print("PASSED")


def main():

    print("================================")
    print("MIGRATION ACTION VALIDATION TEST")
    print("================================")

    data = load_data()

    run_test(
        "total asset validation",
        test_total_assets,
        data,
    )

    run_test(
        "unique asset validation",
        test_unique_assets,
        data,
    )

    run_test(
        "migration type validation",
        test_migration_types,
        data,
    )

    run_test(
        "action structure validation",
        test_action_structure,
        data,
    )

    run_test(
        "candidate consistency validation",
        test_candidate_consistency,
        data,
    )

    run_test(
        "key-agreement validation",
        test_ecd_h_validation,
        data,
    )

    run_test(
        "key-material architectural validation",
        test_ec_architectural_validation,
        data,
    )

    run_test(
        "signature and review validation",
        test_rsa_signature_validation,
        data,
    )

    run_test(
        "no-direct-replacement validation",
        test_no_direct_replacement,
        data,
    )

    run_test(
        "impact-level validation",
        test_impact_levels,
        data,
    )

    run_test(
        "action-count validation",
        test_action_count_summary,
        data,
    )

    run_test(
        "candidate-summary validation",
        test_candidate_summary,
        data,
    )

    run_test(
        "summary asset-count validation",
        test_summary_asset_count,
        data,
    )

    run_test(
        "empty-action validation",
        test_no_empty_actions,
        data,
    )

    print()
    print("================================")
    print("MIGRATION ACTION VALIDATION PASSED")
    print("================================")


if __name__ == "__main__":
    main()

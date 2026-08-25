import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR.parent / "data" / "ecdat-migration-actions.json"


EXPECTED_ASSETS = 59
EXPECTED_PQC_CANDIDATES = 14

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
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_total_assets(data):
    assert len(data["assets"]) == EXPECTED_ASSETS


def test_unique_assets(data):
    names = [asset["asset"] for asset in data["assets"]]

    assert len(names) == len(set(names))


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

        if migration_type == "pqc-candidate":
            assert candidate is not None

    assert pqc_count == EXPECTED_PQC_CANDIDATES


def test_ecd_h_validation(data):
    asset = next(
        item
        for item in data["assets"]
        if item["asset"] == "ECDH"
    )

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
    asset = next(
        item
        for item in data["assets"]
        if item["asset"] == "EC"
    )

    assert asset["migration_type"] == "architectural-migration"

    actions = [
        item["action"].lower()
        for item in asset["actions"]
    ]

    assert any(
        "architectural" in action
        for action in actions
    )

    assert any(
        "source usage" in action
        for action in actions
    )


def test_rsa_signature_validation(data):
    asset = next(
        item
        for item in data["assets"]
        if item["asset"] == "RSA-2048"
    )

    assert asset["migration_type"] == "pqc-candidate"
    assert asset["pqc_candidate"] == "ML-DSA-65"

    actions = [
        item["action"].lower()
        for item in asset["actions"]
    ]

    assert any(
        "digital-signature" in action
        for action in actions
    )

    assert any(
        "ml-dsa-65" in action
        for action in actions
    )


def test_no_direct_replacement(data):
    no_direct_assets = [
        asset
        for asset in data["assets"]
        if asset["migration_type"]
        == "no-direct-pqc-replacement"
    ]

    assert len(no_direct_assets) == 16

    for asset in no_direct_assets:
        assert asset["pqc_candidate"] is None

        actions = [
            item["action"].lower()
            for item in asset["actions"]
        ]

        assert any(
            "no direct" in action
            or "blind direct replacement" in action
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
        "ECDH validation",
        test_ecd_h_validation,
        data,
    )

    run_test(
        "EC architectural validation",
        test_ec_architectural_validation,
        data,
    )

    run_test(
        "RSA signature validation",
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
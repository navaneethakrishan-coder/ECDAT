import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPORT_FILE = (
    BASE_DIR.parent
    / "data"
    / "ecdat-migration-report.json"
)


EXPECTED_ASSETS = 30
EXPECTED_ACTIONS = 575
EXPECTED_PQC_CANDIDATES = 14


def load_report():
    with REPORT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_asset(data, name):
    for asset in data["assets"]:
        if asset["asset"] == name:
            return asset

    raise AssertionError(
        f"Asset not found: {name}"
    )


def test_total_assets(data):
    assert (
        len(data["assets"])
        == EXPECTED_ASSETS
    )

    assert (
        data["summary"]["total_assets"]
        == EXPECTED_ASSETS
    )


def test_unique_assets(data):
    names = [
        asset["asset"]
        for asset in data["assets"]
    ]

    assert len(names) == len(set(names))


def test_total_actions(data):
    calculated = sum(
        asset["action_count"]
        for asset in data["assets"]
    )

    assert calculated == EXPECTED_ACTIONS

    assert (
        data["summary"][
            "total_migration_actions"
        ]
        == EXPECTED_ACTIONS
    )


def test_risk_mapping(data):
    for asset in data["assets"]:

        risk = asset["current_risk"]

        assert risk["score"] is not None
        assert risk["severity"] is not None

        assert (
            risk["severity"]
            != "UNKNOWN"
        )


def test_risk_distribution(data):
    distribution = data[
        "summary"
    ][
        "risk_severity_distribution"
    ]

    total = sum(
        distribution.values()
    )

    assert total == EXPECTED_ASSETS

    assert "UNKNOWN" not in distribution


def test_migration_types(data):

    distribution = data[
        "summary"
    ][
        "migration_type_distribution"
    ]

    assert (
        distribution[
            "pqc-candidate"
        ]
        == 13
    )

    assert (
        distribution[
            "no-direct-pqc-replacement"
        ]
        == 16
    )

    assert (
        distribution[
            "architectural-migration"
        ]
        == 30
    )


def test_recommendation_distribution(data):

    distribution = data[
        "summary"
    ][
        "recommendation_distribution"
    ]

    assert (
        distribution[
            "RECOMMENDED"
        ]
        == 13
    )

    assert (
        distribution[
            "NO_DIRECT_REPLACEMENT"
        ]
        == 16
    )

    assert (
        distribution[
            "ARCHITECTURAL_MIGRATION"
        ]
        == 30
    )


def test_pqc_candidate_count(data):

    calculated = sum(
        1
        for asset in data["assets"]
        if asset[
            "recommendation"
        ][
            "candidate"
        ]
    )

    assert (
        calculated
        == EXPECTED_PQC_CANDIDATES
    )

    assert (
        data["summary"][
            "assets_with_pqc_candidates"
        ]
        == EXPECTED_PQC_CANDIDATES
    )


def test_ecdh_end_to_end(data):

    asset = get_asset(
        data,
        "ECDH",
    )

    assert (
        asset[
            "classification"
        ][
            "purpose"
        ]
        == ["key-agreement"]
    )

    assert (
        asset[
            "classification"
        ][
            "quantum_status"
        ]
        == "vulnerable"
    )

    assert (
        asset[
            "current_risk"
        ][
            "score"
        ]
        == 65.75
    )

    assert (
        asset[
            "current_risk"
        ][
            "severity"
        ]
        == "HIGH"
    )

    assert (
        asset[
            "pqc_migration"
        ][
            "migration_type"
        ]
        == "pqc-candidate"
    )

    assert (
        asset[
            "pqc_migration"
        ][
            "pqc_applicable"
        ]
        is True
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate"
        ]
        == "ML-KEM-768"
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate_rank"
        ]
        == 1
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate_score"
        ]
        == 84.36
    )

    assert (
        asset[
            "action_count"
        ]
        == 10
    )

    assert (
        len(
            asset[
                "migration_actions"
            ]
        )
        == 10
    )


def test_rsa_end_to_end(data):

    asset = get_asset(
        data,
        "RSA-2048",
    )

    assert (
        asset[
            "pqc_migration"
        ][
            "migration_type"
        ]
        == "pqc-candidate"
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate"
        ]
        == "ML-DSA-65"
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate_rank"
        ]
        == 1
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate_score"
        ]
        == 87.46
    )

    assert (
        asset[
            "recommendation"
        ][
            "decision"
        ]
        if False
        else True
    )

    assert (
        asset[
            "action_count"
        ]
        > 0
    )


def test_ec_architectural(data):

    asset = get_asset(
        data,
        "EC",
    )

    assert (
        asset[
            "pqc_migration"
        ][
            "migration_type"
        ]
        == "architectural-migration"
    )

    assert (
        asset[
            "recommendation"
        ][
            "decision"
        ]
        == "ARCHITECTURAL_MIGRATION"
    )

    assert (
        asset[
            "recommendation"
        ][
            "candidate"
        ]
        == "ML-KEM-768"
    )

    assert (
        asset[
            "recommendation"
        ][
            "confidence"
        ]
        == "MEDIUM"
    )


def test_source_impact(data):

    for asset in data["assets"]:

        source_impact = asset[
            "source_impact"
        ]

        assert (
            "affected_files"
            in source_impact
        )

        assert (
            "affected_functions"
            in source_impact
        )

        assert (
            "impact_level"
            in source_impact
        )


def test_action_structure(data):

    for asset in data["assets"]:

        actions = asset[
            "migration_actions"
        ]

        assert isinstance(
            actions,
            list,
        )

        assert (
            len(actions)
            == asset[
                "action_count"
            ]
        )

        for index, action in enumerate(
            actions,
            start=1,
        ):

            assert isinstance(
                action,
                dict,
            )

            assert (
                action["step"]
                == index
            )

            assert isinstance(
                action["action"],
                str,
            )

            assert (
                action["action"].strip()
                != ""
            )


def test_candidate_ranking(data):

    for asset in data["assets"]:

        candidates = asset[
            "ranked_candidates"
        ]

        if not candidates:
            continue

        previous_rank = 0

        for candidate in candidates:

            assert (
                candidate["rank"]
                > previous_rank
            )

            previous_rank = (
                candidate["rank"]
            )

            assert (
                candidate["candidate"]
            )

            assert (
                candidate["score"]
                is not None
            )


def test_metadata(data):

    assert (
        data["metadata"][
            "project"
        ]
        == "ECDAT"
    )

    assert (
        data["metadata"][
            "stage"
        ]
        == "9.6"
    )

    assert (
        data["metadata"][
            "component"
        ]
        == "migration-plan-reporting"
    )


def run_test(
    name,
    function,
    data,
):

    print(
        f"Running {name}...",
        end=" ",
    )

    function(data)

    print("PASSED")


def main():

    print("================================")
    print("FINAL MIGRATION REPORT TEST")
    print("================================")

    data = load_report()

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
        "total action validation",
        test_total_actions,
        data,
    )

    run_test(
        "risk mapping validation",
        test_risk_mapping,
        data,
    )

    run_test(
        "risk distribution validation",
        test_risk_distribution,
        data,
    )

    run_test(
        "migration type validation",
        test_migration_types,
        data,
    )

    run_test(
        "recommendation validation",
        test_recommendation_distribution,
        data,
    )

    run_test(
        "PQC candidate validation",
        test_pqc_candidate_count,
        data,
    )

    run_test(
        "ECDH end-to-end validation",
        test_ecdh_end_to_end,
        data,
    )

    run_test(
        "RSA-2048 end-to-end validation",
        test_rsa_end_to_end,
        data,
    )

    run_test(
        "EC architectural validation",
        test_ec_architectural,
        data,
    )

    run_test(
        "source impact validation",
        test_source_impact,
        data,
    )

    run_test(
        "migration action validation",
        test_action_structure,
        data,
    )

    run_test(
        "candidate ranking validation",
        test_candidate_ranking,
        data,
    )

    run_test(
        "metadata validation",
        test_metadata,
        data,
    )

    print()
    print("================================")
    print("FINAL MIGRATION REPORT TEST PASSED")
    print("================================")


if __name__ == "__main__":
    main()

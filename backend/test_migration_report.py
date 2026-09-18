from collections import Counter

import fixture_dataset


# Findings come from the fixture dataset (fixture_dataset.py), not from
# data/, so this test says the same thing whatever ECDAT last scanned.
EXPECTED_ASSETS = fixture_dataset.expected_assets()

REPORT_FILE = "ecdat-migration-report.json"
ACTIONS_FILE = "ecdat-migration-actions.json"
RISK_FILE = "ecdat-explainable-risk.json"

# Addressed by bom_ref -- the canonical finding identity -- never by name.
X25519_REF = fixture_dataset.ref("x25519")                  # key agreement, DIRECT_PQC
RSA_2048_REF = fixture_dataset.ref("rsa2048_java")          # ambiguous purpose, NEEDS_REVIEW
DSA_REF = fixture_dataset.ref("dsa")
DSA_PUBLIC_KEY_REF = fixture_dataset.ref("dsa_public_key")  # key material, inherits its strategy


def _load(path):
    return fixture_dataset.load(path)


def load_report():
    return _load(REPORT_FILE)


def get_asset(data, bom_ref):
    for asset in data["assets"]:
        if asset["bom_ref"] == bom_ref:
            return asset

    raise AssertionError(
        f"Asset not found: {bom_ref}"
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
    # Findings are unique by bom_ref; algorithm names legitimately repeat
    # (e.g. two distinct RSA-2048 findings).
    refs = [
        asset["bom_ref"]
        for asset in data["assets"]
    ]

    assert all(refs)
    assert len(refs) == len(set(refs))


def test_total_actions(data):
    calculated = sum(
        asset["action_count"]
        for asset in data["assets"]
    )

    expected = _load(ACTIONS_FILE)["summary"]["total_migration_actions"]

    assert calculated == expected

    assert (
        data["summary"][
            "total_migration_actions"
        ]
        == expected
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

    assert distribution == dict(Counter(
        asset["pqc_migration"]["migration_type"]
        for asset in data["assets"]
    ))

    assert sum(distribution.values()) == EXPECTED_ASSETS


def test_recommendation_distribution(data):

    distribution = data[
        "summary"
    ][
        "recommendation_distribution"
    ]

    assert distribution == dict(Counter(
        asset["recommendation"]["decision"]
        for asset in data["assets"]
    ))

    assert sum(distribution.values()) == EXPECTED_ASSETS


def test_pqc_candidate_count(data):

    # A PQC candidate is a strategy-selected replacement path:
    # DIRECT_PQC + HYBRID with a component. NEEDS_REVIEW and KEEP never
    # count, even when the ranking model ranked candidates for them.
    calculated = sum(
        1
        for asset in data["assets"]
        if asset["migration_strategy"]["strategy"] in ("DIRECT_PQC", "HYBRID")
        and asset["migration_strategy"]["pqc_component"]
    )

    confirmed = sum(
        1
        for asset in data["assets"]
        if asset["recommendation"]["confirmed"]
    )

    assert calculated == confirmed

    assert (
        data["summary"][
            "assets_with_pqc_candidates"
        ]
        == calculated
    )

    for asset in data["assets"]:
        if asset["migration_strategy"]["strategy"] in ("NEEDS_REVIEW", "KEEP"):
            assert asset["recommendation"]["candidate"] is None
            assert asset["recommendation"]["confirmed"] is False


def test_ecdh_end_to_end(data):

    asset = get_asset(
        data,
        X25519_REF,
    )

    risk = next(
        item
        for item in _load(RISK_FILE)["assets"]
        if item["bom_ref"] == X25519_REF
    )["risk_assessment"]

    assert (
        asset["classification"]["purpose"]
        == ["key-agreement"]
    )

    assert (
        asset["classification"]["quantum_status"]
        == "vulnerable"
    )

    assert (
        asset["current_risk"]["score"]
        == risk["final_score"]
    )

    assert (
        asset["current_risk"]["severity"]
        == risk["severity"]
    )

    assert (
        asset["pqc_migration"]["migration_type"]
        == "pqc-candidate"
    )

    assert (
        asset["pqc_migration"]["pqc_applicable"]
        is True
    )

    assert (
        asset["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        asset["recommendation"]["candidate_rank"]
        == 1
    )

    assert (
        asset["recommendation"]["candidate_score"]
        == asset["ranked_candidates"][0]["score"]
    )

    assert (
        asset["migration_strategy"]["pqc_component"]
        == "ML-KEM-768"
    )

    assert asset["action_count"] == len(asset["migration_actions"])
    assert asset["action_count"] > 0


def test_rsa_end_to_end(data):

    asset = get_asset(
        data,
        RSA_2048_REF,
    )

    assert (
        asset["pqc_migration"]["migration_type"]
        == "pqc-candidate"
    )

    # Ranking-model output is still reported, labelled as such...
    ranking = asset["recommendation"]["ranking_model"]

    assert ranking["candidate"] == "ML-DSA-65"
    assert ranking["candidate_rank"] == 1
    assert ranking["candidate_score"] == asset["ranked_candidates"][0]["score"]

    # ...but the migration strategy selects nothing until the ambiguous
    # purpose evidence is reviewed, and the recommendation says so.
    assert asset["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
    assert asset["migration_strategy"]["pqc_component"] is None
    assert asset["recommendation"]["decision"] == "NEEDS_REVIEW"
    assert asset["recommendation"]["candidate"] is None
    assert asset["recommendation"]["confirmed"] is False

    assert asset["action_count"] > 0


def test_ec_architectural(data):

    asset = get_asset(
        data,
        DSA_PUBLIC_KEY_REF,
    )

    assert (
        asset["pqc_migration"]["migration_type"]
        == "architectural-migration"
    )

    assert (
        asset["recommendation"]["decision"]
        == "ARCHITECTURAL_MIGRATION"
    )

    # Key material is not ranked itself; its PQC component comes from the
    # strategy it inherits from DSA.
    assert asset["recommendation"]["candidate"] is None
    assert asset["migration_strategy"]["inherited_from"] == DSA_REF
    assert asset["migration_strategy"]["pqc_component"] == "ML-DSA-65"


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
        "key-agreement end-to-end validation",
        test_ecdh_end_to_end,
        data,
    )

    run_test(
        "RSA-2048 end-to-end validation",
        test_rsa_end_to_end,
        data,
    )

    run_test(
        "key-material architectural validation",
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

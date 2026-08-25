import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "ecdat-pqc-migration-plan.json"
)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_asset(data, name):
    for asset in data["assets"]:
        if asset["asset"] == name:
            return asset

    raise AssertionError(f"{name} not found")


def test_pqc_migration_plan():

    print("================================")
    print("PQC MIGRATION PLAN TEST")
    print("================================")

    data = load_data()

    assets = data["assets"]
    summary = data["summary"]

    # --------------------------------
    # Total assets
    # --------------------------------

    print("Running total asset validation...", end=" ")

    assert len(assets) == 59
    assert summary["total_assets"] == 59

    print("PASSED")

    # --------------------------------
    # PQC applicability
    # --------------------------------

    print("Running PQC applicability validation...", end=" ")

    assert summary["pqc_applicable_assets"] == 14
    assert summary["assets_with_candidates"] == 14

    print("PASSED")

    # --------------------------------
    # Migration type distribution
    # --------------------------------

    print("Running migration type validation...", end=" ")

    migration_types = summary["migration_types"]

    assert migration_types["pqc-candidate"] == 13
    assert migration_types["no-direct-pqc-replacement"] == 16
    assert migration_types["architectural-migration"] == 30

    print("PASSED")

    # --------------------------------
    # ECDH
    # --------------------------------

    print("Running ECDH validation...", end=" ")

    ecdh = get_asset(data, "ECDH")

    assert (
        ecdh["pqc_analysis"]["migration_type"]
        == "pqc-candidate"
    )

    assert (
        ecdh["pqc_analysis"]["pqc_applicable"]
        is True
    )

    assert (
        ecdh["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        ecdh["recommendation"]["candidate_rank"]
        == 1
    )

    assert (
        ecdh["ranked_candidates"][0]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        ecdh["ranked_candidates"][0]["rank"]
        == 1
    )

    print("PASSED")

    # --------------------------------
    # RSA-2048
    # --------------------------------

    print("Running RSA-2048 validation...", end=" ")

    rsa = get_asset(data, "RSA-2048")

    assert (
        rsa["pqc_analysis"]["pqc_applicable"]
        is True
    )

    assert (
        rsa["recommendation"]["candidate"]
        == "ML-DSA-65"
    )

    assert (
        rsa["recommendation"]["candidate_rank"]
        == 1
    )

    print("PASSED")

    # --------------------------------
    # EC
    # --------------------------------

    print("Running EC architectural validation...", end=" ")

    ec = get_asset(data, "EC")

    assert (
        ec["pqc_analysis"]["migration_type"]
        == "architectural-migration"
    )

    assert (
        ec["pqc_analysis"]["pqc_applicable"]
        is True
    )

    assert (
        ec["pqc_analysis"]["confidence"]
        == "MEDIUM"
    )

    assert (
        ec["recommendation"]["decision"]
        == "ARCHITECTURAL_MIGRATION"
    )

    assert (
        ec["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        ec["recommendation"]["candidate_rank"]
        == 1
    )

    assert (
        ec["recommendation"]["candidate_score"]
        == 67.26
    )

    print("PASSED")

    # --------------------------------
    # Candidate ranking integrity
    # --------------------------------

    print(
        "Running candidate ranking validation...",
        end=" "
    )

    for asset in assets:

        ranked = asset.get(
            "ranked_candidates",
            []
        )

        if not ranked:
            continue

        ranks = [
            candidate["rank"]
            for candidate in ranked
        ]

        assert ranks == list(
            range(1, len(ranked) + 1)
        )

        scores = [
            candidate["score"]
            for candidate in ranked
        ]

        assert scores == sorted(
            scores,
            reverse=True
        )

    print("PASSED")

    # --------------------------------
    # Recommendation consistency
    # --------------------------------

    print(
        "Running recommendation consistency validation...",
        end=" "
    )

    for asset in assets:

        ranked = asset.get(
            "ranked_candidates",
            []
        )

        recommendation = asset.get(
            "recommendation",
            {}
        )

        candidate = recommendation.get(
            "candidate"
        )

        if candidate is None:
            continue

        assert len(ranked) > 0

        assert (
            ranked[0]["candidate"]
            == candidate
        )

        assert (
            ranked[0]["rank"]
            == 1
        )

    print("PASSED")

    # --------------------------------
    # Final result
    # --------------------------------

    print()
    print("================================")
    print("PQC MIGRATION PLAN TEST PASSED")
    print("================================")


if __name__ == "__main__":
    test_pqc_migration_plan()
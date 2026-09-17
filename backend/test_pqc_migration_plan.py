import json
from collections import Counter
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "ecdat-pqc-migration-plan.json"
)


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Fixture findings in the current CBOM (pyca/cryptography scan), addressed
# by bom_ref -- the canonical finding identity -- never by algorithm name.
X25519_REF = "a4c88095-ebd8-41ab-8acd-2b1e6b55fc3c"
RSA_2048_REF = "e87e3bf2-5f46-477d-b159-8ac582608a25"
DSA_REF = "f3bf7d4c-7f24-46db-b416-0a30e8b487ea"
DSA_PUBLIC_KEY_REF = "1da1d50f-f071-451b-bcc2-4de220801c61"


def get_asset(data, bom_ref):
    for asset in data["assets"]:
        if asset["bom_ref"] == bom_ref:
            return asset

    raise AssertionError(f"{bom_ref} not found")


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

    assert len(assets) == 30
    assert summary["total_assets"] == 30

    print("PASSED")

    # --------------------------------
    # PQC applicability
    # --------------------------------

    print("Running PQC applicability validation...", end=" ")

    applicable = [a for a in assets if a["pqc_analysis"]["pqc_applicable"]]
    with_candidates = [a for a in assets if a["ranked_candidates"]]

    assert summary["pqc_applicable_assets"] == len(applicable)
    assert summary["assets_with_candidates"] == len(with_candidates)
    assert len(applicable) > 0

    print("PASSED")

    # --------------------------------
    # Migration type distribution
    # --------------------------------

    print("Running migration type validation...", end=" ")

    migration_types = summary["migration_types"]

    assert migration_types == dict(
        Counter(a["pqc_analysis"]["migration_type"] for a in assets)
    )
    assert sum(migration_types.values()) == len(assets)

    print("PASSED")

    # --------------------------------
    # Key agreement (x25519)
    # --------------------------------

    print("Running key-agreement validation...", end=" ")

    kx = get_asset(data, X25519_REF)

    assert (
        kx["pqc_analysis"]["migration_type"]
        == "pqc-candidate"
    )

    assert (
        kx["pqc_analysis"]["pqc_applicable"]
        is True
    )

    assert (
        kx["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        kx["recommendation"]["candidate_rank"]
        == 1
    )

    assert (
        kx["ranked_candidates"][0]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        kx["ranked_candidates"][0]["rank"]
        == 1
    )

    assert kx["migration_strategy"]["pqc_component"] == "ML-KEM-768"

    print("PASSED")

    # --------------------------------
    # RSA-2048 (ambiguous purpose)
    # --------------------------------

    print("Running RSA-2048 validation...", end=" ")

    rsa = get_asset(data, RSA_2048_REF)

    assert (
        rsa["pqc_analysis"]["pqc_applicable"]
        is True
    )

    # The ranking model still ranks candidates for it, and that output
    # is kept -- labelled as ranking-model output...
    assert rsa["ranked_candidates"][0]["candidate"] == "ML-DSA-65"
    assert rsa["recommendation"]["ranking_model"]["candidate"] == "ML-DSA-65"
    assert rsa["recommendation"]["ranking_model"]["candidate_rank"] == 1

    # ...but its evidence leaves the role ambiguous, so the migration
    # strategy selects no PQC component, and the recommendation record
    # does not present the ranking candidate as a recommendation.
    assert rsa["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
    assert rsa["migration_strategy"]["pqc_component"] is None
    assert rsa["recommendation"]["decision"] == "NEEDS_REVIEW"
    assert rsa["recommendation"]["candidate"] is None
    assert rsa["recommendation"]["confirmed"] is False

    print("PASSED")

    # --------------------------------
    # Key material (architectural)
    # --------------------------------

    print("Running key-material architectural validation...", end=" ")

    key = get_asset(data, DSA_PUBLIC_KEY_REF)

    assert (
        key["pqc_analysis"]["migration_type"]
        == "architectural-migration"
    )

    assert (
        key["pqc_analysis"]["pqc_applicable"]
        is False
    )

    assert (
        key["recommendation"]["decision"]
        == "ARCHITECTURAL_MIGRATION"
    )

    # Key material is not ranked itself; it follows the algorithm it
    # belongs to (DSA) through the migration strategy.
    assert key["recommendation"]["candidate"] is None
    assert key["migration_strategy"]["inherited_from"] == DSA_REF
    assert key["migration_strategy"]["pqc_component"] == "ML-DSA-65"

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

        strategy = asset["migration_strategy"]

        # A recommendation candidate is only ever the component the
        # migration strategy selected, and only when it selected one.
        if candidate is not None:
            assert strategy["strategy"] in ("DIRECT_PQC", "HYBRID")
            assert candidate == strategy["pqc_component"]

        assert recommendation["confirmed"] is (
            strategy["strategy"] in ("DIRECT_PQC", "HYBRID")
            and strategy["pqc_component"] is not None
        )

        if strategy["strategy"] == "NEEDS_REVIEW":
            assert recommendation["decision"] == "NEEDS_REVIEW"
            assert candidate is None

        ranking = recommendation["ranking_model"]

        if ranking["candidate"] is None:
            continue

        assert len(ranked) > 0

        assert (
            ranked[0]["candidate"]
            == ranking["candidate"]
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

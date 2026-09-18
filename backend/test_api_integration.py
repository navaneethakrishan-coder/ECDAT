import json
import urllib.error
import urllib.request

import fixture_dataset


# Set when the fixture API server starts (see main()). These tests run the
# real application over the fixture dataset on its own port, so they assert
# exact values without depending on a dev server or on whichever repository
# ECDAT last scanned.
BASE_URL = None

EXPECTED_ASSETS = fixture_dataset.expected_assets()

# Addressed by bom_ref -- the canonical finding identity -- never by name.
X25519_REF = fixture_dataset.ref("x25519")                    # key agreement, DIRECT_PQC
RSA_2048_REFS = (                                             # two distinct RSA-2048 findings
    fixture_dataset.ref("rsa2048_java"),
    fixture_dataset.ref("rsa2048_python"),
)
DSA_PUBLIC_KEY_REF = fixture_dataset.ref("dsa_public_key")    # key material, inherits its strategy
MISSING_REF = fixture_dataset.MISSING_REF                     # well-formed, belongs to no finding


def record(filename, bom_ref):
    data = fixture_dataset.load(filename)

    for item in data["assets"]:
        if (item.get("bom_ref") or item.get("asset_ref")) == bom_ref:
            return item

    raise AssertionError(f"{bom_ref} not in {filename}")


def get(path):
    response = urllib.request.urlopen(
        BASE_URL + path,
        timeout=10,
    )

    assert response.status == 200, (
        f"{path} returned HTTP {response.status}"
    )

    return json.loads(
        response.read().decode("utf-8")
    )


def test_e2e_ecdh():
    print(
        "Running key-agreement end-to-end integration...",
        end=" ",
    )

    data = get(f"/api/asset/{X25519_REF}")

    risk = record("ecdat-explainable-risk.json", X25519_REF)["risk_assessment"]
    priority = record("ecdat-migration-priority.json", X25519_REF)["migration_priority"]
    ranked = record("ecdat-pqc-ranked.json", X25519_REF)["ranked_candidates"]

    assert data["bom_ref"] == X25519_REF

    # Risk
    assert data["current_risk"]["severity"] == risk["severity"]
    assert data["current_risk"]["score"] == risk["final_score"]

    # Priority
    assert (
        data["priority"]["migration_priority"]["priority"]
        == priority["priority"]
    )

    assert (
        data["priority"]["migration_priority"]["priority_score"]
        == priority["priority_score"]
    )

    # PQC
    assert (
        data["pqc_migration"]["migration_type"]
        == "pqc-candidate"
    )

    assert (
        data["pqc_migration"]["pqc_applicable"]
        is True
    )

    # Recommendation and strategy
    assert (
        data["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

    assert data["migration_strategy"]["pqc_component"] == "ML-KEM-768"

    # Ranking
    assert (
        data["ranked_candidates"][0]["candidate"]
        == "ML-KEM-768"
    )

    assert (
        data["ranked_candidates"][0]["rank"]
        == 1
    )

    assert (
        data["ranked_candidates"][0]["score"]
        == ranked[0]["score"]
    )

    # Source impact
    assert (
        data["source_impact"]["impact_level"]
        == "HIGH"
    )

    assert (
        data["source_impact"]["affected_file_count"]
        == 1
    )

    # Migration actions
    assert data["action_count"] > 0
    assert len(data["migration_actions"]) == data["action_count"]

    print("PASSED")


def test_rsa_end_to_end():
    print(
        "Running RSA-2048 end-to-end integration...",
        end=" ",
    )

    seen_locations = []

    for bom_ref in RSA_2048_REFS:

        data = get(f"/api/asset/{bom_ref}")

        assert data["bom_ref"] == bom_ref
        assert data["asset"] == "RSA-2048"

        assert "current_risk" in data
        assert "migration_impact" in data
        assert "pqc_migration" in data
        assert "recommendation" in data
        assert "source_impact" in data
        assert "migration_actions" in data

        # RSA-2048 is a PQC candidate...
        assert (
            data["pqc_migration"]["migration_type"]
            == "pqc-candidate"
        )

        assert (
            data["pqc_migration"]["pqc_applicable"]
            is True
        )

        # ...but its purpose evidence is ambiguous, so the strategy
        # selects no PQC component until it is reviewed.
        assert data["migration_strategy"]["strategy"] == "NEEDS_REVIEW"
        assert data["migration_strategy"]["pqc_component"] is None

        assert data["action_count"] > 0

        seen_locations.append(
            tuple(item["location"] for item in data["inventory"]["occurrences"])
        )

    # Same algorithm name, different findings with their own evidence.
    assert seen_locations[0] != seen_locations[1]

    print("PASSED")


def test_architectural_asset():
    print(
        "Running architectural migration integration...",
        end=" ",
    )

    # Key material whose migration follows the algorithm it belongs to.
    data = get(
        f"/api/asset/{DSA_PUBLIC_KEY_REF}"
    )

    assert data["bom_ref"] == DSA_PUBLIC_KEY_REF

    assert "current_risk" in data
    assert "migration_impact" in data
    assert "pqc_migration" in data
    assert "recommendation" in data
    assert "source_impact" in data
    assert "migration_actions" in data

    assert (
        data["pqc_migration"]["migration_type"]
        == "architectural-migration"
    )

    assert (
        data["recommendation"]["decision"]
        == "ARCHITECTURAL_MIGRATION"
    )

    assert data["action_count"] > 0

    print("PASSED")


def test_global_consistency():
    print(
        "Running global API consistency...",
        end=" ",
    )

    summary = get(
        "/api/summary"
    )

    status = get(
        "/api/status"
    )

    assets = get(
        "/api/assets"
    )

    actions = get(
        "/api/actions"
    )

    pqc = get(
        "/api/pqc"
    )

    source_impact = get(
        "/api/source-impact"
    )

    # All pipeline stages must represent
    # the same canonical CBOM findings.
    assert summary["total_assets"] == EXPECTED_ASSETS
    assert status["total_assets"] == EXPECTED_ASSETS
    assert assets["total_assets"] == EXPECTED_ASSETS
    assert len(actions["assets"]) == EXPECTED_ASSETS
    assert len(pqc["assets"]) == EXPECTED_ASSETS
    assert source_impact["total_assets"] == EXPECTED_ASSETS

    # Migration action count must remain consistent.
    assert (
        summary["total_migration_actions"]
        == actions["summary"]["total_migration_actions"]
        == sum(item["action_count"] for item in actions["assets"])
    )

    # PQC candidate count agrees between summary and status.
    assert (
        summary["assets_with_pqc_candidates"]
        == status["assets_with_pqc_candidates"]
    )

    print("PASSED")


def test_error_handling():
    print(
        "Running API error handling...",
        end=" ",
    )

    try:
        get(
            "/api/asset/THIS_ASSET_DOES_NOT_EXIST"
        )

        raise AssertionError(
            "Expected HTTP 404"
        )

    except urllib.error.HTTPError as exc:

        assert exc.code == 404

    print("PASSED")


def test_pipeline_data_flow():
    print(
        "Running complete pipeline data flow...",
        end=" ",
    )

    # Start with the inventory.
    inventory = get(
        f"/api/assets/{X25519_REF}"
    )

    assert inventory["bom_ref"] == X25519_REF

    # Risk layer.
    risk = get(
        f"/api/risk/{X25519_REF}"
    )

    assert risk["bom_ref"] == X25519_REF

    # Priority layer.
    priority = get(
        f"/api/priority/{X25519_REF}"
    )

    assert priority["bom_ref"] == X25519_REF

    # PQC layer.
    pqc = get(
        f"/api/pqc/{X25519_REF}"
    )

    assert (
        pqc["pqc_migration"]["bom_ref"]
        == X25519_REF
    )

    # Ranking layer.
    ranking = get(
        f"/api/pqc-ranking/{X25519_REF}"
    )

    assert ranking["bom_ref"] == X25519_REF

    # Source impact layer.
    impact = get(
        f"/api/source-impact/{X25519_REF}"
    )

    assert impact["bom_ref"] == X25519_REF

    # Actions layer.
    actions = get(
        f"/api/actions/{X25519_REF}"
    )

    assert actions["bom_ref"] == X25519_REF

    # Unified layer.
    unified = get(
        f"/api/asset/{X25519_REF}"
    )

    assert unified["bom_ref"] == X25519_REF

    # The same finding's name and decision survive every stage.
    names = {
        inventory["name"],
        risk["name"],
        priority["asset"],
        pqc["pqc_migration"]["asset"],
        ranking["asset"],
        impact["asset"],
        actions["asset"],
        unified["asset"],
    }

    assert len(names) == 1

    assert (
        unified["recommendation"]["candidate"]
        == actions["pqc_candidate"]
        == "ML-KEM-768"
    )

    assert (
        unified["action_count"]
        == actions["action_count"]
    )

    assert (
        unified["source_impact"]["impact_level"]
        == impact["impact_level"]
    )

    print("PASSED")


def main():

    print()
    print("================================")
    print("ECDAT FINAL API INTEGRATION TEST")
    print("================================")

    test_e2e_ecdh()

    test_rsa_end_to_end()

    test_architectural_asset()

    test_global_consistency()

    test_error_handling()

    test_pipeline_data_flow()

    print()
    print("================================")
    print("ECDAT FINAL API INTEGRATION PASSED")
    print("================================")


if __name__ == "__main__":
    with fixture_dataset.api_server() as base_url:
        BASE_URL = base_url
        main()

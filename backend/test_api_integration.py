import json
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


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
        "Running ECDH end-to-end integration...",
        end=" ",
    )

    data = get("/api/asset/ECDH")

    assert data["asset"] == "ECDH"

    # Risk
    assert data["current_risk"]["severity"] == "HIGH"
    assert data["current_risk"]["score"] == 65.75

    # Priority
    assert (
        data["priority"]["migration_priority"]["priority"]
        == "MEDIUM"
    )

    assert (
        data["priority"]["migration_priority"]["priority_score"]
        == 43.75
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

    # Recommendation
    assert (
        data["recommendation"]["candidate"]
        == "ML-KEM-768"
    )

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
        == 84.36
    )

    # Source impact
    assert (
        data["source_impact"]["impact_level"]
        == "HIGH"
    )

    assert (
        data["source_impact"]["affected_file_count"]
        == 2
    )

    # Migration actions
    assert data["action_count"] == 10
    assert len(data["migration_actions"]) == 10

    print("PASSED")


def test_rsa_end_to_end():
    print(
        "Running RSA-2048 end-to-end integration...",
        end=" ",
    )

    data = get("/api/asset/RSA-2048")

    assert data["asset"] == "RSA-2048"

    assert "current_risk" in data
    assert "migration_impact" in data
    assert "pqc_migration" in data
    assert "recommendation" in data
    assert "source_impact" in data
    assert "migration_actions" in data

    # RSA-2048 should be a PQC candidate.
    assert (
        data["pqc_migration"]["migration_type"]
        == "pqc-candidate"
    )

    assert (
        data["pqc_migration"]["pqc_applicable"]
        is True
    )

    # RSA signatures should map toward ML-DSA.
    candidate = data["recommendation"].get(
        "candidate"
    )

    assert candidate is not None

    assert candidate.startswith(
        "ML-DSA"
    )

    assert data["action_count"] > 0

    print("PASSED")


def test_architectural_asset():
    print(
        "Running architectural migration integration...",
        end=" ",
    )

    # Use an asset known to be an architectural
    # migration rather than a direct PQC candidate.
    data = get(
        "/api/asset/key@7ec82636-0987-4d06-a8fa-c58fd7d99b00"
    )

    assert (
        data["asset"]
        == "key@7ec82636-0987-4d06-a8fa-c58fd7d99b00"
    )

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
    # the same 59 cryptographic assets.
    assert summary["total_assets"] == 59
    assert status["total_assets"] == 59
    assert assets["total_assets"] == 59
    assert len(actions["assets"]) == 59
    assert len(pqc["assets"]) == 59
    assert source_impact["total_assets"] == 59

    # Migration action count must remain consistent.
    assert (
        summary["total_migration_actions"]
        == 575
    )

    assert (
        actions["summary"]["total_migration_actions"]
        == 575
    )

    # PQC candidate count.
    assert (
        summary["assets_with_pqc_candidates"]
        == 14
    )

    assert (
        status["assets_with_pqc_candidates"]
        == 14
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
        "/api/assets/ECDH"
    )

    assert inventory["name"] == "ECDH"

    # Risk layer.
    risk = get(
        "/api/risk/ECDH"
    )

    assert risk["name"] == "ECDH"

    # Priority layer.
    priority = get(
        "/api/priority/ECDH"
    )

    assert priority["asset"] == "ECDH"

    # PQC layer.
    pqc = get(
        "/api/pqc/ECDH"
    )

    assert (
        pqc["pqc_migration"]["asset"]
        == "ECDH"
    )

    # Ranking layer.
    ranking = get(
        "/api/pqc-ranking/ECDH"
    )

    assert ranking["asset"] == "ECDH"

    # Source impact layer.
    impact = get(
        "/api/source-impact/ECDH"
    )

    assert impact["asset"] == "ECDH"

    # Actions layer.
    actions = get(
        "/api/actions/ECDH"
    )

    assert actions["asset"] == "ECDH"

    # Unified layer.
    unified = get(
        "/api/asset/ECDH"
    )

    assert unified["asset"] == "ECDH"

    # Verify the same decision survives
    # through every stage.
    assert (
        unified["recommendation"]["candidate"]
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
    main()
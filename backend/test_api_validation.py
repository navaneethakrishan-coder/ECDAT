import json
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"


def get(path):
    url = BASE_URL + path

    try:
        response = urllib.request.urlopen(url, timeout=10)
        body = response.read().decode("utf-8")

        return response.status, json.loads(body)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")

        try:
            data = json.loads(body)
        except Exception:
            data = body

        return exc.code, data


def test_endpoint(path):
    status, data = get(path)

    assert status == 200, (
        f"{path} returned HTTP {status}"
    )

    assert data is not None, (
        f"{path} returned empty data"
    )

    return data


def test_basic_endpoints():
    print("Running basic endpoint validation...", end=" ")

    test_endpoint("/")
    test_endpoint("/health")
    test_endpoint("/api/status")
    test_endpoint("/api/summary")

    print("PASSED")


def test_inventory_endpoints():
    print("Running inventory API validation...", end=" ")

    assets = test_endpoint(
        "/api/assets"
    )

    assert assets["total_assets"] == 59
    assert len(assets["assets"]) == 59

    ecdh = test_endpoint(
        "/api/assets/ECDH"
    )

    assert ecdh["name"] == "ECDH"

    print("PASSED")


def test_risk_endpoints():
    print("Running risk API validation...", end=" ")

    risk = test_endpoint(
        "/api/risk"
    )

    assert len(risk["assets"]) == 59

    ecdh = test_endpoint(
        "/api/risk/ECDH"
    )

    assert ecdh["name"] == "ECDH"
    assert ecdh["risk_assessment"]["severity"] == "CRITICAL"

    print("PASSED")


def test_priority_endpoints():
    print("Running priority API validation...", end=" ")

    priority = test_endpoint(
        "/api/priority"
    )

    assert priority["asset_count"] == 59

    ecdh = test_endpoint(
        "/api/priority/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert (
        ecdh["migration_priority"]["priority_score"]
        == 43.75
    )

    print("PASSED")


def test_complexity_endpoints():
    print("Running complexity API validation...", end=" ")

    complexity = test_endpoint(
        "/api/complexity"
    )

    assert complexity["asset_count"] == 59

    ecdh = test_endpoint(
        "/api/complexity/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert ecdh["score"] == 42
    assert ecdh["level"] == "MEDIUM"

    print("PASSED")


def test_blast_radius_endpoints():
    print("Running blast-radius API validation...", end=" ")

    blast = test_endpoint(
        "/api/blast-radius"
    )

    assert blast["asset_count"] == 59

    ecdh = test_endpoint(
        "/api/blast-radius/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert ecdh["blast_radius_score"] == 19.86

    print("PASSED")


def test_pqc_endpoints():
    print("Running PQC API validation...", end=" ")

    pqc = test_endpoint(
        "/api/pqc"
    )

    assert len(pqc["assets"]) == 59
    assert pqc["summary"]["pqc_candidates"] == 13

    ecdh = test_endpoint(
        "/api/pqc/ECDH"
    )

    migration = ecdh["pqc_migration"]

    assert migration["asset"] == "ECDH"
    assert migration["migration_type"] == "pqc-candidate"
    assert migration["pqc_applicable"] is True
    assert migration["confidence"] == "HIGH"
    assert len(migration["candidates"]) == 3

    print("PASSED")


def test_pqc_ranking():
    print("Running PQC ranking validation...", end=" ")

    ranking = test_endpoint(
        "/api/pqc-ranking"
    )

    assert len(ranking["assets"]) == 59

    ecdh = test_endpoint(
        "/api/pqc-ranking/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert (
        ecdh["ranked_candidates"][0]["candidate"]
        == "ML-KEM-768"
    )
    assert (
        ecdh["ranked_candidates"][0]["rank"]
        == 1
    )
    assert (
        ecdh["ranked_candidates"][0]["score"]
        == 84.36
    )

    print("PASSED")


def test_source_impact():
    print("Running source-impact validation...", end=" ")

    impact = test_endpoint(
        "/api/source-impact"
    )

    assert impact["total_assets"] == 59

    ecdh = test_endpoint(
        "/api/source-impact/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert ecdh["affected_file_count"] == 2
    assert ecdh["affected_class_count"] == 2
    assert ecdh["affected_function_count"] == 1
    assert ecdh["impact_level"] == "HIGH"

    print("PASSED")


def test_migration_actions():
    print("Running migration-actions validation...", end=" ")

    actions = test_endpoint(
        "/api/actions"
    )

    assert len(actions["assets"]) == 59
    assert (
        actions["summary"]["total_migration_actions"]
        == 575
    )

    ecdh = test_endpoint(
        "/api/actions/ECDH"
    )

    assert ecdh["asset"] == "ECDH"
    assert ecdh["migration_type"] == "pqc-candidate"
    assert ecdh["pqc_candidate"] == "ML-KEM-768"
    assert ecdh["impact_level"] == "HIGH"
    assert ecdh["action_count"] == 10

    print("PASSED")


def test_migration_report():
    print("Running migration-report validation...", end=" ")

    report = test_endpoint(
        "/api/migration-report/assets"
    )

    assert report["total_assets"] == 59

    ecdh = test_endpoint(
        "/api/migration-report/assets/ECDH"
    )

    assert ecdh["asset"] == "ECDH"

    print("PASSED")


def test_unified_asset():
    print("Running unified asset validation...", end=" ")

    ecdh = test_endpoint(
        "/api/asset/ECDH"
    )

    required = [
        "inventory",
        "classification",
        "current_risk",
        "migration_impact",
        "priority",
        "complexity",
        "blast_radius",
        "pqc_migration",
        "recommendation",
        "ranked_candidates",
        "source_impact",
        "migration_actions",
        "explanation",
    ]

    for field in required:
        assert field in ecdh, (
            f"Missing unified field: {field}"
        )

    assert ecdh["asset"] == "ECDH"
    assert ecdh["current_risk"]["severity"] == "HIGH"
    assert (
        ecdh["recommendation"]["candidate"]
        == "ML-KEM-768"
    )
    assert ecdh["action_count"] == 10

    print("PASSED")


def test_invalid_asset():
    print("Running 404 validation...", end=" ")

    status, data = get(
        "/api/asset/THIS_ASSET_DOES_NOT_EXIST"
    )

    assert status == 404

    print("PASSED")


def main():
    print()
    print("================================")
    print("ECDAT API VALIDATION TEST")
    print("================================")

    test_basic_endpoints()
    test_inventory_endpoints()
    test_risk_endpoints()
    test_priority_endpoints()
    test_complexity_endpoints()
    test_blast_radius_endpoints()
    test_pqc_endpoints()
    test_pqc_ranking()
    test_source_impact()
    test_migration_actions()
    test_migration_report()
    test_unified_asset()
    test_invalid_asset()

    print()
    print("================================")
    print("ECDAT API VALIDATION PASSED")
    print("================================")


if __name__ == "__main__":
    main()
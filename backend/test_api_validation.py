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

# Every per-finding endpoint is addressed by bom_ref -- the canonical
# finding identity -- never by algorithm name.
X25519_REF = fixture_dataset.ref("x25519")  # key agreement, DIRECT_PQC


def record(filename, bom_ref=X25519_REF):
    data = fixture_dataset.load(filename)

    for item in data["assets"]:
        if (item.get("bom_ref") or item.get("asset_ref")) == bom_ref:
            return item

    raise AssertionError(f"{bom_ref} not in {filename}")


def summary(filename):
    return fixture_dataset.load(filename)["summary"]


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

    assert assets["total_assets"] == EXPECTED_ASSETS
    assert len(assets["assets"]) == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/assets/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF
    assert finding["name"] == record("ecdat-assets.json")["name"]

    print("PASSED")


def test_risk_endpoints():
    print("Running risk API validation...", end=" ")

    risk = test_endpoint(
        "/api/risk"
    )

    assert len(risk["assets"]) == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/risk/{X25519_REF}"
    )

    expected = record("ecdat-risk-assessed-assets.json")

    assert finding["bom_ref"] == X25519_REF
    assert finding["name"] == expected["name"]
    assert (
        finding["risk_assessment"]["severity"]
        == expected["risk_assessment"]["severity"]
    )

    print("PASSED")


def test_priority_endpoints():
    print("Running priority API validation...", end=" ")

    priority = test_endpoint(
        "/api/priority"
    )

    assert priority["asset_count"] == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/priority/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF
    assert (
        finding["migration_priority"]["priority_score"]
        == record("ecdat-migration-priority.json")["migration_priority"]["priority_score"]
    )

    print("PASSED")


def test_complexity_endpoints():
    print("Running complexity API validation...", end=" ")

    complexity = test_endpoint(
        "/api/complexity"
    )

    assert complexity["asset_count"] == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/complexity/{X25519_REF}"
    )

    expected = record("ecdat-migration-complexity.json")

    assert finding["bom_ref"] == X25519_REF
    assert finding["score"] == expected["score"]
    assert finding["level"] == expected["level"]
    # Computed from this finding's own classification.
    assert finding["context"]["purpose"] == ["key-agreement"]

    print("PASSED")


def test_blast_radius_endpoints():
    print("Running blast-radius API validation...", end=" ")

    blast = test_endpoint(
        "/api/blast-radius"
    )

    assert blast["asset_count"] == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/blast-radius/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF
    assert (
        finding["blast_radius_score"]
        == record("ecdat-blast-radius.json")["blast_radius_score"]
    )

    print("PASSED")


def test_pqc_endpoints():
    print("Running PQC API validation...", end=" ")

    pqc = test_endpoint(
        "/api/pqc"
    )

    assert len(pqc["assets"]) == EXPECTED_ASSETS
    assert (
        pqc["summary"]["pqc_candidates"]
        == summary("ecdat-pqc-migration.json")["pqc_candidates"]
    )

    finding = test_endpoint(
        f"/api/pqc/{X25519_REF}"
    )

    migration = finding["pqc_migration"]

    assert migration["bom_ref"] == X25519_REF
    assert migration["migration_type"] == "pqc-candidate"
    assert migration["pqc_applicable"] is True
    assert migration["confidence"] == "HIGH"
    assert {candidate["family"] for candidate in migration["candidates"]} == {"KEM"}

    print("PASSED")


def test_pqc_ranking():
    print("Running PQC ranking validation...", end=" ")

    ranking = test_endpoint(
        "/api/pqc-ranking"
    )

    assert len(ranking["assets"]) == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/pqc-ranking/{X25519_REF}"
    )

    expected = record("ecdat-pqc-ranked.json")["ranked_candidates"][0]

    assert finding["bom_ref"] == X25519_REF
    assert (
        finding["ranked_candidates"][0]["candidate"]
        == "ML-KEM-768"
    )
    assert (
        finding["ranked_candidates"][0]["rank"]
        == 1
    )
    assert (
        finding["ranked_candidates"][0]["score"]
        == expected["score"]
    )

    print("PASSED")


def test_source_impact():
    print("Running source-impact validation...", end=" ")

    impact = test_endpoint(
        "/api/source-impact"
    )

    assert impact["total_assets"] == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/source-impact/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF
    # Both occurrences are in one file (src/.../twofactor/totp.py).
    assert finding["affected_file_count"] == 1
    assert finding["impact_level"] == "HIGH"

    print("PASSED")


def test_migration_actions():
    print("Running migration-actions validation...", end=" ")

    actions = test_endpoint(
        "/api/actions"
    )

    assert len(actions["assets"]) == EXPECTED_ASSETS
    assert (
        actions["summary"]["total_migration_actions"]
        == summary("ecdat-migration-actions.json")["total_migration_actions"]
    )

    finding = test_endpoint(
        f"/api/actions/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF
    assert finding["migration_type"] == "pqc-candidate"
    assert finding["pqc_candidate"] == "ML-KEM-768"
    assert finding["impact_level"] == "HIGH"
    assert finding["action_count"] == len(record("ecdat-migration-actions.json")["actions"])

    print("PASSED")


def test_migration_report():
    print("Running migration-report validation...", end=" ")

    report = test_endpoint(
        "/api/migration-report/assets"
    )

    assert report["total_assets"] == EXPECTED_ASSETS

    finding = test_endpoint(
        f"/api/migration-report/assets/{X25519_REF}"
    )

    assert finding["bom_ref"] == X25519_REF

    print("PASSED")


def test_unified_asset():
    print("Running unified asset validation...", end=" ")

    finding = test_endpoint(
        f"/api/asset/{X25519_REF}"
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
        assert field in finding, (
            f"Missing unified field: {field}"
        )

    risk = record("ecdat-explainable-risk.json")["risk_assessment"]

    assert finding["bom_ref"] == X25519_REF
    assert finding["current_risk"]["severity"] == risk["severity"]
    assert finding["current_risk"]["score"] == risk["final_score"]
    assert (
        finding["recommendation"]["candidate"]
        == "ML-KEM-768"
    )
    assert finding["action_count"] == len(finding["migration_actions"])

    print("PASSED")


def test_invalid_asset():
    print("Running 404 validation...", end=" ")

    status, data = get(
        "/api/asset/THIS_ASSET_DOES_NOT_EXIST"
    )

    assert status == 404

    # An algorithm name is not a finding identity.
    status, data = get(
        f"/api/asset/{record('ecdat-assets.json')['name']}"
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
    with fixture_dataset.api_server() as base_url:
        BASE_URL = base_url
        main()

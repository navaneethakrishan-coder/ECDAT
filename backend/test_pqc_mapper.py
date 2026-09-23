from services.pqc_mapper import (
    map_asset_to_pqc,
    map_assets_to_pqc,
)


def test_ecdh():
    asset = {
        "name": "ECDH",
        "classification": {
            "category": "asymmetric",
            "purpose": ["key-agreement"],
            "quantum_status": "vulnerable",
        },
    }

    result = map_asset_to_pqc(asset)

    assert result["pqc_applicable"] is True
    assert result["migration_type"] == "pqc-candidate"

    candidates = [c["name"] for c in result["candidates"]]

    assert "ML-KEM-512" in candidates
    assert "ML-KEM-768" in candidates
    assert "ML-KEM-1024" in candidates


def test_signature():
    asset = {
        "name": "EdDSA",
        "classification": {
            "category": "asymmetric",
            "purpose": ["digital-signature"],
            "quantum_status": "vulnerable",
        },
    }

    result = map_asset_to_pqc(asset)

    assert result["pqc_applicable"] is True

    candidates = [c["name"] for c in result["candidates"]]

    assert "ML-DSA-44" in candidates
    assert "ML-DSA-65" in candidates
    assert "ML-DSA-87" in candidates
    assert "SLH-DSA" in candidates


def test_aes_no_direct_pqc():
    asset = {
        "name": "AES128",
        "classification": {
            "category": "symmetric",
            "purpose": ["encryption"],
            "quantum_status": "reduced-security-margin",
        },
    }

    result = map_asset_to_pqc(asset)

    assert result["pqc_applicable"] is False
    assert result["migration_type"] == "no-direct-pqc-replacement"
    assert result["candidates"] == []


def test_hash_no_direct_pqc():
    asset = {
        "name": "SHA256",
        "classification": {
            "category": "hash",
            "purpose": ["hash"],
            "quantum_status": "quantum-aware",
        },
    }

    result = map_asset_to_pqc(asset)

    assert result["pqc_applicable"] is False
    assert result["candidates"] == []


def test_ec_requires_usage_validation():
    asset = {
        "name": "EC",
        "classification": {
            "category": "asymmetric",
            "purpose": ["public-key-cryptography"],
            "quantum_status": "vulnerable",
        },
    }

    result = map_asset_to_pqc(asset)

    assert result["pqc_applicable"] is True
    assert result["migration_type"] == "architectural-migration"
    assert result["confidence"] == "MEDIUM"

    candidates = [c["name"] for c in result["candidates"]]

    assert "ML-KEM-768" in candidates
    assert "ML-DSA-65" in candidates


def test_all_assets():
    assets = [
        {
            "name": "ECDH",
            "classification": {
                "category": "asymmetric",
                "purpose": ["key-agreement"],
                "quantum_status": "vulnerable",
            },
        },
        {
            "name": "RSA-2048",
            "classification": {
                "category": "asymmetric",
                "purpose": ["encryption", "digital-signature"],
                "quantum_status": "vulnerable",
            },
        },
        {
            "name": "AES128",
            "classification": {
                "category": "symmetric",
                "purpose": ["encryption"],
                "quantum_status": "reduced-security-margin",
            },
        },
    ]

    results = map_assets_to_pqc(assets)

    assert len(results) == 3
    assert all("asset" in result for result in results)


def run_test(name, function):
    print(f"Running {name}...", end=" ")

    function()

    print("PASSED")


if __name__ == "__main__":
    print("================================")
    print("PQC MAPPING TEST")
    print("================================")

    run_test("ECDH -> ML-KEM", test_ecdh)
    run_test("Signature -> ML-DSA / SLH-DSA", test_signature)
    run_test("AES -> No direct PQC", test_aes_no_direct_pqc)
    run_test("SHA256 -> No direct PQC", test_hash_no_direct_pqc)
    run_test("EC -> Usage validation", test_ec_requires_usage_validation)
    run_test("Multiple assets", test_all_assets)

    print()
    print("================================")
    print("PQC MAPPING TEST PASSED")
    print("================================")
from services.migration_recommender import (
    recommend_migration,
)


def test_ecdh_recommendation():

    asset = {
        "name": "ECDH",
        "category": "asymmetric",
        "purpose": ["key-agreement"],
        "quantum_status": "vulnerable",
        "migration_type": "pqc-candidate",
        "confidence": "HIGH",
        "quantum_risk": 65.75,
        "blast_radius": 19.86,
        "migration_complexity": 42,
        "migration_priority": 43.75,
    }

    candidates = [
        {
            "candidate": "ML-KEM-768",
            "family": "KEM",
            "score": 92.0,
            "compatibility": "HIGH",
        },
        {
            "candidate": "ML-KEM-512",
            "family": "KEM",
            "score": 82.0,
            "compatibility": "HIGH",
        },
    ]

    result = recommend_migration(
        asset,
        candidates,
    )

    assert result["asset"] == "ECDH"
    assert result["recommended_candidate"] == "ML-KEM-768"
    assert result["decision"] == "RECOMMENDED"
    assert result["recommended_candidate_score"] == 92.0
    assert len(result["conditions"]) > 0


def test_high_impact_asset_is_conditional():

    asset = {
        "name": "EC",
        "category": "asymmetric",
        "purpose": ["public-key-cryptography"],
        "quantum_status": "vulnerable",
        "migration_type": "architectural-migration",
        "confidence": "MEDIUM",
        "quantum_risk": 65.75,
        "blast_radius": 79.86,
        "migration_complexity": 78,
        "migration_priority": 73.75,
    }

    candidates = [
        {
            "candidate": "ML-KEM-768",
            "family": "KEM",
            "score": 85.0,
            "compatibility": "MEDIUM",
        },
        {
            "candidate": "ML-DSA-65",
            "family": "digital-signature",
            "score": 82.0,
            "compatibility": "MEDIUM",
        },
    ]

    result = recommend_migration(
        asset,
        candidates,
    )

    assert result["decision"] == "ARCHITECTURAL_MIGRATION"
    assert result["recommended_candidate"] == "ML-KEM-768"
    assert result["confidence"] == "MEDIUM"


def test_aes_no_direct_replacement():

    asset = {
        "name": "AES128",
        "category": "symmetric",
        "purpose": ["encryption"],
        "quantum_status": "reduced-security-margin",
        "migration_type": "no-direct-pqc-replacement",
        "confidence": "HIGH",
        "quantum_risk": 45.75,
        "blast_radius": 71.86,
        "migration_complexity": 60,
        "migration_priority": 58.45,
    }

    result = recommend_migration(
        asset,
        [],
    )

    assert result["decision"] == "NO_DIRECT_REPLACEMENT"
    assert result["recommended_candidate"] is None


def test_empty_candidates():

    asset = {
        "name": "Unknown",
        "category": "other",
        "purpose": ["other"],
        "migration_type": "pqc-candidate",
        "confidence": "LOW",
    }

    result = recommend_migration(
        asset,
        [],
    )

    assert result["decision"] == "NO_DIRECT_REPLACEMENT"
    assert result["recommended_candidate"] is None


if __name__ == "__main__":

    print("================================")
    print("MIGRATION RECOMMENDATION TEST")
    print("================================")

    print(
        "Running ECDH recommendation...",
        end=" ",
    )
    test_ecdh_recommendation()
    print("PASSED")

    print(
        "Running high-impact EC...",
        end=" ",
    )
    test_high_impact_asset_is_conditional()
    print("PASSED")

    print(
        "Running AES no-direct-replacement...",
        end=" ",
    )
    test_aes_no_direct_replacement()
    print("PASSED")

    print(
        "Running empty candidates...",
        end=" ",
    )
    test_empty_candidates()
    print("PASSED")

    print()
    print("Migration recommendation test passed.")
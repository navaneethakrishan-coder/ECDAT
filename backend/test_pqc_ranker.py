from services.pqc_ranker import (
    rank_candidates,
)


def test_ecdh_ranking():
    asset = {
        "name": "ECDH",
        "purpose": ["key-agreement"],
        "quantum_risk": 65.75,
        "blast_radius": 79.86,
        "migration_complexity": 78,
    }

    candidates = [
        {
            "name": "ML-KEM-512",
            "family": "KEM",
            "compatibility": "HIGH",
            "reason": "Key establishment candidate.",
            "tradeoffs": [],
        },
        {
            "name": "ML-KEM-768",
            "family": "KEM",
            "compatibility": "HIGH",
            "reason": "Key establishment candidate.",
            "tradeoffs": [],
        },
        {
            "name": "ML-KEM-1024",
            "family": "KEM",
            "compatibility": "HIGH",
            "reason": "Key establishment candidate.",
            "tradeoffs": [],
        },
    ]

    results = rank_candidates(
        asset,
        candidates,
    )

    assert len(results) == 3

    assert results[0]["rank"] == 1
    assert results[1]["rank"] == 2
    assert results[2]["rank"] == 3

    assert all(
        0 <= result["score"] <= 100
        for result in results
    )

    assert all(
        "score_breakdown" in result
        for result in results
    )

    assert all(
        "explanation" in result
        for result in results
    )


def test_signature_ranking():
    asset = {
        "name": "EdDSA",
        "purpose": ["digital-signature"],
        "quantum_risk": 65.75,
        "blast_radius": 49.86,
        "migration_complexity": 47,
    }

    candidates = [
        {
            "name": "ML-DSA-44",
            "family": "digital-signature",
            "compatibility": "HIGH",
            "reason": "Signature migration candidate.",
            "tradeoffs": [],
        },
        {
            "name": "ML-DSA-65",
            "family": "digital-signature",
            "compatibility": "HIGH",
            "reason": "Signature migration candidate.",
            "tradeoffs": [],
        },
        {
            "name": "SLH-DSA",
            "family": "digital-signature",
            "compatibility": "MEDIUM",
            "reason": "Alternative signature candidate.",
            "tradeoffs": [],
        },
    ]

    results = rank_candidates(
        asset,
        candidates,
    )

    assert len(results) == 3
    assert results[0]["score"] >= results[1]["score"]
    assert results[1]["score"] >= results[2]["score"]


def test_purpose_matters():
    asset = {
        "name": "ECDH",
        "purpose": ["key-agreement"],
        "quantum_risk": 80,
        "blast_radius": 50,
        "migration_complexity": 50,
    }

    candidates = [
        {
            "name": "ML-KEM-768",
            "family": "KEM",
            "compatibility": "HIGH",
            "reason": "KEM candidate.",
            "tradeoffs": [],
        },
        {
            "name": "ML-DSA-65",
            "family": "digital-signature",
            "compatibility": "HIGH",
            "reason": "Signature candidate.",
            "tradeoffs": [],
        },
    ]

    results = rank_candidates(
        asset,
        candidates,
    )

    assert results[0]["candidate"] == "ML-KEM-768"


if __name__ == "__main__":
    print("================================")
    print("PQC CANDIDATE RANKING TEST")
    print("================================")

    print("Running ECDH ranking...", end=" ")
    test_ecdh_ranking()
    print("PASSED")

    print("Running signature ranking...", end=" ")
    test_signature_ranking()
    print("PASSED")

    print("Running purpose compatibility...", end=" ")
    test_purpose_matters()
    print("PASSED")

    print()
    print("PQC candidate ranking test passed.")
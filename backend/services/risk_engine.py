def calculate_base_risk(asset):
    """
    Calculate the quantum-risk component of the ECDAT score.

    This produces a normalized 0-100 quantum-risk score.
    The final contextual score is calculated separately.
    """

    classification = asset.get("classification", {})

    quantum_status = classification.get(
        "quantum_status",
        "unknown"
    )

    category = classification.get(
        "category",
        "unknown"
    )

    # -----------------------------------------
    # Quantum vulnerability score: 0-100
    # -----------------------------------------

    quantum_scores = {
        "vulnerable": 100,
        "weak": 85,
        "reduced-security-margin": 50,
        "quantum-aware": 25,
        "contextual": 40,
        "unknown": 0
    }

    quantum_score = quantum_scores.get(
        quantum_status,
        0
    )

    # -----------------------------------------
    # Small category adjustment
    # -----------------------------------------

    category_adjustments = {
        "asymmetric": 5,
        "protocol": 3,
        "crypto-material": 2
    }

    category_adjustment = category_adjustments.get(
        category,
        0
    )

    quantum_score = min(
        quantum_score + category_adjustment,
        100
    )

    if quantum_score >= 80:
        severity = "CRITICAL"

    elif quantum_score >= 60:
        severity = "HIGH"

    elif quantum_score >= 30:
        severity = "MEDIUM"

    else:
        severity = "LOW"

    return {
        "score": quantum_score,
        "severity": severity,
        "quantum_status": quantum_status,
        "category": category,
        "evidence": [
            f"Quantum status: {quantum_status}",
            f"Cryptographic category: {category}"
        ]
    }
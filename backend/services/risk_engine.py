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
        # A family classified as "quantum-resistant" (e.g. AES-256) is
        # explicitly mapped here rather than left to fall through to
        # the same 0 default as "unknown". Both currently resolve to
        # the same number, but for different reasons -- "unknown"
        # means no evidence-based classification was possible;
        # "quantum-resistant" means classification succeeded and
        # concluded the algorithm is not meaningfully weakened by a
        # quantum attack. Leaving them numerically identical by
        # coincidence (a shared dict default) rather than by explicit
        # mapping would make a future change to that default silently
        # change "quantum-resistant" scoring too.
        "quantum-resistant": 0,
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
def generate_risk_explanation(
    asset,
    risk_assessment
):
    """
    Generate a human-readable explanation
    for an ECDAT risk assessment.
    """

    classification = asset.get(
        "classification",
        {}
    )

    risk = risk_assessment.get(
        "contextual_risk",
        risk_assessment
    )

    score = risk.get(
        "final_score",
        0
    )

    severity = risk.get(
        "severity",
        "UNKNOWN"
    )

    category = classification.get(
        "category",
        "unknown"
    )

    quantum_status = classification.get(
        "quantum_status",
        "unknown"
    )

    risk_reason = classification.get(
        "risk_reason",
        "No risk reason available."
    )

    breakdown = risk.get(
        "score_breakdown",
        {}
    )

    reasons = []

    reasons.append(
        f"The asset is classified as "
        f"{category} cryptography."
    )

    reasons.append(
        f"Quantum status is "
        f"{quantum_status}."
    )

    reasons.append(
        f"Base risk contributed "
        f"{breakdown.get('base_score', 0)} points."
    )

    reasons.append(
        f"Business criticality contributed "
        f"{breakdown.get('business_criticality_points', 0)} points."
    )

    reasons.append(
        f"Exposure contributed "
        f"{breakdown.get('exposure_points', 0)} points."
    )

    reasons.append(
        f"Mosca-style migration urgency contributed "
        f"{breakdown.get('mosca_points', 0)} points."
    )

    reasons.append(
        risk_reason
    )

    return {
        "summary": (
            f"{asset.get('name', 'Unknown asset')} "
            f"has a final quantum-risk score of "
            f"{score}/100 and a severity of "
            f"{severity}."
        ),

        "reasons": reasons
    }
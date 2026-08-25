def explain_blast_radius(
    result
):
    """
    Generate a human-readable explanation
    for a migration blast-radius assessment.
    """

    asset = result.get(
        "asset",
        "Unknown asset"
    )

    score = result.get(
        "blast_radius_score",
        0
    )

    severity = result.get(
        "severity",
        "UNKNOWN"
    )

    direct_dependencies = result.get(
        "direct_dependencies",
        {}
    ).get(
        "count",
        0
    )

    direct_dependents = result.get(
        "direct_dependents",
        {}
    ).get(
        "count",
        0
    )

    transitive_dependents = result.get(
        "transitive_dependents",
        {}
    ).get(
        "count",
        0
    )

    evidence_count = result.get(
        "evidence",
        {}
    ).get(
        "count",
        0
    )

    risk_score = result.get(
        "risk",
        {}
    ).get(
        "score",
        0
    )

    reasons = []

    # --------------------------------------------------------
    # Dependency reasons
    # --------------------------------------------------------

    if direct_dependents > 0:

        reasons.append(
            f"{direct_dependents} direct "
            f"dependent asset(s) were identified."
        )

    else:

        reasons.append(
            "No direct dependent assets "
            "were identified."
        )

    if transitive_dependents > 0:

        reasons.append(
            f"{transitive_dependents} transitive "
            f"dependent asset(s) are reachable "
            f"through the dependency graph."
        )

    if direct_dependencies > 0:

        reasons.append(
            f"The asset directly depends on "
            f"{direct_dependencies} other asset(s)."
        )

    # --------------------------------------------------------
    # Risk reason
    # --------------------------------------------------------

    if risk_score >= 75:

        reasons.append(
            f"The asset has a very high quantum-risk "
            f"score of {risk_score}."
        )

    elif risk_score >= 50:

        reasons.append(
            f"The asset has a high quantum-risk "
            f"score of {risk_score}."
        )

    elif risk_score > 0:

        reasons.append(
            f"The asset has a quantum-risk "
            f"score of {risk_score}."
        )

    else:

        reasons.append(
            "No quantum-risk score was available."
        )

    # --------------------------------------------------------
    # Evidence reason
    # --------------------------------------------------------

    if evidence_count > 0:

        reasons.append(
            f"{evidence_count} CBOM evidence "
            f"occurrence(s) support the asset."
        )

    else:

        reasons.append(
            "No CBOM evidence occurrences "
            "were available."
        )

    # --------------------------------------------------------
    # Severity interpretation
    # --------------------------------------------------------

    if severity == "CRITICAL":

        reasons.append(
            "The combination of dependency impact "
            "and cryptographic risk produces a "
            "critical potential migration impact."
        )

    elif severity == "HIGH":

        reasons.append(
            "The dependency structure and "
            "cryptographic risk indicate a high "
            "potential migration impact."
        )

    elif severity == "MEDIUM":

        reasons.append(
            "The asset has a moderate potential "
            "migration impact."
        )

    else:

        reasons.append(
            "The asset has a relatively low "
            "potential migration impact."
        )

    summary = (
        f"{asset} has a potential migration "
        f"blast-radius score of {score}/100 "
        f"and a severity of {severity}."
    )

    return {
        "summary": summary,
        "reasons": reasons
    }
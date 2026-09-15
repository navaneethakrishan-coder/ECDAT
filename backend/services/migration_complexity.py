def calculate_migration_complexity(
    asset,
    classification,
    risk_assessment,
    blast_radius
):
    """
    Calculate explainable migration complexity.

    This score estimates implementation/migration difficulty.
    It is NOT a guarantee of actual engineering effort.
    """

    # ========================================================
    # Extract data
    # ========================================================

    category = classification.get(
        "category",
        "unknown"
    )

    purpose = classification.get(
        "purpose",
        []
    )

    quantum_status = classification.get(
        "quantum_status",
        "unknown"
    )

    context = risk_assessment.get(
        "context",
        {}
    )

    migration_time = context.get(
        "migration_time_years",
        0
    )

    data_lifetime = context.get(
        "data_lifetime_years",
        0
    )

    business_criticality = context.get(
        "business_criticality",
        "LOW"
    )

    exposure = context.get(
        "exposure",
        "INTERNAL"
    )

    evidence_quality = risk_assessment.get(
        "evidence_quality",
        {}
    )

    evidence_count = evidence_quality.get(
        "evidence_count",
        0
    )

    # ========================================================
    # Dependency information
    # ========================================================

    direct_dependents = blast_radius.get(
        "direct_dependents",
        {}
    ).get(
        "count",
        0
    )

    transitive_dependents = blast_radius.get(
        "transitive_dependents",
        {}
    ).get(
        "count",
        0
    )

    # ========================================================
    # Factor 1 — Cryptographic complexity
    # ========================================================

    crypto_score = 0

    if category == "asymmetric":
        crypto_score = 20

    elif category == "symmetric":
        crypto_score = 12

    elif category == "hash":
        crypto_score = 8

    elif category == "mac":
        crypto_score = 8

    elif category == "kdf":
        crypto_score = 10

    elif category == "protocol":
        crypto_score = 15

    else:
        crypto_score = 5

    # Key agreement / signatures generally involve
    # broader migration considerations.
    #
    # (Incidental fix: this previously checked the literal string
    # "signature", which no classification stage has ever emitted --
    # every signature-purpose finding uses "digital-signature" -- so
    # this bonus never actually applied. Found while wiring in
    # repository-specific purpose resolution, fixed here since it's
    # the same "purpose" value this round is about getting right.)

    if (
        "key-agreement" in purpose
        or "digital-signature" in purpose
    ):
        crypto_score += 5

    crypto_score = min(
        crypto_score,
        25
    )

    # ========================================================
    # Factor 2 — Dependency complexity
    # ========================================================

    dependency_score = (
        min(
            direct_dependents * 3,
            20
        )
        +
        min(
            transitive_dependents * 2,
            15
        )
    )

    dependency_score = min(
        dependency_score,
        35
    )

    # ========================================================
    # Factor 3 — Migration time
    # ========================================================

    if migration_time >= 5:
        migration_time_score = 20

    elif migration_time >= 4:
        migration_time_score = 16

    elif migration_time >= 3:
        migration_time_score = 12

    elif migration_time >= 2:
        migration_time_score = 8

    elif migration_time >= 1:
        migration_time_score = 4

    else:
        migration_time_score = 0

    # ========================================================
    # Factor 4 — Evidence/source surface
    # ========================================================

    evidence_score = min(
        evidence_count * 2,
        10
    )

    # ========================================================
    # Factor 5 — Data lifetime pressure
    # ========================================================

    if data_lifetime >= 15:
        lifetime_score = 10

    elif data_lifetime >= 10:
        lifetime_score = 8

    elif data_lifetime >= 5:
        lifetime_score = 5

    elif data_lifetime >= 2:
        lifetime_score = 3

    else:
        lifetime_score = 0

    # ========================================================
    # Raw complexity score
    # ========================================================

    raw_score = (
        crypto_score
        + dependency_score
        + migration_time_score
        + evidence_score
        + lifetime_score
    )

    score = min(
        round(raw_score, 2),
        100
    )

    # ========================================================
    # Complexity level
    # ========================================================

    if score >= 75:
        level = "CRITICAL"

    elif score >= 50:
        level = "HIGH"

    elif score >= 25:
        level = "MEDIUM"

    else:
        level = "LOW"

    # ========================================================
    # Explanation
    # ========================================================

    reasons = []

    reasons.append(
        f"Cryptographic category: {category}."
    )

    if purpose:
        reasons.append(
            "Cryptographic purpose: "
            + ", ".join(purpose)
            + "."
        )

    if direct_dependents > 0:
        reasons.append(
            f"{direct_dependents} direct dependent "
            f"asset(s) increase migration complexity."
        )

    if transitive_dependents > 0:
        reasons.append(
            f"{transitive_dependents} transitive dependent "
            f"asset(s) may be affected."
        )

    reasons.append(
        f"Estimated migration time: "
        f"{migration_time} year(s)."
    )

    if evidence_count > 0:
        reasons.append(
            f"{evidence_count} evidence occurrence(s) "
            f"indicate source-level migration surface."
        )

    if data_lifetime > 0:
        reasons.append(
            f"Protected data lifetime: "
            f"{data_lifetime} year(s)."
        )

    reasons.append(
        f"Quantum status: {quantum_status}."
    )

    summary = (
        f"{asset.get('name', 'Unknown')} has an "
        f"estimated migration complexity score of "
        f"{score}/100 and a complexity level of "
        f"{level}."
    )

    return {
        "score": score,

        "level": level,

        "factors": {
            "cryptographic_complexity": crypto_score,

            "dependency_complexity": dependency_score,

            "migration_time_complexity":
                migration_time_score,

            "evidence_surface":
                evidence_score,

            "data_lifetime_pressure":
                lifetime_score
        },

        "context": {
            "category": category,

            "purpose": purpose,

            "quantum_status":
                quantum_status,

            "business_criticality":
                business_criticality,

            "exposure": exposure,

            "migration_time_years":
                migration_time,

            "data_lifetime_years":
                data_lifetime,

            "direct_dependents":
                direct_dependents,

            "transitive_dependents":
                transitive_dependents,

            "evidence_count":
                evidence_count
        },

        "explanation": {
            "summary": summary,

            "reasons": reasons
        }
    }
def calculate_migration_priority(
    risk_score,
    blast_radius_score,
    complexity_score
):
    """
    Calculate migration priority from three
    independent ECDAT dimensions.

    Risk        = 40%
    Blast Radius = 35%
    Complexity  = 25%
    """

    risk_score = max(
        0,
        min(100, float(risk_score))
    )

    blast_radius_score = max(
        0,
        min(100, float(blast_radius_score))
    )

    complexity_score = max(
        0,
        min(100, float(complexity_score))
    )

    weighted_risk = (
        risk_score * 0.40
    )

    weighted_blast = (
        blast_radius_score * 0.35
    )

    weighted_complexity = (
        complexity_score * 0.25
    )

    priority_score = round(
        weighted_risk
        + weighted_blast
        + weighted_complexity,
        2
    )

    if priority_score >= 75:
        priority = "CRITICAL"

    elif priority_score >= 60:
        priority = "HIGH"

    elif priority_score >= 40:
        priority = "MEDIUM"

    else:
        priority = "LOW"

    return {
        "priority_score": priority_score,

        "priority": priority,

        "score_breakdown": {
            "quantum_risk": {
                "raw_score": risk_score,
                "weight": 0.40,
                "weighted_score":
                    round(weighted_risk, 2)
            },

            "blast_radius": {
                "raw_score":
                    blast_radius_score,
                "weight": 0.35,
                "weighted_score":
                    round(weighted_blast, 2)
            },

            "migration_complexity": {
                "raw_score":
                    complexity_score,
                "weight": 0.25,
                "weighted_score":
                    round(weighted_complexity, 2)
            }
        },

        "explanation": {
            "summary": (
                f"Migration priority is "
                f"{priority_score}/100 "
                f"({priority})."
            ),

            "reasons": [
                f"Quantum-risk contribution: "
                f"{round(weighted_risk, 2)}.",

                f"Blast-radius contribution: "
                f"{round(weighted_blast, 2)}.",

                f"Migration-complexity contribution: "
                f"{round(weighted_complexity, 2)}."
            ]
        }
    }
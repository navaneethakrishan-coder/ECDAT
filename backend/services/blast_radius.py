from services.dependency_graph import (
    get_direct_dependencies,
    get_direct_dependents,
    get_transitive_dependents
)


def calculate_blast_radius(
    asset,
    graph,
    risk_assessment=None
):
    """
    Calculate the potential migration blast radius
    of a cryptographic asset.

    This measures potential dependency impact.
    It does not claim that every connected asset
    must necessarily be changed.
    """

    asset_ref = asset.get("bom_ref")

    # --------------------------------------------------------
    # Dependency impact
    # --------------------------------------------------------

    direct_dependencies = get_direct_dependencies(
        graph,
        asset_ref
    )

    direct_dependents = get_direct_dependents(
        graph,
        asset_ref
    )

    transitive_dependents = get_transitive_dependents(
        graph,
        asset_ref
    )

    # --------------------------------------------------------
    # Evidence impact
    # --------------------------------------------------------

    occurrences = asset.get(
        "occurrences",
        []
    )

    evidence_count = len(
        occurrences
    )

    # --------------------------------------------------------
    # Dependency scores
    # --------------------------------------------------------

    direct_dependency_score = min(
        len(direct_dependencies) * 5,
        15
    )

    direct_dependent_score = min(
        len(direct_dependents) * 10,
        30
    )

    transitive_score = min(
        len(transitive_dependents) * 5,
        30
    )

    # --------------------------------------------------------
    # Evidence score
    # --------------------------------------------------------

    evidence_score = min(
        evidence_count * 5,
        10
    )

    # --------------------------------------------------------
    # Risk contribution
    # --------------------------------------------------------

    risk_score = 0

    if risk_assessment:

        risk_score = risk_assessment.get(
            "final_score",
            risk_assessment.get(
                "score",
                0
            )
        )

    risk_contribution = min(
        risk_score * 0.15,
        15
    )

    # --------------------------------------------------------
    # Final blast-radius score
    # --------------------------------------------------------

    raw_score = (
        direct_dependency_score
        + direct_dependent_score
        + transitive_score
        + evidence_score
        + risk_contribution
    )

    score = min(
        round(raw_score, 2),
        100
    )

    # --------------------------------------------------------
    # Severity
    # --------------------------------------------------------

    if score >= 75:
        severity = "CRITICAL"

    elif score >= 50:
        severity = "HIGH"

    elif score >= 25:
        severity = "MEDIUM"

    else:
        severity = "LOW"

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "asset": asset.get(
            "name"
        ),

        "asset_ref": asset_ref,
        "bom_ref": asset_ref,

        "blast_radius_score": score,

        "severity": severity,

        "direct_dependencies": {
            "count": len(
                direct_dependencies
            ),
            "refs": direct_dependencies
        },

        "direct_dependents": {
            "count": len(
                direct_dependents
            ),
            "refs": direct_dependents
        },

        "transitive_dependents": {
            "count": len(
                transitive_dependents
            ),
            "refs": transitive_dependents
        },

        "evidence": {
            "count": evidence_count
        },

        "risk": {
            "score": risk_score
        },

        "score_breakdown": {
            "direct_dependency_score":
                direct_dependency_score,

            "direct_dependent_score":
                direct_dependent_score,

            "transitive_score":
                transitive_score,

            "evidence_score":
                evidence_score,

            "risk_contribution":
                round(
                    risk_contribution,
                    2
                )
        }
    }

"""
Human-readable explanation of one ECDAT contextual risk assessment.

Every sentence here is derived from a value
services/contextual_risk.calculate_contextual_risk() actually computed
for this finding -- its `score_breakdown`, `context`, `base_risk`,
`evidence_quality` and `mosca_analysis` -- never from a default. The
previous version looked up flat keys (`base_score`,
`business_criticality_points`, `exposure_points`, `mosca_points`) that
calculate_contextual_risk() has never emitted: its breakdown is keyed
by factor (`quantum_risk`, `business_criticality`, `data_lifetime`,
`exposure`, `migration_time`, `evidence_quality`), each holding
`raw_score`/`weight`/`weighted_score` (or `known: False` plus a reason
when the factor was excluded as UNKNOWN). Every lookup therefore fell
back to 0, so every finding's explanation claimed zero-point
contributions, omitted two real factors entirely, and described Mosca
urgency as a score contribution even though Mosca is informational
only and never weighted into the risk score.

`contributions` is returned alongside the prose so the explanation is
machine-checkable: the sum of the displayed (2-decimal) contributions
reconciles with `final_score` to within per-term rounding.
"""


# Canonical factor order and display labels -- the keys
# calculate_contextual_risk() writes into score_breakdown.
FACTOR_LABELS = (
    ("quantum_risk", "Quantum risk"),
    ("business_criticality", "Business criticality"),
    ("data_lifetime", "Data lifetime"),
    ("exposure", "Exposure"),
    ("migration_time", "Migration time"),
    ("evidence_quality", "Evidence quality"),
)


def _factor_input(key, context, base_risk, evidence_quality):
    """Describe the real input that produced a factor's raw score."""

    if key == "quantum_risk":
        return (
            f"quantum status '{base_risk.get('quantum_status')}', "
            f"category '{base_risk.get('category')}'"
        )

    if key == "business_criticality":
        return f"level {context.get('business_criticality')}"

    if key == "data_lifetime":
        return f"{context.get('data_lifetime_years')} year(s)"

    if key == "exposure":
        return f"exposure {context.get('exposure')}"

    if key == "migration_time":
        return f"{context.get('migration_time_years')} year(s)"

    if key == "evidence_quality":
        return (
            f"{evidence_quality.get('quality')} quality from "
            f"{evidence_quality.get('evidence_count')} occurrence(s)"
        )

    return None


def generate_risk_explanation(
    asset,
    risk_assessment
):
    """
    Generate a human-readable, traceable explanation for an ECDAT
    contextual risk assessment (the dict returned by
    calculate_contextual_risk()).
    """

    classification = asset.get("classification") or {}

    risk = risk_assessment.get(
        "contextual_risk",
        risk_assessment
    ) or {}

    score = risk.get("final_score")
    severity = risk.get("severity", "UNKNOWN")

    breakdown = risk.get("score_breakdown") or {}
    context = risk.get("context") or {}
    base_risk = risk.get("base_risk") or {}
    evidence_quality = risk.get("evidence_quality") or {}
    mosca = risk.get("mosca_analysis")

    reasons = [
        f"The asset is classified as "
        f"{classification.get('category', 'unknown')} cryptography.",

        f"Quantum status is "
        f"{classification.get('quantum_status', 'unknown')}.",
    ]

    contributions = []

    for key, label in FACTOR_LABELS:

        entry = breakdown.get(key)

        # A factor the calculation did not produce is not mentioned
        # at all -- never reported as a zero-point contribution.
        if not isinstance(entry, dict):
            continue

        if entry.get("known") is False:
            contributions.append({
                "factor": key,
                "label": label,
                "known": False,
                "reason": entry.get("reason"),
            })

            reasons.append(
                f"{label} is UNKNOWN for this finding, so it was "
                "excluded from the weighting rather than guessed; the "
                "remaining factors' weights were rescaled to compensate."
            )
            continue

        weighted_score = entry.get("weighted_score")

        if weighted_score is None:
            continue

        factor_input = _factor_input(
            key,
            context,
            base_risk,
            evidence_quality,
        )

        contributions.append({
            "factor": key,
            "label": label,
            "known": True,
            "raw_score": entry.get("raw_score"),
            "weight": entry.get("weight"),
            "weighted_score": weighted_score,
            "input": factor_input,
        })

        reasons.append(
            f"{label} contributed {weighted_score} points "
            f"(score {entry.get('raw_score')} x weight {entry.get('weight')}; "
            f"{factor_input})."
        )

    contribution_total = round(
        sum(
            item["weighted_score"]
            for item in contributions
            if item["known"]
        ),
        2,
    )

    # Mosca is informational: calculate_contextual_risk() computes it
    # only when a data lifetime is configured, and never adds it to
    # final_score. Say exactly that, never "contributed N points".
    if isinstance(mosca, dict):
        reasons.append(
            "Mosca timeline (informational only, not a weighted risk "
            f"factor): {mosca.get('explanation')} "
            f"Migration urgency: {mosca.get('migration_urgency')}."
        )
    else:
        reasons.append(
            "Mosca timeline analysis was not performed because no data "
            "lifetime is configured for this finding (it is "
            "informational only and never a weighted risk factor)."
        )

    risk_reason = classification.get("risk_reason")

    if risk_reason:
        reasons.append(risk_reason)

    return {
        "summary": (
            f"{asset.get('name', 'Unknown asset')} "
            f"has a final quantum-risk score of "
            f"{score}/100 and a severity of "
            f"{severity}."
        ),

        "reasons": reasons,

        "contributions": contributions,

        "contribution_total": contribution_total,

        "final_score": score,
    }

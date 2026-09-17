from services.business_context import (
    BUSINESS_CRITICALITY_SCORES,
    MOSCA_URGENCY_SCORES,
)


# ================================================================
# Base weights, used when every factor is known.
#
# Risk/blast-radius/complexity keep their original 0.40/0.35/0.25
# ratio (8:7:5) -- just rescaled to make room for two more factors --
# so that when business_criticality and mosca_urgency are both
# UNKNOWN (the default, until an organization configures
# data/business-context.json -- see services/business_context.py),
# renormalizing across only the known factors reproduces the exact
# original 0.40/0.35/0.25 formula. See _normalized_weights() below:
# this is a deliberate property, not a coincidence, and is what keeps
# "no business context configured" numerically identical to the
# previous behavior rather than silently shifting every priority
# score the moment this feature was added.
# ================================================================

BASE_WEIGHTS = {
    "quantum_risk": 0.32,
    "blast_radius": 0.28,
    "migration_complexity": 0.20,
    "business_criticality": 0.10,
    "mosca_urgency": 0.10,
}


def _normalized_weights(known_keys):
    """
    Weights for exactly the factors in `known_keys`, rescaled so they
    sum to 1.0 -- i.e. a weighted AVERAGE over only what is actually
    known, never a weighted SUM diluted by treating an unknown factor
    as zero (which would silently penalize every finding an
    organization hasn't configured business context for yet).
    """

    total = sum(BASE_WEIGHTS[key] for key in known_keys)

    return {key: BASE_WEIGHTS[key] / total for key in known_keys}


def calculate_migration_priority(
    risk_score,
    blast_radius_score,
    complexity_score,
    business_criticality=None,
    mosca_urgency=None,
):
    """
    Calculate migration priority -- "how urgently should this
    organization migrate this finding", as distinct from risk ("how
    dangerous is this cryptographic finding"), which is computed
    entirely upstream and only enters here as `risk_score`.

    Always-known technical dimensions:
      - risk_score            (upstream quantum-risk figure)
      - blast_radius_score    (dependency-graph technical impact)
      - complexity_score      (estimated migration difficulty)

    Optional organization-provided dimensions (see
    services/business_context.py -- both None/UNKNOWN unless an
    organization has explicitly configured
    data/business-context.json for this specific finding):
      - business_criticality  ("LOW"/"MEDIUM"/"HIGH"/"CRITICAL")
      - mosca_urgency          ("LOW"/"MEDIUM"/"HIGH"/"CRITICAL",
                                 from services/mosca_analysis.py's
                                 data-lifetime-vs-threat-horizon
                                 comparison)

    A factor that is None is never scored as if it were zero or any
    other fabricated value -- it is excluded entirely, and the
    remaining factors' weights are rescaled to still sum to 1.0 (see
    _normalized_weights). This is why calling this function with only
    the three technical arguments reproduces the exact score this
    function has always returned.
    """

    risk_score = max(0, min(100, float(risk_score)))
    blast_radius_score = max(0, min(100, float(blast_radius_score)))
    complexity_score = max(0, min(100, float(complexity_score)))

    raw_scores = {
        "quantum_risk": risk_score,
        "blast_radius": blast_radius_score,
        "migration_complexity": complexity_score,
    }

    unknown_factors = []

    normalized_criticality = None
    if isinstance(business_criticality, str):
        normalized_criticality = business_criticality.strip().upper()

    if normalized_criticality in BUSINESS_CRITICALITY_SCORES:
        raw_scores["business_criticality"] = BUSINESS_CRITICALITY_SCORES[normalized_criticality]
    else:
        unknown_factors.append("business_criticality")

    normalized_mosca = None
    if isinstance(mosca_urgency, str):
        normalized_mosca = mosca_urgency.strip().upper()

    if normalized_mosca in MOSCA_URGENCY_SCORES:
        raw_scores["mosca_urgency"] = MOSCA_URGENCY_SCORES[normalized_mosca]
    else:
        unknown_factors.append("mosca_urgency")

    weights = _normalized_weights(raw_scores.keys())

    # Unrounded weighted values feed the actual priority_score (summed
    # once, then rounded once) -- matching this function's original
    # behavior exactly rather than compounding per-term rounding.
    # `weighted` (rounded, for display only) is derived afterward.
    exact_weighted = {
        key: raw_scores[key] * weights[key]
        for key in raw_scores
    }

    priority_score = round(sum(exact_weighted.values()), 2)

    weighted = {
        key: round(value, 2)
        for key, value in exact_weighted.items()
    }

    if priority_score >= 75:
        priority = "CRITICAL"

    elif priority_score >= 60:
        priority = "HIGH"

    elif priority_score >= 40:
        priority = "MEDIUM"

    else:
        priority = "LOW"

    # ------------------------------------------------------------
    # Explainability: every KNOWN factor gets a real weight/score/
    # contribution entry; every UNKNOWN factor is still named (so a
    # judge or user can see it exists and why it isn't counted) but
    # carries no fabricated score, weight or contribution.
    # ------------------------------------------------------------

    factor_labels = {
        "quantum_risk": "Quantum-risk",
        "blast_radius": "Blast-radius",
        "migration_complexity": "Migration-complexity",
        "business_criticality": "Business-criticality",
        "mosca_urgency": "Mosca/data-lifetime urgency",
    }

    score_breakdown = {}

    for key in ("quantum_risk", "blast_radius", "migration_complexity", "business_criticality", "mosca_urgency"):

        if key in raw_scores:
            score_breakdown[key] = {
                "known": True,
                "raw_score": raw_scores[key],
                "weight": round(weights[key], 4),
                "weighted_score": weighted[key],
            }

        else:
            score_breakdown[key] = {
                "known": False,
                "reason": "Not configured for this finding (see data/business-context.json).",
            }

    reasons = [
        f"{factor_labels[key]} contribution: {weighted[key]}."
        for key in ("quantum_risk", "blast_radius", "migration_complexity", "business_criticality", "mosca_urgency")
        if key in raw_scores
    ]

    for key in unknown_factors:
        reasons.append(
            f"{factor_labels[key]} is UNKNOWN for this finding, so it was excluded "
            "rather than guessed; the remaining factors' weights were rescaled to compensate."
        )

    return {
        "priority_score": priority_score,

        "priority": priority,

        "score_breakdown": score_breakdown,

        "unknown_factors": unknown_factors,

        "explanation": {
            "summary": (
                f"Migration priority is {priority_score}/100 ({priority})."
            ),

            "reasons": reasons,
        },
    }

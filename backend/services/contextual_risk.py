from models.risk_factors import RiskContext
from services.risk_engine import calculate_base_risk
from services.mosca_analysis import calculate_mosca_risk
from services.evidence_engine import calculate_evidence_quality


# ================================================================
# Base weights, used when every factor is known.
#
# Unchanged from the original 40/20/15/10/10/5 model. When
# data_lifetime is UNKNOWN (see below), it is excluded and the
# remaining five factors' weights are rescaled to sum to 1.0 --
# never scored as 0 years (which would itself be a fabricated,
# maximally-favorable guess) and never silently defaulted to a
# specific number. This is the same exclude-and-renormalize pattern
# services/migration_priority.py already uses for business
# criticality and Mosca urgency, applied here to keep this weighted
# average mathematically honest instead of building a second,
# different UNKNOWN-handling scheme.
# ================================================================

BASE_WEIGHTS = {
    "quantum_risk": 0.40,
    "business_criticality": 0.20,
    "data_lifetime": 0.15,
    "exposure": 0.10,
    "migration_time": 0.10,
    "evidence_quality": 0.05,
}


def _normalized_weights(known_keys):
    total = sum(BASE_WEIGHTS[key] for key in known_keys)
    return {key: BASE_WEIGHTS[key] / total for key in known_keys}


def calculate_contextual_risk(asset, context: RiskContext):
    """
    Calculate the final normalized ECDAT quantum-risk score.

    Weighted model (all factors known):

        Quantum Risk          40%
        Business Criticality  20%
        Data Lifetime         15%
        Exposure              10%
        Migration Time        10%
        Evidence Quality       5%

        Total                100%

    `context.data_lifetime_years` is None whenever no organization-
    provided value exists for this finding (see
    services/business_context.py and services/risk_context.py) --
    it is never a fabricated number. When it is None, the Data
    Lifetime factor is excluded from this weighted average entirely,
    and the remaining five factors' weights are rescaled to still sum
    to 1.0 (see _normalized_weights) rather than treating the missing
    factor as 0 years (the most favorable possible score) or any
    other guess. This is why calling this function with a known
    data_lifetime_years continues to produce exactly the same
    final_score this function has always returned for that input --
    see test_contextual_risk.py, unchanged.
    """

    # -----------------------------------------
    # Base quantum risk
    # -----------------------------------------

    base_risk = calculate_base_risk(
        asset
    )

    quantum_score = base_risk["score"]

    # -----------------------------------------
    # Business criticality
    # -----------------------------------------

    criticality_scores = {
        "LOW": 0,
        "MEDIUM": 50,
        "HIGH": 80,
        "CRITICAL": 100
    }

    criticality_score = criticality_scores.get(
        context.business_criticality.upper(),
        50
    )

    # -----------------------------------------
    # Data lifetime -- UNKNOWN-aware (see docstring above)
    # -----------------------------------------

    data_lifetime_known = context.data_lifetime_years is not None

    if data_lifetime_known:
        # 0 years = 0
        # 20+ years = 100
        data_lifetime_score = min(
            max(context.data_lifetime_years, 0) / 20 * 100,
            100
        )
    else:
        data_lifetime_score = None

    # -----------------------------------------
    # Exposure
    # -----------------------------------------

    exposure_scores = {
        "ISOLATED": 0,
        "INTERNAL": 50,
        "INTERNET": 100
    }

    exposure_score = exposure_scores.get(
        context.exposure.upper(),
        50
    )

    # -----------------------------------------
    # Migration time
    # -----------------------------------------

    # 0 years = 0
    # 10+ years = 100

    migration_score = min(
        max(context.migration_time_years, 0) / 10 * 100,
        100
    )

    # -----------------------------------------
    # Mosca analysis
    #
    # Mosca urgency fundamentally depends on knowing the protected
    # data's lifetime -- with data_lifetime_years UNKNOWN, there is
    # no honest "combined time vs. threat horizon" comparison to make,
    # so this is skipped entirely rather than computed against a
    # guessed lifetime. Mirrors the same gate
    # services/business_context.calculate_mosca_urgency() already
    # applies for the migration-priority model, so the two paths
    # agree on when Mosca urgency can and cannot be determined.
    # -----------------------------------------

    if data_lifetime_known:
        mosca = calculate_mosca_risk(
            context
        )

        mosca_urgency_scores = {
            "LOW": 0,
            "MEDIUM": 60,
            "HIGH": 80,
            "CRITICAL": 100
        }

        mosca_score = mosca_urgency_scores.get(
            mosca["migration_urgency"],
            0
        )
    else:
        mosca = None
        mosca_score = None

    # -----------------------------------------
    # Evidence quality
    # -----------------------------------------

    evidence = calculate_evidence_quality(
        asset
    )

    evidence_score = evidence["score"]

    # -----------------------------------------
    # Weighted final score -- exclude-and-renormalize for any
    # UNKNOWN factor (currently only data_lifetime can be UNKNOWN).
    # -----------------------------------------

    raw_scores = {
        "quantum_risk": quantum_score,
        "business_criticality": criticality_score,
        "exposure": exposure_score,
        "migration_time": migration_score,
        "evidence_quality": evidence_score,
    }

    if data_lifetime_known:
        raw_scores["data_lifetime"] = data_lifetime_score

    weights = _normalized_weights(raw_scores.keys())

    exact_weighted = {
        key: raw_scores[key] * weights[key]
        for key in raw_scores
    }

    final_score = round(min(sum(exact_weighted.values()), 100), 2)

    weighted = {
        key: round(value, 2)
        for key, value in exact_weighted.items()
    }

    # -----------------------------------------
    # Severity
    # -----------------------------------------

    if final_score >= 80:
        severity = "CRITICAL"

    elif final_score >= 60:
        severity = "HIGH"

    elif final_score >= 30:
        severity = "MEDIUM"

    else:
        severity = "LOW"

    # -----------------------------------------
    # Score breakdown -- data_lifetime always appears, marked
    # known/unknown, exactly like migration_priority.py's own
    # breakdown does for business_criticality/mosca_urgency.
    # -----------------------------------------

    score_breakdown = {
        "quantum_risk": {
            "raw_score": quantum_score,
            "weight": round(weights["quantum_risk"], 4),
            "weighted_score": weighted["quantum_risk"],
        },

        "business_criticality": {
            "raw_score": criticality_score,
            "weight": round(weights["business_criticality"], 4),
            "weighted_score": weighted["business_criticality"],
        },

        "exposure": {
            "raw_score": exposure_score,
            "weight": round(weights["exposure"], 4),
            "weighted_score": weighted["exposure"],
        },

        "migration_time": {
            "raw_score": round(migration_score, 2),
            "weight": round(weights["migration_time"], 4),
            "weighted_score": weighted["migration_time"],
        },

        "evidence_quality": {
            "raw_score": evidence_score,
            "weight": round(weights["evidence_quality"], 4),
            "weighted_score": weighted["evidence_quality"],
        },
    }

    if data_lifetime_known:
        score_breakdown["data_lifetime"] = {
            "known": True,
            "raw_score": round(data_lifetime_score, 2),
            "weight": round(weights["data_lifetime"], 4),
            "weighted_score": weighted["data_lifetime"],
        }
    else:
        score_breakdown["data_lifetime"] = {
            "known": False,
            "reason": (
                "No confidentiality data-lifetime is configured for this "
                "finding (see data/business-context.json) -- excluded "
                "from the risk weighting rather than guessed; the "
                "remaining factors' weights were rescaled to compensate."
            ),
        }

    return {

        "base_risk": base_risk,

        "context": {
            "business_criticality":
                context.business_criticality,

            "data_lifetime_years":
                context.data_lifetime_years,

            "data_lifetime_known":
                data_lifetime_known,

            "migration_time_years":
                context.migration_time_years,

            "exposure":
                context.exposure,

            "quantum_threat_horizon_years":
                context.quantum_threat_horizon_years
        },

        "mosca_analysis": mosca,

        "evidence_quality": evidence,

        "score_breakdown": score_breakdown,

        "final_score": final_score,

        "severity": severity
    }

from models.risk_factors import RiskContext
from services.risk_engine import calculate_base_risk
from services.mosca_analysis import calculate_mosca_risk
from services.evidence_engine import calculate_evidence_quality


def calculate_contextual_risk(asset, context: RiskContext):
    """
    Calculate the final normalized ECDAT quantum-risk score.

    Weighted model:

        Quantum Risk          40%
        Business Criticality  20%
        Data Lifetime         15%
        Exposure              10%
        Migration Time        10%
        Evidence Quality       5%

        Total                100%
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
    # Data lifetime
    # -----------------------------------------

    # 0 years = 0
    # 20+ years = 100

    data_lifetime_score = min(
        max(context.data_lifetime_years, 0) / 20 * 100,
        100
    )

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
    # -----------------------------------------

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

    # -----------------------------------------
    # Evidence quality
    # -----------------------------------------

    evidence = calculate_evidence_quality(
        asset
    )

    evidence_score = evidence["score"]

    # -----------------------------------------
    # Weighted final score
    # -----------------------------------------

    weighted_quantum = quantum_score * 0.40

    weighted_criticality = (
        criticality_score * 0.20
    )

    weighted_data_lifetime = (
        data_lifetime_score * 0.15
    )

    weighted_exposure = (
        exposure_score * 0.10
    )

    weighted_migration = (
        migration_score * 0.10
    )

    weighted_evidence = (
        evidence_score * 0.05
    )

    final_score = (
        weighted_quantum
        + weighted_criticality
        + weighted_data_lifetime
        + weighted_exposure
        + weighted_migration
        + weighted_evidence
    )

    final_score = round(
        min(final_score, 100),
        2
    )

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

    return {

        "base_risk": base_risk,

        "context": {
            "business_criticality":
                context.business_criticality,

            "data_lifetime_years":
                context.data_lifetime_years,

            "migration_time_years":
                context.migration_time_years,

            "exposure":
                context.exposure,

            "quantum_threat_horizon_years":
                context.quantum_threat_horizon_years
        },

        "mosca_analysis": mosca,

        "evidence_quality": evidence,

        "score_breakdown": {

            "quantum_risk": {
                "raw_score": quantum_score,
                "weight": 0.40,
                "weighted_score":
                    round(weighted_quantum, 2)
            },

            "business_criticality": {
                "raw_score": criticality_score,
                "weight": 0.20,
                "weighted_score":
                    round(weighted_criticality, 2)
            },

            "data_lifetime": {
                "raw_score":
                    round(data_lifetime_score, 2),
                "weight": 0.15,
                "weighted_score":
                    round(weighted_data_lifetime, 2)
            },

            "exposure": {
                "raw_score": exposure_score,
                "weight": 0.10,
                "weighted_score":
                    round(weighted_exposure, 2)
            },

            "migration_time": {
                "raw_score":
                    round(migration_score, 2),
                "weight": 0.10,
                "weighted_score":
                    round(weighted_migration, 2)
            },

            "evidence_quality": {
                "raw_score": evidence_score,
                "weight": 0.05,
                "weighted_score":
                    round(weighted_evidence, 2)
            }
        },

        "final_score": final_score,

        "severity": severity
    }
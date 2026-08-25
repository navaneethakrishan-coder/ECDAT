from models.risk_factors import RiskContext


def calculate_mosca_risk(context: RiskContext):
    """
    Perform a simplified Mosca-style timeline analysis.

    Core idea:

        Data Lifetime + Migration Time
                    >
             Quantum Threat Horizon

    indicates that migration planning is urgent.
    """

    combined_time = (
        context.data_lifetime_years
        + context.migration_time_years
    )

    threat_horizon = (
        context.quantum_threat_horizon_years
    )

    if combined_time > threat_horizon:

        urgency = "CRITICAL"

    elif combined_time >= threat_horizon * 0.8:

        urgency = "HIGH"

    elif combined_time >= threat_horizon * 0.5:

        urgency = "MEDIUM"

    else:

        urgency = "LOW"

    return {
        "data_lifetime_years":
            context.data_lifetime_years,

        "migration_time_years":
            context.migration_time_years,

        "combined_time_years":
            combined_time,

        "quantum_threat_horizon_years":
            threat_horizon,

        "migration_urgency":
            urgency,

        "explanation": (
            f"Protected data lifetime "
            f"({context.data_lifetime_years} years) + "
            f"estimated migration time "
            f"({context.migration_time_years} years) = "
            f"{combined_time} years, compared with a "
            f"{threat_horizon}-year quantum threat horizon."
        )
    }
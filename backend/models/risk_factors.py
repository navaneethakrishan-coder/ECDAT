from dataclasses import dataclass


@dataclass
class RiskContext:
    """
    Contextual information used for enterprise
    quantum-risk assessment.
    """

    business_criticality: str = "MEDIUM"

    data_lifetime_years: int = 5

    migration_time_years: int = 2

    exposure: str = "INTERNAL"

    quantum_threat_horizon_years: int = 10
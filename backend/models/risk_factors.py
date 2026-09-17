from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskContext:
    """
    Contextual information used for enterprise
    quantum-risk assessment.

    `data_lifetime_years` is None (UNKNOWN) by default -- it is an
    organizational fact (how long protected data must stay
    confidential) that nothing in ECDAT can observe on its own; the
    active pipeline (services/risk_context.py) always supplies an
    explicit value here, sourced from services/business_context.py,
    and never relies on this class-level default. See
    services/contextual_risk.py for how a None value is excluded
    (not guessed) from the risk calculation.
    """

    business_criticality: str = "MEDIUM"

    data_lifetime_years: Optional[int] = None

    migration_time_years: int = 2

    exposure: str = "INTERNAL"

    quantum_threat_horizon_years: int = 10
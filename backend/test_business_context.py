"""
Regression tests for wiring organization-provided business
criticality and Mosca-style data-lifetime urgency into the live
migration-priority ranking (services/business_context.py +
services/migration_priority.py).

These tests exercise the GENERIC mechanism -- unit-level scoring
behavior and a config-driven end-to-end path -- rather than any one
repository's dataset, so they hold regardless of what repository was
analyzed.
"""

import json
import tempfile
from pathlib import Path

import services.business_context as business_context
from services.migration_priority import calculate_migration_priority
from services.mosca_analysis import calculate_mosca_risk
from models.risk_factors import RiskContext


# ================================================================
# Helpers
# ================================================================


def _use_config(config_dict, test_fn):
    """
    Point services.business_context at a throwaway config file for
    the duration of `test_fn`, then restore the module's real,
    unmodified config path and cache -- never touches
    data/business-context.json itself.
    """

    original_path = business_context.CONFIG_PATH

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "business-context.json"
        config_path.write_text(json.dumps(config_dict), encoding="utf-8")

        business_context.CONFIG_PATH = config_path
        business_context.reload_config()

        try:
            test_fn()
        finally:
            business_context.CONFIG_PATH = original_path
            business_context.reload_config()


# ================================================================
# A. Same risk, different business criticality -> different priority
# ================================================================


def test_same_risk_higher_business_criticality_yields_higher_priority():
    low = calculate_migration_priority(
        risk_score=60,
        blast_radius_score=40,
        complexity_score=30,
        business_criticality="LOW",
    )

    critical = calculate_migration_priority(
        risk_score=60,
        blast_radius_score=40,
        complexity_score=30,
        business_criticality="CRITICAL",
    )

    assert critical["priority_score"] > low["priority_score"]

    # Risk/blast/complexity inputs were identical -- only the
    # business-criticality contribution should differ.
    low_breakdown = low["score_breakdown"]
    critical_breakdown = critical["score_breakdown"]

    assert low_breakdown["quantum_risk"]["raw_score"] == critical_breakdown["quantum_risk"]["raw_score"]
    assert low_breakdown["business_criticality"]["raw_score"] == 0
    assert critical_breakdown["business_criticality"]["raw_score"] == 100


# ================================================================
# B. Same risk, different data lifetime -> different Mosca urgency
# ================================================================


def test_longer_data_lifetime_yields_higher_mosca_urgency_when_applicable():
    short_lifetime = calculate_mosca_risk(
        RiskContext(data_lifetime_years=1, migration_time_years=1, quantum_threat_horizon_years=10)
    )

    long_lifetime = calculate_mosca_risk(
        RiskContext(data_lifetime_years=20, migration_time_years=1, quantum_threat_horizon_years=10)
    )

    urgency_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

    assert urgency_rank[long_lifetime["migration_urgency"]] > urgency_rank[short_lifetime["migration_urgency"]]

    priority_short = calculate_migration_priority(
        risk_score=60, blast_radius_score=40, complexity_score=30,
        mosca_urgency=short_lifetime["migration_urgency"],
    )

    priority_long = calculate_migration_priority(
        risk_score=60, blast_radius_score=40, complexity_score=30,
        mosca_urgency=long_lifetime["migration_urgency"],
    )

    assert priority_long["priority_score"] > priority_short["priority_score"]


# ================================================================
# C. UNKNOWN business criticality is never fabricated
# ================================================================


def test_unconfigured_business_criticality_is_none_not_fabricated():
    def check():
        business_context.reload_config()
        assert business_context.get_business_criticality("any-bom-ref-at-all") is None

    _use_config({}, check)


def test_invalid_business_criticality_value_is_treated_as_unknown():
    def check():
        assert business_context.get_business_criticality("ref-1") is None

    _use_config(
        {"findings": {"ref-1": {"business_criticality": "SUPER-DUPER-IMPORTANT"}}},
        check,
    )


def test_unknown_business_criticality_excluded_from_priority_not_scored_as_zero():
    with_unknown = calculate_migration_priority(
        risk_score=60, blast_radius_score=40, complexity_score=30,
        business_criticality=None,
    )

    with_low = calculate_migration_priority(
        risk_score=60, blast_radius_score=40, complexity_score=30,
        business_criticality="LOW",
    )

    assert with_unknown["score_breakdown"]["business_criticality"]["known"] is False
    assert "business_criticality" in with_unknown["unknown_factors"]

    # Treating LOW (scored as 0) is NOT the same as excluding the
    # factor entirely -- LOW should pull the score down relative to
    # simply not counting it (weights of the other, higher-scoring
    # factors get diluted by a real zero, vs. renormalized away).
    assert with_low["priority_score"] <= with_unknown["priority_score"]


# ================================================================
# D. UNKNOWN data lifetime is never fabricated
# ================================================================


def test_unconfigured_data_lifetime_yields_no_mosca_urgency():
    def check():
        result = business_context.calculate_mosca_urgency("some-bom-ref", migration_time_years=2)
        assert result is None

    _use_config({}, check)


def test_configured_data_lifetime_yields_real_mosca_urgency():
    def check():
        result = business_context.calculate_mosca_urgency("ref-1", migration_time_years=2)
        assert result is not None
        assert result["migration_urgency"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert result["data_lifetime_years"] == 12.0

    _use_config({"findings": {"ref-1": {"data_lifetime_years": 12}}}, check)


# ================================================================
# E. Risk and priority remain separate concepts
# ================================================================


def test_risk_score_input_is_never_mutated_by_priority_factors():
    # The exact risk_score passed in must appear verbatim in the
    # breakdown regardless of which other factors are known --
    # priority blends risk into its own weighted score, it never
    # rewrites what "risk" itself means.
    baseline = calculate_migration_priority(risk_score=77.75, blast_radius_score=50, complexity_score=20)
    enriched = calculate_migration_priority(
        risk_score=77.75, blast_radius_score=50, complexity_score=20,
        business_criticality="CRITICAL", mosca_urgency="CRITICAL",
    )

    assert baseline["score_breakdown"]["quantum_risk"]["raw_score"] == 77.75
    assert enriched["score_breakdown"]["quantum_risk"]["raw_score"] == 77.75


# ================================================================
# F. Backward compatibility: unknown factors reproduce the original
#    three-factor formula exactly (see services/migration_priority.py
#    BASE_WEIGHTS comment for why this is a designed property, not a
#    coincidence).
# ================================================================


def test_no_business_context_reproduces_original_three_factor_formula():
    result = calculate_migration_priority(
        risk_score=65.75, blast_radius_score=79.86, complexity_score=78
    )

    assert result["priority_score"] == 73.75


# ================================================================
# G. Priority ordering changes appropriately when urgency factors
#    change (end-to-end through the config mechanism).
# ================================================================


def test_priority_ordering_shifts_only_for_the_configured_finding():
    def check():
        business_context.reload_config()

        unconfigured = calculate_migration_priority(
            risk_score=65.75, blast_radius_score=19.86, complexity_score=16,
            business_criticality=business_context.get_business_criticality("no-config-ref"),
            mosca_urgency=(business_context.calculate_mosca_urgency("no-config-ref", 2) or {}).get("migration_urgency"),
        )

        mosca = business_context.calculate_mosca_urgency("configured-ref", 2)

        configured = calculate_migration_priority(
            risk_score=65.75, blast_radius_score=19.86, complexity_score=16,
            business_criticality=business_context.get_business_criticality("configured-ref"),
            mosca_urgency=mosca["migration_urgency"] if mosca else None,
        )

        assert configured["priority_score"] > unconfigured["priority_score"]

    _use_config(
        {"findings": {"configured-ref": {"business_criticality": "CRITICAL", "data_lifetime_years": 25}}},
        check,
    )


# ================================================================
# H. bom_ref identity: distinct findings never share configuration
#    just because they share a display name.
# ================================================================


def test_duplicate_algorithm_name_findings_keep_independent_business_context():
    def check():
        business_context.reload_config()

        # Two findings that would display with the identical
        # algorithm name ("RSA-2048") but have different bom_refs
        # must resolve independently -- lookups are keyed by bom_ref,
        # never by name.
        assert business_context.get_business_criticality("rsa-2048-instance-a") == "CRITICAL"
        assert business_context.get_business_criticality("rsa-2048-instance-b") is None

    _use_config(
        {"findings": {"rsa-2048-instance-a": {"business_criticality": "CRITICAL"}}},
        check,
    )


if __name__ == "__main__":
    test_same_risk_higher_business_criticality_yields_higher_priority()
    test_longer_data_lifetime_yields_higher_mosca_urgency_when_applicable()

    test_unconfigured_business_criticality_is_none_not_fabricated()
    test_invalid_business_criticality_value_is_treated_as_unknown()
    test_unknown_business_criticality_excluded_from_priority_not_scored_as_zero()

    test_unconfigured_data_lifetime_yields_no_mosca_urgency()
    test_configured_data_lifetime_yields_real_mosca_urgency()

    test_risk_score_input_is_never_mutated_by_priority_factors()

    test_no_business_context_reproduces_original_three_factor_formula()

    test_priority_ordering_shifts_only_for_the_configured_finding()

    test_duplicate_algorithm_name_findings_keep_independent_business_context()

    print("All business-context / migration-priority tests passed.")

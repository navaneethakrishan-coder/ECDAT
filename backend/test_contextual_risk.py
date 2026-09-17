from models.risk_factors import RiskContext
from services.contextual_risk import calculate_contextual_risk


def test_contextual_rsa():

    asset = {
        "name": "RSA-2048",

        "classification": {
            "category": "asymmetric",
            "quantum_status": "vulnerable"
        }
    }

    context = RiskContext(
        business_criticality="HIGH",
        data_lifetime_years=15,
        migration_time_years=4,
        exposure="INTERNET",
        quantum_threat_horizon_years=10
    )

    result = calculate_contextual_risk(
        asset,
        context
    )

    print("\n==============================")
    print("ECDAT CONTEXTUAL RISK")
    print("==============================")

    print(
        "Asset:",
        asset["name"]
    )

    print(
        "Final Score:",
        result["final_score"]
    )

    print(
        "Severity:",
        result["severity"]
    )

    print(
        "Mosca:",
        result["mosca_analysis"]
    )

    print(
        "Breakdown:",
        result["score_breakdown"]
    )

    assert result["final_score"] == 81.25

    assert result["severity"] == "CRITICAL"


def test_unknown_data_lifetime_is_excluded_not_defaulted_to_five():
    """
    The audit-reported bug: data_lifetime_years used to be silently
    fabricated as 5 for every finding. With it genuinely UNKNOWN
    (None), the Data Lifetime factor must be excluded from the
    weighted average -- not treated as 5, not treated as 0 -- and the
    remaining five factors' weights rescaled to compensate.
    """

    asset = {
        "name": "RSA-2048",
        "classification": {"category": "asymmetric", "quantum_status": "vulnerable"},
    }

    context_unknown = RiskContext(
        business_criticality="HIGH",
        data_lifetime_years=None,
        migration_time_years=4,
        exposure="INTERNET",
        quantum_threat_horizon_years=10,
    )

    context_five = RiskContext(
        business_criticality="HIGH",
        data_lifetime_years=5,
        migration_time_years=4,
        exposure="INTERNET",
        quantum_threat_horizon_years=10,
    )

    result_unknown = calculate_contextual_risk(asset, context_unknown)
    result_five = calculate_contextual_risk(asset, context_five)

    assert result_unknown["score_breakdown"]["data_lifetime"]["known"] is False
    assert "data_lifetime_years" not in result_unknown["score_breakdown"]["data_lifetime"]

    # The two results must NOT be equal -- if UNKNOWN silently
    # resolved to the same number as an explicit 5-year value, this
    # bug would still be present in a different disguise.
    assert result_unknown["final_score"] != result_five["final_score"]


def test_unknown_data_lifetime_skips_mosca_rather_than_guessing():
    """
    Mosca urgency cannot be honestly computed without a data
    lifetime -- with it UNKNOWN, calculate_contextual_risk() must not
    call calculate_mosca_risk() with a fabricated value.
    """

    asset = {
        "name": "Ed25519",
        "classification": {"category": "asymmetric", "quantum_status": "vulnerable"},
    }

    context = RiskContext(
        business_criticality="MEDIUM",
        data_lifetime_years=None,
        migration_time_years=2,
        exposure="INTERNAL",
        quantum_threat_horizon_years=10,
    )

    result = calculate_contextual_risk(asset, context)

    assert result["mosca_analysis"] is None
    assert result["context"]["data_lifetime_known"] is False
    assert result["context"]["data_lifetime_years"] is None


if __name__ == "__main__":

    test_contextual_rsa()
    test_unknown_data_lifetime_is_excluded_not_defaulted_to_five()
    test_unknown_data_lifetime_skips_mosca_rather_than_guessing()

    print(
        "\nContextual risk test passed."
    )
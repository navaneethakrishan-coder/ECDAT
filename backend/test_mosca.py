from models.risk_factors import RiskContext
from services.mosca_analysis import calculate_mosca_risk


def test_critical_migration():

    context = RiskContext(
        business_criticality="HIGH",
        data_lifetime_years=15,
        migration_time_years=4,
        exposure="INTERNET",
        quantum_threat_horizon_years=10
    )

    result = calculate_mosca_risk(context)

    print("\nMosca Analysis:")
    print(result)

    assert result["combined_time_years"] == 19
    assert result["migration_urgency"] == "CRITICAL"


def test_low_urgency():

    context = RiskContext(
        business_criticality="LOW",
        data_lifetime_years=2,
        migration_time_years=1,
        exposure="INTERNAL",
        quantum_threat_horizon_years=10
    )

    result = calculate_mosca_risk(context)

    print("\nLow-risk timeline:")
    print(result)

    assert result["combined_time_years"] == 3
    assert result["migration_urgency"] == "LOW"


if __name__ == "__main__":

    test_critical_migration()
    test_low_urgency()

    print("\nAll Mosca tests passed.")
    
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


if __name__ == "__main__":

    test_contextual_rsa()

    print(
        "\nContextual risk test passed."
    )
from services.migration_complexity import (
    calculate_migration_complexity
)


def test_migration_complexity():

    asset = {
        "name": "ECDH"
    }

    classification = {
        "category": "asymmetric",

        "purpose": [
            "key-agreement"
        ],

        "quantum_status":
            "vulnerable"
    }

    risk_assessment = {

        "context": {

            "business_criticality":
                "MEDIUM",

            "data_lifetime_years":
                5,

            "migration_time_years":
                2,

            "exposure":
                "INTERNAL"
        },

        "evidence_quality": {

            "evidence_count":
                2
        }
    }

    blast_radius = {

        "direct_dependents": {

            "count": 12
        },

        "transitive_dependents": {

            "count": 12
        }
    }

    result = calculate_migration_complexity(
        asset,
        classification,
        risk_assessment,
        blast_radius
    )

    print()
    print(
        "================================"
    )

    print(
        "MIGRATION COMPLEXITY TEST"
    )

    print(
        "================================"
    )

    print(
        "Asset:",
        asset["name"]
    )

    print(
        "Score:",
        result["score"]
    )

    print(
        "Level:",
        result["level"]
    )

    print(
        "Factors:",
        result["factors"]
    )

    print(
        "Explanation:",
        result["explanation"]
    )

    assert 0 <= result["score"] <= 100

    assert result["level"] in [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL"
    ]

    assert (
        result["context"]["direct_dependents"]
        == 12
    )

    assert (
        result["context"]["transitive_dependents"]
        == 12
    )

    print()
    print(
        "Migration complexity test passed."
    )


if __name__ == "__main__":
    test_migration_complexity()
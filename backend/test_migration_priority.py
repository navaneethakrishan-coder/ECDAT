from services.migration_priority import (
    calculate_migration_priority
)


def test_migration_priority():

    result = calculate_migration_priority(
        risk_score=65.75,
        blast_radius_score=79.86,
        complexity_score=78
    )

    print()
    print("================================")
    print("MIGRATION PRIORITY TEST")
    print("================================")

    print(
        "Priority Score:",
        result["priority_score"]
    )

    print(
        "Priority:",
        result["priority"]
    )

    print(
        "Breakdown:",
        result["score_breakdown"]
    )

    print(
        "Explanation:",
        result["explanation"]
    )

    assert 0 <= result[
        "priority_score"
    ] <= 100

    assert result[
        "priority"
    ] in [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL"
    ]

    assert round(
        result["priority_score"],
        2
    ) == 73.75

    print()
    print(
        "Migration priority test passed."
    )


if __name__ == "__main__":
    test_migration_priority()
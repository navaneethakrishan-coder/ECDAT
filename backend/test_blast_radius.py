from services.dependency_graph import build_dependency_graph
from services.blast_radius import calculate_blast_radius


def test_blast_radius():

    assets = [
        {
            "bom_ref": "A",
            "name": "EC",
            "occurrences": [
                {
                    "location": "test.java",
                    "line": 10
                }
            ]
        },
        {
            "bom_ref": "B",
            "name": "ECDH",
            "occurrences": []
        },
        {
            "bom_ref": "C",
            "name": "Component-C",
            "occurrences": []
        }
    ]

    dependencies = [
        {
            "ref": "B",
            "dependsOn": ["A"]
        },
        {
            "ref": "C",
            "dependsOn": ["B"]
        }
    ]

    graph = build_dependency_graph(
        assets,
        dependencies
    )

    risk = {
        "final_score": 65.75
    }

    result = calculate_blast_radius(
        assets[0],
        graph,
        risk
    )

    print()
    print("================================")
    print("BLAST RADIUS TEST")
    print("================================")

    print(
        "Asset:",
        result["asset"]
    )

    print(
        "Blast Radius Score:",
        result["blast_radius_score"]
    )

    print(
        "Severity:",
        result["severity"]
    )

    print(
        "Direct dependents:",
        result["direct_dependents"]["count"]
    )

    print(
        "Transitive dependents:",
        result["transitive_dependents"]["count"]
    )

    print(
        "Breakdown:",
        result["score_breakdown"]
    )

    assert result[
        "direct_dependents"
    ]["count"] == 1

    assert result[
        "transitive_dependents"
    ]["count"] == 2

    assert 0 <= result[
        "blast_radius_score"
    ] <= 100

    print()
    print(
        "Blast-radius test passed."
    )


if __name__ == "__main__":
    test_blast_radius()
from services.dependency_graph import (
    build_dependency_graph,
    get_direct_dependencies,
    get_direct_dependents,
    get_transitive_dependents
)


def test_dependency_graph():

    assets = [
        {
            "bom_ref": "A",
            "name": "ECDH"
        },
        {
            "bom_ref": "B",
            "name": "Component-B"
        },
        {
            "bom_ref": "C",
            "name": "Component-C"
        }
    ]

    dependencies = [
        {
            "ref": "A",
            "dependsOn": ["B"]
        },
        {
            "ref": "B",
            "dependsOn": ["C"]
        }
    ]

    graph = build_dependency_graph(
        assets,
        dependencies
    )

    assert get_direct_dependencies(
        graph,
        "A"
    ) == ["B"]

    assert get_direct_dependents(
        graph,
        "B"
    ) == ["A"]

    affected = get_transitive_dependents(
        graph,
        "C"
    )

    assert set(affected) == {"A", "B"}

    print()
    print("================================")
    print("DEPENDENCY GRAPH TEST")
    print("================================")

    print(
        "A depends on:",
        get_direct_dependencies(
            graph,
            "A"
        )
    )

    print(
        "B is depended on by:",
        get_direct_dependents(
            graph,
            "B"
        )
    )

    print(
        "C transitive dependents:",
        affected
    )

    print()
    print(
        "Dependency graph test passed."
    )


if __name__ == "__main__":
    test_dependency_graph()
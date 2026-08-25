def build_dependency_graph(assets, dependencies):
    """
    Build a bidirectional dependency graph from CBOM relationships.

    Returns:
        {
            "depends_on": {
                asset_ref: [dependency_refs]
            },
            "dependents": {
                asset_ref: [dependent_refs]
            }
        }
    """

    depends_on = {}
    dependents = {}

    # Initialize every known asset
    for asset in assets:

        ref = asset.get("bom_ref")

        if ref:
            depends_on.setdefault(ref, [])
            dependents.setdefault(ref, [])

    # Process CBOM dependency relationships
    for dependency in dependencies:

        ref = dependency.get("ref")

        dependency_refs = dependency.get(
            "dependsOn",
            []
        )

        if not ref:
            continue

        depends_on.setdefault(ref, [])
        dependents.setdefault(ref, [])

        for dependency_ref in dependency_refs:

            if dependency_ref not in depends_on[ref]:
                depends_on[ref].append(
                    dependency_ref
                )

            dependents.setdefault(
                dependency_ref,
                []
            )

            if ref not in dependents[dependency_ref]:
                dependents[dependency_ref].append(
                    ref
                )

    return {
        "depends_on": depends_on,
        "dependents": dependents
    }


def get_direct_dependencies(graph, asset_ref):
    """
    Return assets directly required by the given asset.
    """

    return graph["depends_on"].get(
        asset_ref,
        []
    )


def get_direct_dependents(graph, asset_ref):
    """
    Return assets that directly depend on the given asset.
    """

    return graph["dependents"].get(
        asset_ref,
        []
    )


def get_transitive_dependents(
    graph,
    asset_ref
):
    """
    Find all assets affected through the
    reverse dependency graph.
    """

    visited = set()

    queue = [
        asset_ref
    ]

    while queue:

        current = queue.pop(0)

        for dependent in graph[
            "dependents"
        ].get(
            current,
            []
        ):

            if dependent in visited:
                continue

            visited.add(
                dependent
            )

            queue.append(
                dependent
            )

    # Do not include the original asset
    visited.discard(
        asset_ref
    )

    return list(visited)
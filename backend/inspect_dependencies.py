import json
from pathlib import Path

from services.dependency_graph import (
    build_dependency_graph,
    get_direct_dependencies,
    get_direct_dependents,
    get_transitive_dependents
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-assets.json"
)


def main():

    # --------------------------------------------------------
    # Load normalized ECDAT data
    # --------------------------------------------------------

    with open(
        DATA_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    assets = data.get(
        "assets",
        []
    )

    dependencies = data.get(
        "dependencies",
        []
    )

    # --------------------------------------------------------
    # Build lookup table
    # --------------------------------------------------------

    asset_map = {
        asset.get("bom_ref"): asset
        for asset in assets
        if asset.get("bom_ref")
    }

    asset_refs = set(
        asset_map.keys()
    )

    # --------------------------------------------------------
    # Count dependency mappings
    # --------------------------------------------------------

    matched_relationships = 0
    unmatched_relationships = 0

    matched_refs = set()

    for dependency in dependencies:

        ref = dependency.get(
            "ref"
        )

        depends_on = dependency.get(
            "dependsOn",
            []
        )

        ref_matches = (
            ref in asset_refs
        )

        dependency_matches = any(
            dependency_ref in asset_refs
            for dependency_ref in depends_on
        )

        if ref_matches or dependency_matches:

            matched_relationships += 1

            if ref_matches:
                matched_refs.add(ref)

            for dependency_ref in depends_on:

                if dependency_ref in asset_refs:
                    matched_refs.add(
                        dependency_ref
                    )

        else:
            unmatched_relationships += 1

    # --------------------------------------------------------
    # Build graph
    # --------------------------------------------------------

    graph = build_dependency_graph(
        assets,
        dependencies
    )

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print()
    print("=" * 45)
    print("ECDAT DEPENDENCY MAPPING")
    print("=" * 45)

    print(
        f"Crypto assets: "
        f"{len(assets)}"
    )

    print(
        f"CBOM dependencies: "
        f"{len(dependencies)}"
    )

    print(
        f"Matched relationships: "
        f"{matched_relationships}"
    )

    print(
        f"Unmatched relationships: "
        f"{unmatched_relationships}"
    )

    print(
        f"Assets appearing in dependencies: "
        f"{len(matched_refs)}"
    )

    # --------------------------------------------------------
    # Show connected crypto assets
    # --------------------------------------------------------

    print()
    print("Connected crypto assets:")

    connected_count = 0

    for asset in assets:

        ref = asset.get(
            "bom_ref"
        )

        direct_dependencies = (
            get_direct_dependencies(
                graph,
                ref
            )
        )

        direct_dependents = (
            get_direct_dependents(
                graph,
                ref
            )
        )

        if (
            direct_dependencies
            or direct_dependents
        ):

            connected_count += 1

            print()
            print(
                f"{connected_count}. "
                f"{asset.get('name')}"
            )

            print(
                f"   Ref: {ref}"
            )

            print(
                f"   Depends on: "
                f"{len(direct_dependencies)}"
            )

            print(
                f"   Dependents: "
                f"{len(direct_dependents)}"
            )

    # --------------------------------------------------------
    # Find most connected assets
    # --------------------------------------------------------

    rankings = []

    for asset in assets:

        ref = asset.get(
            "bom_ref"
        )

        direct_dependencies = (
            get_direct_dependencies(
                graph,
                ref
            )
        )

        direct_dependents = (
            get_direct_dependents(
                graph,
                ref
            )
        )

        transitive = (
            get_transitive_dependents(
                graph,
                ref
            )
        )

        connection_score = (
            len(direct_dependencies)
            + len(direct_dependents)
            + len(transitive)
        )

        rankings.append({
            "name": asset.get(
                "name"
            ),

            "ref": ref,

            "direct_dependencies":
                len(direct_dependencies),

            "direct_dependents":
                len(direct_dependents),

            "transitive_dependents":
                len(transitive),

            "connection_score":
                connection_score
        })

    rankings.sort(
        key=lambda x: x[
            "connection_score"
        ],
        reverse=True
    )

    # --------------------------------------------------------
    # Top connected assets
    # --------------------------------------------------------

    print()
    print("=" * 45)
    print("MOST CONNECTED CRYPTO ASSETS")
    print("=" * 45)

    for index, item in enumerate(
        rankings[:10],
        start=1
    ):

        print(
            f"{index}. "
            f"{item['name']}"
        )

        print(
            f"   Direct dependencies: "
            f"{item['direct_dependencies']}"
        )

        print(
            f"   Direct dependents: "
            f"{item['direct_dependents']}"
        )

        print(
            f"   Transitive dependents: "
            f"{item['transitive_dependents']}"
        )

        print(
            f"   Connection score: "
            f"{item['connection_score']}"
        )


if __name__ == "__main__":
    main()
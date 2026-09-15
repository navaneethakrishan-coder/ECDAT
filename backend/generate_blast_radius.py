import json
from pathlib import Path

from services.dependency_graph import build_dependency_graph
from services.blast_radius import calculate_blast_radius
from services.blast_radius_explanation import (
    explain_blast_radius
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

ASSETS_PATH = DATA_DIR / "ecdat-assets.json"

RISK_PATH = DATA_DIR / "ecdat-explainable-risk.json"

OUTPUT_PATH = DATA_DIR / "ecdat-blast-radius.json"


# ============================================================
# JSON LOADER
# ============================================================

def load_json(path):
    """
    Load a JSON file from disk.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# BUILD RISK LOOKUP
# ============================================================

def build_risk_map(risk_assets):
    """
    Build a lookup table using the CBOM bom-ref.
    """

    risk_map = {}

    duplicate_refs = []

    for item in risk_assets:

        bom_ref = item.get("bom_ref")

        if not bom_ref:
            continue

        if bom_ref in risk_map:
            duplicate_refs.append(bom_ref)

        risk_map[bom_ref] = item.get(
            "risk_assessment",
            {}
        )

    return risk_map, duplicate_refs


# ============================================================
# VALIDATE RISK MAPPING
# ============================================================

def validate_risk_mapping(
    assets,
    risk_map
):
    """
    Verify that every normalized asset has
    a corresponding risk assessment.
    """

    mapped = []
    missing = []

    for asset in assets:

        bom_ref = asset.get("bom_ref")

        if bom_ref in risk_map:

            mapped.append(bom_ref)

        else:

            missing.append(bom_ref)

    return mapped, missing


# ============================================================
# GENERATE BLAST-RADIUS ANALYSIS
# ============================================================

def generate_blast_radius(
    assets,
    dependencies,
    risk_map
):
    """
    Calculate blast radius for every crypto asset.
    """

    # --------------------------------------------------------
    # Build dependency graph
    # --------------------------------------------------------

    graph = build_dependency_graph(
        assets,
        dependencies
    )

    results = []

    # --------------------------------------------------------
    # Calculate blast radius for each asset
    # --------------------------------------------------------

    for asset in assets:

        risk_assessment = risk_map.get(
            asset.get("bom_ref"),
            {}
        )

        result = calculate_blast_radius(
            asset,
            graph,
            risk_assessment
        )
        result["explanation"] = (
    explain_blast_radius(
        result
    )
)

        results.append(
            result
        )

    # --------------------------------------------------------
    # Sort highest blast radius first
    # --------------------------------------------------------

    results.sort(
        key=lambda item: item.get(
            "blast_radius_score",
            0
        ),
        reverse=True
    )

    return results


# ============================================================
# SAVE OUTPUT
# ============================================================

def save_output(
    results,
    dependencies,
    mapped_count,
    missing_count
):
    """
    Save the final blast-radius analysis.
    """

    output = {

        "project": "ECDAT",

        "source": "keycloak-cbom.json",

        "asset_count": len(
            results
        ),

        "dependency_count": len(
            dependencies
        ),

        "risk_mapping": {

            "total_assets": len(
                results
            ),

            "mapped_assets": mapped_count,

            "missing_assets": missing_count
        },

        "assets": results
    }

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2
        )


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(
    results,
    dependencies,
    mapped_count,
    missing_count
):
    """
    Display a human-readable summary.
    """

    severity_counts = {

        "CRITICAL": 0,

        "HIGH": 0,

        "MEDIUM": 0,

        "LOW": 0
    }

    for result in results:

        severity = result.get(
            "severity",
            "LOW"
        )

        if severity not in severity_counts:

            severity = "LOW"

        severity_counts[
            severity
        ] += 1

    # --------------------------------------------------------
    # Main summary
    # --------------------------------------------------------

    print()

    print(
        "=" * 45
    )

    print(
        "ECDAT MIGRATION BLAST-RADIUS SUMMARY"
    )

    print(
        "=" * 45
    )

    print(
        f"Total assets: {len(results)}"
    )

    print(
        f"Dependencies: {len(dependencies)}"
    )

    print()

    # --------------------------------------------------------
    # Risk mapping
    # --------------------------------------------------------

    print(
        "Risk Mapping:"
    )

    print(
        f"  Mapped assets: {mapped_count}"
    )

    print(
        f"  Missing assets: {missing_count}"
    )

    # --------------------------------------------------------
    # Severity
    # --------------------------------------------------------

    print()

    print(
        "Severity:"
    )

    for severity in [
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW"
    ]:

        print(
            f"  {severity}: "
            f"{severity_counts[severity]}"
        )

    # --------------------------------------------------------
    # Top assets
    # --------------------------------------------------------

    print()

    print(
        "Top Blast-Radius Assets:"
    )

    for index, result in enumerate(
        results[:10],
        start=1
    ):

        asset_name = result.get(
            "asset",
            "Unknown"
        )

        score = result.get(
            "blast_radius_score",
            0
        )

        severity = result.get(
            "severity",
            "UNKNOWN"
        )

        direct_dependents = result.get(
            "direct_dependents",
            {}
        ).get(
            "count",
            0
        )

        transitive_dependents = result.get(
            "transitive_dependents",
            {}
        ).get(
            "count",
            0
        )

        risk_score = result.get(
            "risk",
            {}
        ).get(
            "score",
            0
        )

        print()

        print(
            f"  {index}. "
            f"{asset_name} — "
            f"{score} "
            f"({severity})"
        )

        print(
            f"      Quantum Risk: "
            f"{risk_score}"
        )

        print(
            f"      Direct dependents: "
            f"{direct_dependents}"
        )

        print(
            f"      Transitive dependents: "
            f"{transitive_dependents}"
        )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print()

    print(
        f"Output: {OUTPUT_PATH}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Loading ECDAT data..."
    )

    # --------------------------------------------------------
    # Load normalized assets
    # --------------------------------------------------------

    data = load_json(
        ASSETS_PATH
    )

    assets = data.get(
        "assets",
        []
    )

    dependencies = data.get(
        "dependencies",
        []
    )

    # --------------------------------------------------------
    # Load explainable risk
    # --------------------------------------------------------

    risk_data = load_json(
        RISK_PATH
    )

    risk_assets = risk_data.get(
        "assets",
        []
    )

    print(
        f"Assets loaded: {len(assets)}"
    )

    print(
        f"Dependencies loaded: "
        f"{len(dependencies)}"
    )

    print(
        f"Risk records loaded: "
        f"{len(risk_assets)}"
    )

    # --------------------------------------------------------
    # Build risk lookup
    # --------------------------------------------------------

    risk_map, duplicate_refs = build_risk_map(
        risk_assets
    )

    # --------------------------------------------------------
    # Validate mapping
    # --------------------------------------------------------

    mapped, missing = validate_risk_mapping(
        assets,
        risk_map
    )

    print()

    print(
        "Risk mapping validation:"
    )

    print(
        f"  Total assets: "
        f"{len(assets)}"
    )

    print(
        f"  Successfully mapped: "
        f"{len(mapped)}"
    )

    print(
        f"  Missing risk records: "
        f"{len(missing)}"
    )

    if duplicate_refs:

        print()

        print(
            "WARNING: Duplicate CBOM bom-ref values detected:"
        )

        for bom_ref in duplicate_refs:

            print(
                f"  - {bom_ref}"
            )

    if missing:

        print()

        print(
            "Assets without risk assessments:"
        )

        for name in missing:

            print(
                f"  - {name}"
            )

    # --------------------------------------------------------
    # Generate blast radius
    # --------------------------------------------------------

    results = generate_blast_radius(
        assets,
        dependencies,
        risk_map
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_output(
        results,
        dependencies,
        len(mapped),
        len(missing)
    )

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print_summary(
        results,
        dependencies,
        len(mapped),
        len(missing)
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

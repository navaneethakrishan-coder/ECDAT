import json
from pathlib import Path

from services.migration_complexity import (
    calculate_migration_complexity
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

ASSETS_PATH = DATA_DIR / "ecdat-assets.json"

RISK_PATH = DATA_DIR / "ecdat-explainable-risk.json"

BLAST_PATH = DATA_DIR / "ecdat-blast-radius.json"

OUTPUT_PATH = (
    DATA_DIR
    / "ecdat-migration-complexity.json"
)


# ============================================================
# JSON LOADER
# ============================================================

def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Loading ECDAT data..."
    )

    # --------------------------------------------------------
    # Load files
    # --------------------------------------------------------

    asset_data = load_json(
        ASSETS_PATH
    )

    risk_data = load_json(
        RISK_PATH
    )

    blast_data = load_json(
        BLAST_PATH
    )

    assets = asset_data.get(
        "assets",
        []
    )

    risk_assets = risk_data.get(
        "assets",
        []
    )

    blast_assets = blast_data.get(
        "assets",
        []
    )

    print(
        f"Assets loaded: {len(assets)}"
    )

    print(
        f"Risk records loaded: "
        f"{len(risk_assets)}"
    )

    print(
        f"Blast-radius records loaded: "
        f"{len(blast_assets)}"
    )

    # --------------------------------------------------------
    # Build lookups
    # --------------------------------------------------------

    risk_map = {}

    for item in risk_assets:

        bom_ref = item.get("bom_ref")

        if bom_ref:
            risk_map[bom_ref] = item

    blast_map = {}

    for item in blast_assets:

        bom_ref = item.get("bom_ref") or item.get("asset_ref")

        if bom_ref:
            blast_map[bom_ref] = item

    # --------------------------------------------------------
    # Validate mappings
    # --------------------------------------------------------

    risk_mapped = 0
    blast_mapped = 0

    missing_risk = []
    missing_blast = []

    for asset in assets:

        name = asset.get("name")
        bom_ref = asset.get("bom_ref")

        if bom_ref in risk_map:

            risk_mapped += 1

        else:

            missing_risk.append(
                name
            )

        if bom_ref in blast_map:

            blast_mapped += 1

        else:

            missing_blast.append(
                name
            )

    print()
    print(
        "Mapping validation:"
    )

    print(
        f"  Risk mapped: "
        f"{risk_mapped}/{len(assets)}"
    )

    print(
        f"  Blast mapped: "
        f"{blast_mapped}/{len(assets)}"
    )

    # --------------------------------------------------------
    # Calculate migration complexity
    # --------------------------------------------------------

    results = []

    for asset in assets:

        name = asset.get(
            "name"
        )

        risk_record = risk_map.get(
            bom_ref,
            {}
        )

        blast_record = blast_map.get(
            bom_ref,
            {}
        )

        classification = risk_record.get(
            "classification",
            {}
        )

        risk_assessment = risk_record.get(
            "risk_assessment",
            {}
        )

        result = (
            calculate_migration_complexity(
                asset,
                classification,
                risk_assessment,
                blast_record
            )
        )

        # Add asset metadata

        result["asset"] = name

        result["bom_ref"] = asset.get(
            "bom_ref"
        )

        results.append(
            result
        )

    # --------------------------------------------------------
    # Sort by complexity
    # --------------------------------------------------------

    results.sort(
        key=lambda item: item.get(
            "score",
            0
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output = {

        "project": "ECDAT",

        "source": "keycloak-cbom.json",

        "asset_count": len(
            results
        ),

        "risk_mapping": {

            "mapped": risk_mapped,

            "missing": len(
                missing_risk
            )
        },

        "blast_radius_mapping": {

            "mapped": blast_mapped,

            "missing": len(
                missing_blast
            )
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

    # --------------------------------------------------------
    # Complexity distribution
    # --------------------------------------------------------

    levels = {

        "CRITICAL": 0,

        "HIGH": 0,

        "MEDIUM": 0,

        "LOW": 0
    }

    for result in results:

        level = result.get(
            "level",
            "LOW"
        )

        if level not in levels:

            level = "LOW"

        levels[level] += 1

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print(
        "=" * 45
    )

    print(
        "ECDAT MIGRATION COMPLEXITY SUMMARY"
    )

    print(
        "=" * 45
    )

    print(
        f"Total assets: "
        f"{len(results)}"
    )

    print()
    print(
        "Complexity:"
    )

    for level in [
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW"
    ]:

        print(
            f"  {level}: "
            f"{levels[level]}"
        )

    # --------------------------------------------------------
    # Top complexity assets
    # --------------------------------------------------------

    print()
    print(
        "Top Migration Complexity Assets:"
    )

    for index, result in enumerate(
        results[:10],
        start=1
    ):

        print()

        print(
            f"  {index}. "
            f"{result['asset']} — "
            f"{result['score']} "
            f"({result['level']})"
        )

        print(
            f"      Crypto: "
            f"{result['factors']['cryptographic_complexity']}"
        )

        print(
            f"      Dependency: "
            f"{result['factors']['dependency_complexity']}"
        )

        print(
            f"      Migration time: "
            f"{result['factors']['migration_time_complexity']}"
        )

        print(
            f"      Evidence: "
            f"{result['factors']['evidence_surface']}"
        )

        print(
            f"      Data lifetime: "
            f"{result['factors']['data_lifetime_pressure']}"
        )

    print()
    print(
        f"Output: {OUTPUT_PATH}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

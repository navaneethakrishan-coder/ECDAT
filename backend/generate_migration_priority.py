import json
from pathlib import Path

from services.migration_priority import (
    calculate_migration_priority
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RISK_PATH = DATA_DIR / "ecdat-explainable-risk.json"

BLAST_PATH = DATA_DIR / "ecdat-blast-radius.json"

COMPLEXITY_PATH = (
    DATA_DIR
    / "ecdat-migration-complexity.json"
)

OUTPUT_PATH = (
    DATA_DIR
    / "ecdat-migration-priority.json"
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
        "Loading ECDAT migration data..."
    )

    risk_data = load_json(
        RISK_PATH
    )

    blast_data = load_json(
        BLAST_PATH
    )

    complexity_data = load_json(
        COMPLEXITY_PATH
    )

    risk_assets = risk_data.get(
        "assets",
        []
    )

    blast_assets = blast_data.get(
        "assets",
        []
    )

    complexity_assets = (
        complexity_data.get(
            "assets",
            []
        )
    )

    print(
        f"Risk records: "
        f"{len(risk_assets)}"
    )

    print(
        f"Blast-radius records: "
        f"{len(blast_assets)}"
    )

    print(
        f"Complexity records: "
        f"{len(complexity_assets)}"
    )

    # ========================================================
    # BUILD LOOKUPS
    # ========================================================

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


    complexity_map = {}

    for item in complexity_assets:

        bom_ref = item.get("bom_ref")

        if bom_ref:
            complexity_map[bom_ref] = item


    # ========================================================
    # FIND ALL ASSETS
    # ========================================================

    finding_ids = set()

    finding_ids.update(
        risk_map.keys()
    )

    finding_ids.update(
        blast_map.keys()
    )

    finding_ids.update(
        complexity_map.keys()
    )

    print()
    print(
        f"Unique CBOM findings found: "
        f"{len(finding_ids)}"
    )


    # ========================================================
    # VALIDATE MAPPINGS
    # ========================================================

    missing_risk = []

    missing_blast = []

    missing_complexity = []

    for name in sorted(
        finding_ids
    ):

        if name not in risk_map:

            missing_risk.append(
                name
            )

        if name not in blast_map:

            missing_blast.append(
                name
            )

        if name not in complexity_map:

            missing_complexity.append(
                name
            )


    print()
    print(
        "Mapping validation:"
    )

    print(
        f"  Risk mapped: "
        f"{len(finding_ids) - len(missing_risk)}"
        f"/{len(finding_ids)}"
    )

    print(
        f"  Blast mapped: "
        f"{len(finding_ids) - len(missing_blast)}"
        f"/{len(finding_ids)}"
    )

    print(
        f"  Complexity mapped: "
        f"{len(finding_ids) - len(missing_complexity)}"
        f"/{len(finding_ids)}"
    )


    # ========================================================
    # GENERATE PRIORITY
    # ========================================================

    results = []

    for bom_ref in finding_ids:

        risk_record = risk_map.get(
            bom_ref,
            {}
        )

        blast_record = blast_map.get(
            bom_ref,
            {}
        )

        complexity_record = (
            complexity_map.get(
                bom_ref,
                {}
            )
        )

        # --------------------------------------------
        # Extract scores
        # --------------------------------------------

        risk_score = (
            risk_record
            .get(
                "risk_assessment",
                {}
            )
            .get(
                "final_score",
                0
            )
        )

        blast_score = (
            blast_record
            .get(
                "blast_radius_score",
                0
            )
        )

        complexity_score = (
            complexity_record
            .get(
                "score",
                0
            )
        )

        # --------------------------------------------
        # Calculate priority
        # --------------------------------------------

        priority = calculate_migration_priority(
            risk_score,
            blast_score,
            complexity_score
        )

        # --------------------------------------------
        # Build result
        # --------------------------------------------

        result = {

            "asset": risk_record.get("name") or complexity_record.get("asset") or blast_record.get("asset") or "Unknown",
            "bom_ref": bom_ref,

            "quantum_risk": {
                "score": risk_score,

                "severity":
                    risk_record
                    .get(
                        "risk_assessment",
                        {}
                    )
                    .get(
                        "severity",
                        "UNKNOWN"
                    )
            },

            "blast_radius": {
                "score": blast_score,

                "severity":
                    blast_record
                    .get(
                        "severity",
                        "UNKNOWN"
                    )
            },

            "migration_complexity": {
                "score": complexity_score,

                "level":
                    complexity_record
                    .get(
                        "level",
                        "UNKNOWN"
                    )
            },

            "migration_priority": priority
        }

        results.append(
            result
        )


    # ========================================================
    # SORT
    # ========================================================

    results.sort(
        key=lambda item:
            item[
                "migration_priority"
            ][
                "priority_score"
            ],

        reverse=True
    )


    # ========================================================
    # DISTRIBUTION
    # ========================================================

    priority_counts = {

        "CRITICAL": 0,

        "HIGH": 0,

        "MEDIUM": 0,

        "LOW": 0
    }

    for result in results:

        priority = (
            result[
                "migration_priority"
            ][
                "priority"
            ]
        )

        if priority not in priority_counts:

            priority = "LOW"

        priority_counts[
            priority
        ] += 1


    # ========================================================
    # SAVE
    # ========================================================

    output = {

        "project": "ECDAT",

        "asset_count":
            len(results),

        "weights": {

            "quantum_risk": 0.40,

            "blast_radius": 0.35,

            "migration_complexity": 0.25
        },

        "priority_distribution":
            priority_counts,

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


    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print(
        "=" * 45
    )

    print(
        "ECDAT MIGRATION PRIORITY SUMMARY"
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
        "Priority distribution:"
    )

    for priority in [
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW"
    ]:

        print(
            f"  {priority}: "
            f"{priority_counts[priority]}"
        )


    print()
    print(
        "Top Migration Priorities:"
    )


    for index, result in enumerate(
        results[:10],
        start=1
    ):

        priority_data = (
            result[
                "migration_priority"
            ]
        )

        print()

        print(
            f"  {index}. "
            f"{result['asset']} — "
            f"{priority_data['priority_score']} "
            f"({priority_data['priority']})"
        )

        print(
            f"      Quantum Risk: "
            f"{result['quantum_risk']['score']}"
        )

        print(
            f"      Blast Radius: "
            f"{result['blast_radius']['score']}"
        )

        print(
            f"      Complexity: "
            f"{result['migration_complexity']['score']}"
        )


    print()
    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

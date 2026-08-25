import json
from pathlib import Path

from services.source_crypto_mapper import map_assets_to_source
from services.source_impact_analyzer import analyze_all_source_usage
from services.migration_action_generator import (
    generate_all_migration_actions,
    summarize_migration_actions,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

RISK_FILE = DATA_DIR / "ecdat-explainable-risk.json"
MIGRATION_FILE = DATA_DIR / "ecdat-pqc-migration-plan.json"

OUTPUT_FILE = DATA_DIR / "ecdat-migration-actions.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    print("Loading ECDAT migration-action data...")

    risk_data = load_json(RISK_FILE)
    migration_data = load_json(MIGRATION_FILE)

    assets = risk_data.get("assets", [])
    migrations = migration_data.get("assets", [])

    print(f"Assets loaded: {len(assets)}")
    print(f"Migration records: {len(migrations)}")

    print()
    print("=============================================")
    print("ECDAT MIGRATION ACTION GENERATION")
    print("=============================================")

    print()
    print("Running source-to-crypto mapping...")

    mappings = map_assets_to_source(assets)

    print(f"Source mappings: {len(mappings)}")

    print()
    print("Running source impact analysis...")

    impacts = analyze_all_source_usage(mappings)

    print(f"Impact records: {len(impacts)}")

    print()
    print("Generating migration actions...")

    actions = generate_all_migration_actions(
        mappings,
        impacts,
        migrations,
    )

    print(f"Migration-action records: {len(actions)}")

    summary = summarize_migration_actions(actions)

    output = {
        "metadata": {
            "project": "ECDAT",
            "stage": "9.4",
            "component": "migration-action-generation",
            "source_asset_count": len(assets),
            "migration_record_count": len(migrations),
        },
        "summary": summary,
        "assets": actions,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
        )

    print()
    print("=============================================")
    print("MIGRATION ACTION GENERATION COMPLETE")
    print("=============================================")

    print()
    print(f"Total assets: {summary['total_assets']}")
    print(
        f"Total migration actions: "
        f"{summary['total_migration_actions']}"
    )
    print(
        f"Assets with PQC candidates: "
        f"{summary['assets_with_pqc_candidates']}"
    )

    print()
    print("Migration-type distribution:")

    for migration_type, count in (
        summary["migration_type_distribution"].items()
    ):
        print(
            f"  {migration_type}: {count}"
        )

    print()
    print("Sample migration actions:")

    for item in actions[:10]:
        print()
        print(
            f"{item['asset']} "
            f"→ {item['pqc_candidate'] or 'None'}"
        )

        print(
            f"  Type: "
            f"{item['migration_type']}"
        )

        print(
            f"  Impact: "
            f"{item['impact_level']}"
        )

        print(
            f"  Actions: "
            f"{item['action_count']}"
        )

        if item["actions"]:
            print(
                f"  First action: "
                f"{item['actions'][0]['action']}"
            )

    print()
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
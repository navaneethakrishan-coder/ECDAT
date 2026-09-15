import json
from pathlib import Path

from services.pqc_mapper import map_asset_to_pqc


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

INPUT_FILE = DATA_DIR / "ecdat-explainable-risk.json"
OUTPUT_FILE = DATA_DIR / "ecdat-pqc-migration.json"


def load_assets():
    print("Loading ECDAT classified risk data...")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assets = data.get("assets", [])

    if not isinstance(assets, list):
        raise ValueError("Invalid ECDAT data: 'assets' must be a list.")

    print(f"Assets loaded: {len(assets)}")

    return assets


def generate_migration_analysis(assets):
    results = []

    for asset in assets:
        classification = asset.get("classification", {})

        # Build the input expected by the PQC mapper.
        mapper_asset = {
            "name": asset.get("name"),
            "bom_ref": asset.get("bom_ref"),
            "classification": classification,
        }

        mapping = map_asset_to_pqc(mapper_asset)

        result = {
            "bom_ref": asset.get("bom_ref"),
            "id": asset.get("id"),
            "name": asset.get("name"),
            "asset_type": asset.get("asset_type"),
            "primitive": asset.get("primitive"),
            "classification": classification,
            "risk_assessment": asset.get("risk_assessment"),
            "evidence": asset.get("evidence"),
            "pqc_migration": mapping,
        }

        results.append(result)

    return results


def build_summary(results):
    total = len(results)

    pqc_applicable = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("pqc_applicable") is True
    )

    direct_replacement = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("migration_type")
        == "direct-replacement"
    )

    pqc_candidates = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("migration_type")
        == "pqc-candidate"
    )

    architectural = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("migration_type")
        == "architectural-migration"
    )

    no_direct_replacement = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("migration_type")
        == "no-direct-pqc-replacement"
    )

    not_applicable = sum(
        1
        for asset in results
        if asset["pqc_migration"].get("migration_type")
        == "not-applicable"
    )

    return {
        "total_assets": total,
        "pqc_applicable_assets": pqc_applicable,
        "direct_replacement": direct_replacement,
        "pqc_candidates": pqc_candidates,
        "architectural_migrations": architectural,
        "no_direct_pqc_replacement": no_direct_replacement,
        "not_applicable": not_applicable,
    }


def save_results(results, summary):
    output = {
        "project": "ECDAT",
        "stage": "8.3",
        "description": (
            "PQC migration candidate analysis generated from "
            "ECDAT classified cryptographic assets."
        ),
        "summary": summary,
        "assets": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(f"Output: {OUTPUT_FILE}")


def print_summary(results, summary):
    print()
    print("=============================================")
    print("ECDAT PQC MIGRATION ANALYSIS")
    print("=============================================")

    print(f"Total assets: {summary['total_assets']}")
    print(
        f"PQC-applicable assets: "
        f"{summary['pqc_applicable_assets']}"
    )

    print()
    print("Migration categories:")
    print(
        f"  Direct replacement: "
        f"{summary['direct_replacement']}"
    )
    print(
        f"  PQC candidates: "
        f"{summary['pqc_candidates']}"
    )
    print(
        f"  Architectural migration: "
        f"{summary['architectural_migrations']}"
    )
    print(
        f"  No direct PQC replacement: "
        f"{summary['no_direct_pqc_replacement']}"
    )
    print(
        f"  Not applicable: "
        f"{summary['not_applicable']}"
    )

    print()
    print("Top PQC migration candidates:")

    count = 0

    for asset in results:
        mapping = asset["pqc_migration"]

        if not mapping.get("pqc_applicable"):
            continue

        candidates = mapping.get("candidates", [])

        if not candidates:
            continue

        count += 1

        print()
        print(
            f"{count}. {asset['name']}"
        )
        print(
            f"   Category: "
            f"{mapping.get('category')}"
        )
        print(
            f"   Purpose: "
            f"{', '.join(mapping.get('purpose', []))}"
        )
        print(
            f"   Migration: "
            f"{mapping.get('migration_type')}"
        )
        print(
            f"   Confidence: "
            f"{mapping.get('confidence')}"
        )

        print("   Candidates:")

        for candidate in candidates:
            print(
                f"      - {candidate['name']} "
                f"({candidate['compatibility']})"
            )

        if count >= 10:
            break


def main():
    assets = load_assets()

    results = generate_migration_analysis(assets)

    summary = build_summary(results)

    print_summary(results, summary)

    save_results(results, summary)


if __name__ == "__main__":
    main()

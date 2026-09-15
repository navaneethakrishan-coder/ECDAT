"""
Risk-scoring consistency check.

Verifies, for every asset, that every ECDAT output file which claims
to carry a "risk" figure actually agrees with the single authoritative
computation in ecdat-explainable-risk.json (produced by
explain_cbom.py). This is the automated counterpart to the manual
audit described in docs/ARCHITECTURE.md ("Risk-scoring unification").

Checks performed, per asset:
    1. ecdat-risk-assessed-assets.json's risk_assessment
       == ecdat-explainable-risk.json's risk_assessment.base_risk
       (score AND severity)
    2. ecdat-migration-report.json's current_risk.{score,severity}
       == ecdat-explainable-risk.json's risk_assessment.{final_score,severity}

Run manually:
    python check_risk_consistency.py

Also run automatically as the last stage of run_pipeline.py, where a
mismatch fails the pipeline (exit code 1) instead of shipping a
silently-inconsistent dataset.
"""

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

EXPLAINABLE_RISK_FILE = DATA_DIR / "ecdat-explainable-risk.json"
RISK_ASSESSED_FILE = DATA_DIR / "ecdat-risk-assessed-assets.json"
MIGRATION_REPORT_FILE = DATA_DIR / "ecdat-migration-report.json"


def load_json(path):
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def index_by_name(records, name_keys=("name", "asset")):
    indexed = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        name = record.get("bom_ref") or record.get("asset_ref")

        if not name:
            for key in name_keys:
                name = record.get(key)
                if name:
                    break

        if name:
            indexed[name] = record

    return indexed


def main():

    explainable = load_json(EXPLAINABLE_RISK_FILE)
    risk_assessed = load_json(RISK_ASSESSED_FILE)
    migration_report = load_json(MIGRATION_REPORT_FILE)

    if explainable is None:
        print(f"SKIP: {EXPLAINABLE_RISK_FILE.name} not found — nothing to check against.")
        return 0

    explainable_by_name = index_by_name(explainable.get("assets", []))

    mismatches = []
    checked = 0

    # ------------------------------------------------------------
    # Check 1: ecdat-risk-assessed-assets.json vs authoritative
    # ------------------------------------------------------------

    if risk_assessed is not None:

        for asset in risk_assessed.get("assets", []):

            name = asset.get("bom_ref") or asset.get("asset_ref")
            authoritative = explainable_by_name.get(name)

            if authoritative is None:
                mismatches.append(
                    f"[risk-assessed] '{name}': no matching entry in "
                    f"{EXPLAINABLE_RISK_FILE.name}"
                )
                continue

            base_risk = authoritative.get("risk_assessment", {}).get("base_risk", {})
            actual = asset.get("risk_assessment", {})

            checked += 1

            if (
                actual.get("score") != base_risk.get("score")
                or actual.get("severity") != base_risk.get("severity")
            ):
                mismatches.append(
                    f"[risk-assessed] '{name}': "
                    f"score={actual.get('score')}/severity={actual.get('severity')} "
                    f"!= authoritative "
                    f"score={base_risk.get('score')}/severity={base_risk.get('severity')}"
                )

    else:
        print(f"SKIP: {RISK_ASSESSED_FILE.name} not found — check 1 skipped.")

    # ------------------------------------------------------------
    # Check 2: ecdat-migration-report.json vs authoritative
    # ------------------------------------------------------------

    if migration_report is not None:

        for asset in migration_report.get("assets", []):

            name = asset.get("bom_ref") or asset.get("asset_ref")
            authoritative = explainable_by_name.get(name)

            if authoritative is None:
                mismatches.append(
                    f"[migration-report] '{name}': no matching entry in "
                    f"{EXPLAINABLE_RISK_FILE.name}"
                )
                continue

            risk_assessment = authoritative.get("risk_assessment", {})
            current_risk = asset.get("current_risk", {})

            checked += 1

            if (
                current_risk.get("score") != risk_assessment.get("final_score")
                or current_risk.get("severity") != risk_assessment.get("severity")
            ):
                mismatches.append(
                    f"[migration-report] '{name}': "
                    f"score={current_risk.get('score')}/severity={current_risk.get('severity')} "
                    f"!= authoritative "
                    f"score={risk_assessment.get('final_score')}/severity={risk_assessment.get('severity')}"
                )

    else:
        print(f"SKIP: {MIGRATION_REPORT_FILE.name} not found — check 2 skipped.")

    # ------------------------------------------------------------
    # Report
    # ------------------------------------------------------------

    print("=" * 70)
    print("ECDAT RISK-SCORING CONSISTENCY CHECK")
    print("=" * 70)
    print(f"Checked {checked} risk figures against the authoritative dataset.")

    if mismatches:
        print(f"\nFOUND {len(mismatches)} MISMATCH(ES):\n")
        for line in mismatches:
            print(f"  - {line}")
        print()
        return 1

    print("All risk figures are consistent with the authoritative source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

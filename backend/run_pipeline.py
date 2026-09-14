import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# Risk-scoring unification (see docs/ARCHITECTURE.md): explain_cbom.py
# is the single authoritative risk computation. Every downstream stage
# (blast radius, complexity, priority, PQC mapping, migration report)
# already read its output (ecdat-explainable-risk.json) directly.
# "Basic Risk Assessment" now re-projects that same authoritative
# figure into its legacy output shape instead of recomputing
# independently, so it must run AFTER Explainable Risk, not before.
# "Contextual Risk Assessment" was a byte-for-byte duplicate of
# Explainable Risk's own computation with no remaining reader
# anywhere in the codebase, so it has been retired from the active
# pipeline (the script itself is kept, deprecated, for manual use).
PIPELINE = [
    ("CBOM Parser", "cbom_parser.py"),
    ("Classification", "classify_cbom.py"),
    ("Explainable Risk", "explain_cbom.py"),
    ("Basic Risk Assessment (legacy view)", "score_cbom.py"),
    ("Blast Radius", "generate_blast_radius.py"),
    ("Migration Complexity", "generate_migration_complexity.py"),
    ("Migration Priority", "generate_migration_priority.py"),
    ("PQC Migration", "generate_pqc_migration.py"),
    ("PQC Ranking", "generate_pqc_ranking.py"),
    ("PQC Migration Plan", "generate_pqc_migration_plan.py"),
    ("Migration Actions", "generate_migration_actions.py"),
    ("Migration Report", "generate_migration_report.py"),
    ("Risk Consistency Check", "check_risk_consistency.py"),
]


def run_stage(name, script):
    print("\n" + "=" * 70)
    print(f"RUNNING: {name}")
    print(f"SCRIPT : {script}")
    print("=" * 70)

    script_path = BASE_DIR / script

    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}")
        return False

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR)
    )

    if result.returncode != 0:
        print(f"\nERROR: {name} failed.")
        print(f"Exit code: {result.returncode}")
        return False

    print(f"\nSUCCESS: {name}")
    return True


def main():
    print("=" * 70)
    print("ECDAT COMPLETE ANALYSIS PIPELINE")
    print("=" * 70)
    print(f"Backend: {BASE_DIR}")
    print(f"Python : {sys.executable}")

    for name, script in PIPELINE:
        if not run_stage(name, script):
            print("\n" + "=" * 70)
            print("PIPELINE STOPPED")
            print("=" * 70)
            sys.exit(1)

    print("\n" + "=" * 70)
    print("ECDAT PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)

    data_dir = BASE_DIR.parent / "data"

    print("\nGenerated ECDAT files:")
    for file in sorted(data_dir.glob("ecdat-*.json")):
        print(f"  {file.name:40} {file.stat().st_size:,} bytes")

    print("\nAll analysis stages completed successfully.")


if __name__ == "__main__":
    main()
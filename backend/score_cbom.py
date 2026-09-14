"""
Legacy "basic risk" view — sourced from the authoritative pipeline.

This stage used to call services.risk_engine.calculate_base_risk()
independently, computing the same quantum-only 0-100 score a second
time from scratch. explain_cbom.py already computes that exact value
(as risk_assessment.base_risk, an internal input to its own weighted
contextual score) as part of the single authoritative risk
computation that also feeds blast radius, complexity, priority, PQC
mapping, and the final migration report.

This script no longer performs its own risk calculation. It now
reads the authoritative dataset (ecdat-explainable-risk.json) and
re-projects each asset's base_risk into the historical
ecdat-risk-assessed-assets.json shape, so /api/risk and
/api/risk/{name} (backend/main.py) keep exactly the same response
format while being provably derived from the same computation as
everything else, instead of a numerically-coincidental duplicate.
See docs/ARCHITECTURE.md ("Risk-scoring unification") for the full
history.

Consequently, explain_cbom.py must run before this script in
run_pipeline.py.
"""

import json
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-classified-assets.json"
)

RISK_SOURCE_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-explainable-risk.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-risk-assessed-assets.json"
)


def load_quantum_risk_by_asset():
    """
    Load the authoritative quantum-risk ("base risk") view, keyed by
    asset name, from the same dataset every other pipeline stage
    (blast radius, complexity, priority, PQC mapping, migration
    report) treats as the single source of truth for risk.
    """

    if not RISK_SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Authoritative risk file not found: {RISK_SOURCE_PATH}. "
            "explain_cbom.py must run before score_cbom.py."
        )

    with open(
        RISK_SOURCE_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    by_name = {}

    for asset in data.get("assets", []):

        name = asset.get("name")

        base_risk = asset.get(
            "risk_assessment",
            {}
        ).get(
            "base_risk",
            {}
        )

        if name and base_risk:
            by_name[name] = base_risk

    return by_name


def main():

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    with open(
        INPUT_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    assets = data.get(
        "assets",
        []
    )

    quantum_risk_by_name = load_quantum_risk_by_asset()

    risk_assessed_assets = []

    for asset in assets:

        name = asset.get("name")

        risk = quantum_risk_by_name.get(name)

        if risk is None:
            # Same input file feeds both this stage and
            # explain_cbom.py, so this should not normally happen.
            # Fail loudly rather than silently falling back to an
            # independently (and possibly differently) computed
            # score, which is exactly the divergence this stage was
            # rewritten to prevent.
            raise ValueError(
                f"No authoritative quantum-risk entry found for "
                f"asset '{name}' in {RISK_SOURCE_PATH.name}. Was "
                f"explain_cbom.py run on the same CBOM?"
            )

        updated_asset = {
            **asset,
            "risk_assessment": risk
        }

        risk_assessed_assets.append(
            updated_asset
        )

    output = {
        "source": data.get(
            "source"
        ),

        "format": data.get(
            "format"
        ),

        "asset_count": len(
            risk_assessed_assets
        ),

        "assets": risk_assessed_assets
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

    print(
        f"Risk assessed {len(risk_assessed_assets)} assets "
        f"(re-projected from {RISK_SOURCE_PATH.name})."
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

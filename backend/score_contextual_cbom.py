import json
from pathlib import Path

from models.risk_factors import RiskContext
from services.contextual_risk import calculate_contextual_risk


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-classified-assets.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-contextual-risk-assets.json"
)


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

    assets = data.get("assets", [])

    # -----------------------------------------
    # Prototype default context
    # -----------------------------------------

    context = RiskContext(
        business_criticality="MEDIUM",
        data_lifetime_years=5,
        migration_time_years=2,
        exposure="INTERNAL",
        quantum_threat_horizon_years=10
    )

    assessed_assets = []

    for asset in assets:

        risk = calculate_contextual_risk(
            asset,
            context
        )

        assessed_asset = {
            **asset,
            "contextual_risk": risk
        }

        assessed_assets.append(
            assessed_asset
        )

    output = {
        "source": data.get("source"),
        "format": data.get("format"),
        "asset_count": len(assessed_assets),
        "default_context": {
            "business_criticality":
                context.business_criticality,

            "data_lifetime_years":
                context.data_lifetime_years,

            "migration_time_years":
                context.migration_time_years,

            "exposure":
                context.exposure,

            "quantum_threat_horizon_years":
                context.quantum_threat_horizon_years
        },
        "assets": assessed_assets
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
        f"Contextual risk assessed "
        f"{len(assessed_assets)} assets."
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
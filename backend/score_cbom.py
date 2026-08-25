import json
from pathlib import Path

from services.risk_engine import calculate_base_risk


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-classified-assets.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-risk-assessed-assets.json"
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

    assets = data.get(
        "assets",
        []
    )

    risk_assessed_assets = []

    for asset in assets:

        risk = calculate_base_risk(
            asset
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
        f"Risk assessed "
        f"{len(risk_assessed_assets)} assets."
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
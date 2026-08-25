import json
from pathlib import Path

from services.crypto_classifier import classify_asset


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = BASE_DIR / "data" / "ecdat-assets.json"
OUTPUT_PATH = BASE_DIR / "data" / "ecdat-classified-assets.json"


def main():

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    with open(INPUT_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    assets = data.get("assets", [])

    classified_assets = []

    for asset in assets:
        classified = classify_asset(asset)
        classified_assets.append(classified)

    output = {
        "source": data.get("source"),
        "format": data.get("format"),
        "asset_count": len(classified_assets),
        "assets": classified_assets
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

    print(f"Classified {len(classified_assets)} assets.")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
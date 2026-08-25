import json
from pathlib import Path


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

CBOM_PATH = DATA_DIR / "keycloak-cbom.json"

OUTPUT_PATH = DATA_DIR / "ecdat-assets.json"


# ============================================================
# LOAD CBOM
# ============================================================

def load_cbom():
    print("Loading CBOM...")

    if not CBOM_PATH.exists():
        raise FileNotFoundError(
            f"CBOM file not found: {CBOM_PATH}"
        )

    with open(
        CBOM_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        cbom = json.load(file)

    print("CBOM loaded successfully.")

    return cbom


# ============================================================
# EXTRACT CRYPTO ASSETS
# ============================================================

def extract_assets(cbom):
    components = cbom.get("components", [])

    assets = []

    for component in components:

        crypto_properties = component.get(
            "cryptoProperties",
            {}
        )

        asset_type = crypto_properties.get(
            "assetType"
        )

        algorithm_properties = crypto_properties.get(
            "algorithmProperties",
            {}
        )

        primitive = algorithm_properties.get(
            "primitive"
        )

        occurrences = (
            component
            .get("evidence", {})
            .get("occurrences", [])
        )

        normalized_occurrences = []

        for occurrence in occurrences:

            normalized_occurrences.append({
                "location": occurrence.get(
                    "location"
                ),

                "line": occurrence.get(
                    "line"
                ),

                "offset": occurrence.get(
                    "offset"
                ),

                "context": (
                    occurrence.get(
                        "additionalContext"
                    )
                    or occurrence.get(
                        "context"
                    )
                )
            })

        asset = {
            "bom_ref": component.get(
                "bom-ref"
            ),

            "name": component.get(
                "name",
                "Unknown"
            ),

            "type": component.get(
                "type"
            ),

            "asset_type": asset_type,

            "primitive": primitive,

            "oid": crypto_properties.get(
                "oid"
            ),

            "occurrences": normalized_occurrences
        }

        assets.append(asset)

    return assets


# ============================================================
# SAVE NORMALIZED DATA
# ============================================================

def save_assets(assets, dependencies, cbom):

    output = {
        "source": CBOM_PATH.name,

        "format": cbom.get(
            "bomFormat",
            "Unknown"
        ),

        "spec_version": cbom.get(
            "specVersion"
        ),

        "asset_count": len(assets),

        "assets": assets,

        "dependencies": dependencies
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
        f"Saved normalized CBOM to: {OUTPUT_PATH}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. Load original CBOM
    # --------------------------------------------------------

    cbom = load_cbom()

    # --------------------------------------------------------
    # 2. Extract cryptographic assets
    # --------------------------------------------------------

    assets = extract_assets(cbom)

    print(
        f"Extracted {len(assets)} crypto assets."
    )

    # --------------------------------------------------------
    # 3. Extract dependency relationships
    # --------------------------------------------------------

    dependencies = cbom.get(
        "dependencies",
        []
    )

    print(
        f"Extracted {len(dependencies)} dependency relationships."
    )

    # --------------------------------------------------------
    # 4. Save normalized ECDAT data
    # --------------------------------------------------------

    save_assets(
        assets,
        dependencies,
        cbom
    )

    # --------------------------------------------------------
    # 5. Verification
    # --------------------------------------------------------

    print()
    print("===================================")
    print("ECDAT CBOM IMPORT SUMMARY")
    print("===================================")

    print(
        f"Total crypto assets: {len(assets)}"
    )

    print(
        f"Dependency relationships: "
        f"{len(dependencies)}"
    )

    # --------------------------------------------------------
    # Evidence statistics
    # --------------------------------------------------------

    assets_with_evidence = 0
    total_evidence = 0

    for asset in assets:

        occurrences = asset.get(
            "occurrences",
            []
        )

        if occurrences:
            assets_with_evidence += 1

        total_evidence += len(
            occurrences
        )

    print(
        f"Assets with evidence: "
        f"{assets_with_evidence}"
    )

    print(
        f"Total evidence locations: "
        f"{total_evidence}"
    )

    print()
    print("First 10 assets:")

    for index, asset in enumerate(
        assets[:10],
        start=1
    ):

        print()
        print(
            f"{index}. {asset['name']}"
        )

        print(
            f"   Type      : "
            f"{asset['asset_type']}"
        )

        print(
            f"   Primitive : "
            f"{asset['primitive']}"
        )

        print(
            f"   OID       : "
            f"{asset['oid']}"
        )

        print(
            f"   Locations : "
            f"{len(asset['occurrences'])}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
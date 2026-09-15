import json
from pathlib import Path

from services.crypto_classifier import classify_asset
from services.purpose_resolver import resolve_purpose


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = BASE_DIR / "data" / "ecdat-assets.json"
OUTPUT_PATH = BASE_DIR / "data" / "ecdat-classified-assets.json"


def classify_and_resolve(asset):
    """
    Classify an asset by algorithm family, then resolve its actual
    cryptographic purpose from this specific finding's own CBOM/source
    evidence (see services/purpose_resolver.py) -- so every downstream
    consumer of classification["purpose"] (PQC mapping/ranking,
    migration recommendation, migration complexity) reads a
    repository-specific answer instead of a generic per-algorithm-name
    one, with no changes needed in those consumers.

    "category"/"quantum_status"/"risk_reason" are left as
    crypto_classifier.py produced them -- those describe a fact about
    the algorithm itself (e.g. "RSA is asymmetric"), not about how
    this particular finding is used, so they are not in scope for
    purpose resolution.
    """

    classified = classify_asset(asset)
    resolved = resolve_purpose(classified)

    classified["classification"] = {
        **classified["classification"],
        "purpose": resolved["purpose"],
        "usage": resolved["usage"],
        "purpose_confidence": resolved["confidence"],
        "purpose_evidence_source": resolved["evidence_source"],
        "purpose_evidence_reason": resolved["evidence_reason"],
        "purpose_needs_review": resolved["needs_review"],
        "purpose_evidence": resolved["evidence"],
    }

    return classified


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
        classified = classify_and_resolve(asset)
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
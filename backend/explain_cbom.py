
import json
from pathlib import Path

from services.evidence_engine import extract_evidence
from services.evidence_confidence import calculate_evidence_confidence
from services.contextual_risk import calculate_contextual_risk
from services.explanation_engine import generate_risk_explanation
from services.risk_context import derive_risk_context


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-classified-assets.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-explainable-risk.json"
)


def main():

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

    analyzed_assets = []

    for asset in assets:

        # -------------------------------
        # Risk
        # -------------------------------

        # Each asset gets its own RiskContext, derived from that
        # asset's own CBOM evidence (occurrence file paths, API
        # context strings, occurrence count, classification
        # category) instead of one context object shared identically
        # by every asset in every repository. See
        # services/risk_context.py for exactly what is derived and
        # why two dimensions (data lifetime, quantum threat horizon)
        # remain fixed, documented assumptions rather than invented
        # per-asset values.
        context = derive_risk_context(asset)

        risk = calculate_contextual_risk(
            asset,
            context
        )

        # -------------------------------
        # Evidence
        # -------------------------------

        evidence = extract_evidence(
            asset
        )
        evidence_confidence = calculate_evidence_confidence(
            asset
        )
        
        

        # -------------------------------
        # Explanation
        # -------------------------------

        explanation = generate_risk_explanation(
            asset,
            risk
        )

        analyzed_asset = {
    **asset,

    "risk_assessment": risk,

    "evidence": evidence,

    "evidence_confidence": evidence_confidence,

    "explanation": explanation
}

        analyzed_assets.append(
            analyzed_asset
        )

    output = {

        "source": data.get(
            "source"
        ),

        "format": data.get(
            "format"
        ),

        "asset_count": len(
            analyzed_assets
        ),

        "assets": analyzed_assets
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
        f"Generated explainable analysis "
        f"for {len(analyzed_assets)} assets."
    )

    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
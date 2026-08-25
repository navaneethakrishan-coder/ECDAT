
import json
from pathlib import Path

from services.evidence_engine import extract_evidence
from services.evidence_confidence import calculate_evidence_confidence
from services.contextual_risk import calculate_contextual_risk
from services.explanation_engine import generate_risk_explanation
from models.risk_factors import RiskContext


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

    # Current prototype context
    context = RiskContext(
        business_criticality="MEDIUM",
        data_lifetime_years=5,
        migration_time_years=2,
        exposure="INTERNAL",
        quantum_threat_horizon_years=10
    )

    analyzed_assets = []

    for asset in assets:

        # -------------------------------
        # Risk
        # -------------------------------

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
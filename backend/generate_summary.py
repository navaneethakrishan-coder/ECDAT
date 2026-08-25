import json
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent

INPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-explainable-risk.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "ecdat-risk-summary.json"
)


def main():

    with open(
        INPUT_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    assets = data.get("assets", [])

    severity_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }

    confidence_counts = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }

    total_score = 0

    for asset in assets:

        risk = asset.get(
            "risk_assessment",
            {}
        )

        severity = risk.get(
            "severity",
            "LOW"
        )

        score = risk.get(
            "final_score",
            0
        )

        confidence = asset.get(
            "evidence_confidence",
            {}
        ).get(
            "confidence",
            "LOW"
        )

        severity_counts[severity] = (
            severity_counts.get(severity, 0) + 1
        )

        confidence_counts[confidence] = (
            confidence_counts.get(confidence, 0) + 1
        )

        total_score += score

    average_score = (
        total_score / len(assets)
        if assets
        else 0
    )

    # Top 10 assets by risk
    top_assets = sorted(
        assets,
        key=lambda x: x.get(
            "risk_assessment",
            {}
        ).get(
            "final_score",
            0
        ),
        reverse=True
    )[:10]

    top_risk_assets = []

    for asset in top_assets:

        risk = asset.get(
            "risk_assessment",
            {}
        )

        top_risk_assets.append({
            "name": asset.get(
                "name",
                "Unknown"
            ),

            "score": risk.get(
                "final_score",
                0
            ),

            "severity": risk.get(
                "severity",
                "UNKNOWN"
            ),

            "evidence_confidence":
                asset.get(
                    "evidence_confidence",
                    {}
                ).get(
                    "confidence",
                    "UNKNOWN"
                )
        })

    summary = {

        "total_assets": len(assets),

        "severity_distribution":
            severity_counts,

        "evidence_confidence_distribution":
            confidence_counts,

        "average_risk_score":
            round(average_score, 2),

        "top_risk_assets":
            top_risk_assets
    }

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2
        )

    print()
    print("=" * 40)
    print("ECDAT QUANTUM RISK SUMMARY")
    print("=" * 40)

    print(
        f"Total Assets: {len(assets)}"
    )

    print()
    print("Severity:")

    for severity, count in severity_counts.items():
        print(
            f"  {severity}: {count}"
        )

    print()
    print(
        f"Average Risk Score: "
        f"{average_score:.2f}"
    )

    print()
    print("Evidence Confidence:")

    for confidence, count in confidence_counts.items():
        print(
            f"  {confidence}: {count}"
        )

    print()
    print("Top Risk Assets:")

    for index, asset in enumerate(
        top_risk_assets,
        start=1
    ):
        print(
            f"  {index}. "
            f"{asset['name']} — "
            f"{asset['score']} "
            f"({asset['severity']})"
        )

    print()
    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
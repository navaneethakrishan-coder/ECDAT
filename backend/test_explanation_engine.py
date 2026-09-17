"""
Regression tests for services/explanation_engine.py.

The explanation must correspond exactly to what
calculate_contextual_risk() computed: every stated contribution must
be a real score_breakdown value, UNKNOWN factors must be reported as
UNKNOWN (never as zero points), and Mosca urgency must never be
presented as a score contribution.
"""

import json
from pathlib import Path

from models.risk_factors import RiskContext
from services.contextual_risk import calculate_contextual_risk
from services.explanation_engine import generate_risk_explanation


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Six factors, each displayed to 2 decimals: the rounded terms can
# differ from the once-rounded final_score by at most 6 x 0.005.
ROUNDING_TOLERANCE = 0.035


def _asset(occurrences=None):
    return {
        "name": "Ed25519",
        "classification": {
            "category": "asymmetric",
            "quantum_status": "vulnerable",
            "risk_reason": "Elliptic-curve signatures are broken by Shor's algorithm.",
        },
        "occurrences": occurrences or [
            {"location": "src/sign.py", "line": 10, "context": "Signature#sign()"},
            {"location": "src/verify.py", "line": 20, "context": "Signature#verify()"},
        ],
    }


def _explain(context):
    asset = _asset()
    risk = calculate_contextual_risk(asset, context)
    return risk, generate_risk_explanation(asset, risk)


def test_contributions_are_the_real_breakdown_values():
    risk, explanation = _explain(
        RiskContext(
            business_criticality="HIGH",
            data_lifetime_years=15,
            migration_time_years=3,
            exposure="INTERNET",
            quantum_threat_horizon_years=10,
        )
    )

    breakdown = risk["score_breakdown"]

    known = [item for item in explanation["contributions"] if item["known"]]

    assert {item["factor"] for item in known} == set(breakdown.keys())

    for item in known:
        assert item["weighted_score"] == breakdown[item["factor"]]["weighted_score"]
        assert item["raw_score"] == breakdown[item["factor"]]["raw_score"]
        assert item["weight"] == breakdown[item["factor"]]["weight"]

    assert abs(explanation["contribution_total"] - risk["final_score"]) <= ROUNDING_TOLERANCE


def test_nonzero_factors_are_never_reported_as_zero_points():
    risk, explanation = _explain(
        RiskContext(
            business_criticality="MEDIUM",
            data_lifetime_years=None,
            migration_time_years=2,
            exposure="INTERNAL",
            quantum_threat_horizon_years=10,
        )
    )

    quantum = risk["score_breakdown"]["quantum_risk"]["weighted_score"]

    assert quantum > 0
    assert any(f"Quantum risk contributed {quantum} points" in reason for reason in explanation["reasons"])
    assert not any("contributed 0 points" in reason for reason in explanation["reasons"])


def test_unknown_data_lifetime_is_reported_as_unknown_not_zero():
    risk, explanation = _explain(
        RiskContext(
            business_criticality="MEDIUM",
            data_lifetime_years=None,
            migration_time_years=2,
            exposure="INTERNAL",
            quantum_threat_horizon_years=10,
        )
    )

    lifetime = next(item for item in explanation["contributions"] if item["factor"] == "data_lifetime")

    assert lifetime["known"] is False
    assert "weighted_score" not in lifetime
    assert any("Data lifetime is UNKNOWN" in reason for reason in explanation["reasons"])

    # Excluded factors are not counted, so the known contributions
    # alone must still reconcile with the score.
    assert abs(explanation["contribution_total"] - risk["final_score"]) <= ROUNDING_TOLERANCE


def test_mosca_is_never_presented_as_a_score_contribution():
    _, with_lifetime = _explain(
        RiskContext(
            business_criticality="MEDIUM",
            data_lifetime_years=20,
            migration_time_years=2,
            exposure="INTERNAL",
            quantum_threat_horizon_years=10,
        )
    )

    assert "mosca" not in {item["factor"] for item in with_lifetime["contributions"]}
    assert any("informational only, not a weighted risk factor" in reason for reason in with_lifetime["reasons"])
    assert not any("Mosca-style migration urgency contributed" in reason for reason in with_lifetime["reasons"])


def test_persisted_pipeline_explanations_reconcile_with_scores():
    """
    Every explanation the active pipeline wrote to
    ecdat-explainable-risk.json must reconcile with that same record's
    final_score -- guards the stage wiring, not just the function.
    """

    with (DATA_DIR / "ecdat-explainable-risk.json").open(encoding="utf-8") as file:
        assets = json.load(file)["assets"]

    assert assets

    for asset in assets:
        explanation = asset["explanation"]
        final_score = asset["risk_assessment"]["final_score"]

        assert explanation["final_score"] == final_score, asset["bom_ref"]
        assert abs(explanation["contribution_total"] - final_score) <= ROUNDING_TOLERANCE, asset["bom_ref"]


if __name__ == "__main__":
    test_contributions_are_the_real_breakdown_values()
    test_nonzero_factors_are_never_reported_as_zero_points()
    test_unknown_data_lifetime_is_reported_as_unknown_not_zero()
    test_mosca_is_never_presented_as_a_score_contribution()
    test_persisted_pipeline_explanations_reconcile_with_scores()

    print("All explanation-engine tests passed.")

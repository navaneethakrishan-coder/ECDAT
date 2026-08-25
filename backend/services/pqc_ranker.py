from typing import Any, Dict, List


COMPATIBILITY_SCORE = {
    "HIGH": 100,
    "MEDIUM": 70,
    "LOW": 40,
}


def _purpose_score(
    asset: Dict[str, Any],
    candidate: Dict[str, Any],
) -> float:
    """
    Score how well the PQC candidate family matches the
    cryptographic purpose of the current asset.
    """

    purposes = asset.get("purpose", [])
    family = candidate.get("family", "")

    if isinstance(purposes, str):
        purposes = [purposes]

    purposes = [str(p).lower() for p in purposes]

    if "key-agreement" in purposes or "key-establishment" in purposes:
        return 100.0 if family == "KEM" else 20.0

    if "digital-signature" in purposes:
        return 100.0 if family == "digital-signature" else 20.0

    if family == "KEM":
        return 60.0

    if family == "digital-signature":
        return 60.0

    return 30.0


def _compatibility_score(candidate: Dict[str, Any]) -> float:
    compatibility = str(
        candidate.get("compatibility", "LOW")
    ).upper()

    return COMPATIBILITY_SCORE.get(
        compatibility,
        40,
    )


def _parameter_score(candidate: Dict[str, Any]) -> float:
    """
    ECDAT decision-support heuristic.

    This does NOT claim that a larger parameter set is always
    the correct production choice.
    """

    name = str(candidate.get("name", "")).upper()

    if name in {"ML-KEM-512", "ML-DSA-44"}:
        return 75.0

    if name in {"ML-KEM-768", "ML-DSA-65"}:
        return 100.0

    if name in {"ML-KEM-1024", "ML-DSA-87"}:
        return 90.0

    if name == "SLH-DSA":
        return 80.0

    return 50.0


def _complexity_score(
    asset: Dict[str, Any],
) -> float:
    """
    Lower migration complexity should slightly improve the
    candidate ranking.
    """

    complexity = asset.get("migration_complexity")

    if complexity is None:
        return 70.0

    try:
        complexity = float(complexity)
    except (TypeError, ValueError):
        return 70.0

    # Lower complexity is better.
    return max(
        0.0,
        min(
            100.0,
            100.0 - complexity,
        ),
    )


def _risk_score(
    asset: Dict[str, Any],
) -> float:
    """
    Current quantum risk.

    A high-risk asset receives stronger migration attention.
    """

    risk = asset.get("quantum_risk", 0)

    try:
        return max(
            0.0,
            min(
                100.0,
                float(risk),
            ),
        )
    except (TypeError, ValueError):
        return 0.0


def _blast_radius_score(
    asset: Dict[str, Any],
) -> float:
    blast = asset.get("blast_radius", 0)

    try:
        return max(
            0.0,
            min(
                100.0,
                float(blast),
            ),
        )
    except (TypeError, ValueError):
        return 0.0


def score_candidate(
    asset: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate an explainable ECDAT PQC candidate score.

    Weights:

    Purpose compatibility     30%
    Candidate compatibility   25%
    Parameter suitability     15%
    Current quantum risk      10%
    Blast radius              10%
    Migration complexity      10%
    """

    purpose = _purpose_score(asset, candidate)
    compatibility = _compatibility_score(candidate)
    parameter = _parameter_score(candidate)
    risk = _risk_score(asset)
    blast = _blast_radius_score(asset)
    complexity = _complexity_score(asset)

    weighted = {
        "purpose_compatibility": {
            "raw_score": purpose,
            "weight": 0.30,
            "weighted_score": purpose * 0.30,
        },
        "candidate_compatibility": {
            "raw_score": compatibility,
            "weight": 0.25,
            "weighted_score": compatibility * 0.25,
        },
        "parameter_suitability": {
            "raw_score": parameter,
            "weight": 0.15,
            "weighted_score": parameter * 0.15,
        },
        "quantum_risk": {
            "raw_score": risk,
            "weight": 0.10,
            "weighted_score": risk * 0.10,
        },
        "blast_radius": {
            "raw_score": blast,
            "weight": 0.10,
            "weighted_score": blast * 0.10,
        },
        "migration_complexity": {
            "raw_score": complexity,
            "weight": 0.10,
            "weighted_score": complexity * 0.10,
        },
    }

    score = sum(
        item["weighted_score"]
        for item in weighted.values()
    )

    reasons: List[str] = []

    if purpose >= 90:
        reasons.append(
            "Candidate family strongly matches the cryptographic purpose."
        )
    elif purpose >= 60:
        reasons.append(
            "Candidate family has partial compatibility with the purpose."
        )
    else:
        reasons.append(
            "Candidate family has weak purpose compatibility."
        )

    if compatibility >= 90:
        reasons.append(
            "Candidate has HIGH compatibility in the ECDAT PQC registry."
        )
    elif compatibility >= 60:
        reasons.append(
            "Candidate has MEDIUM compatibility in the ECDAT PQC registry."
        )

    if parameter >= 90:
        reasons.append(
            "Candidate uses a strong parameter-set suitability score."
        )

    if risk >= 70:
        reasons.append(
            "The current asset has high quantum-risk pressure."
        )

    if blast >= 70:
        reasons.append(
            "The current asset has a large potential migration blast radius."
        )

    return {
        "candidate": candidate.get("name"),
        "family": candidate.get("family"),
        "score": round(score, 2),
        "compatibility": candidate.get("compatibility"),
        "score_breakdown": weighted,
        "reason": candidate.get("reason"),
        "tradeoffs": candidate.get("tradeoffs", []),
        "explanation": {
            "summary": (
                f"{candidate.get('name')} received an ECDAT "
                f"candidate score of {round(score, 2)}/100."
            ),
            "reasons": reasons,
        },
    }


def rank_candidates(
    asset: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scored = [
        score_candidate(asset, candidate)
        for candidate in candidates
    ]

    scored.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    for index, candidate in enumerate(scored, start=1):
        candidate["rank"] = index

    return scored
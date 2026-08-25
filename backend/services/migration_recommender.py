from typing import Any, Dict, List


RECOMMENDED = "RECOMMENDED"
CONDITIONALLY_RECOMMENDED = "CONDITIONALLY_RECOMMENDED"
ARCHITECTURAL_MIGRATION = "ARCHITECTURAL_MIGRATION"
NO_DIRECT_REPLACEMENT = "NO_DIRECT_REPLACEMENT"
NOT_APPLICABLE = "NOT_APPLICABLE"


def _priority_score(asset: Dict[str, Any]) -> float:
    value = asset.get("migration_priority", 0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _quantum_risk(asset: Dict[str, Any]) -> float:
    value = asset.get("quantum_risk", 0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _blast_radius(asset: Dict[str, Any]) -> float:
    value = asset.get("blast_radius", 0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _complexity(asset: Dict[str, Any]) -> float:
    value = asset.get("migration_complexity", 0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_high_impact(asset: Dict[str, Any]) -> bool:
    return (
        _priority_score(asset) >= 70
        or _blast_radius(asset) >= 70
        or _complexity(asset) >= 70
    )


def _candidate_family_matches(
    asset: Dict[str, Any],
    candidate: Dict[str, Any],
) -> bool:
    purposes = asset.get("purpose", [])
    family = str(candidate.get("family", "")).lower()

    if isinstance(purposes, str):
        purposes = [purposes]

    purposes = [
        str(p).lower()
        for p in purposes
    ]

    if (
        "key-agreement" in purposes
        or "key-establishment" in purposes
    ):
        return family == "kem"

    if "digital-signature" in purposes:
        return family == "digital-signature"

    return False


def recommend_migration(
    asset: Dict[str, Any],
    ranked_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:

    name = asset.get("name", "Unknown")
    category = asset.get("category")
    purposes = asset.get("purpose", [])
    migration_type = asset.get("migration_type")
    confidence = str(
        asset.get("confidence", "LOW")
    ).upper()

    if isinstance(purposes, str):
        purposes = [purposes]

    # ---------------------------------------------------------
    # No direct PQC replacement
    # ---------------------------------------------------------

    if migration_type == "no-direct-pqc-replacement":
        return {
            "asset": name,
            "decision": NO_DIRECT_REPLACEMENT,
            "recommended_candidate": None,
            "confidence": confidence,
            "reason": (
                "The asset does not have a direct replacement in "
                "the current PQC registry."
            ),
            "conditions": [],
            "risks": [
                "PQC migration requires evaluating the surrounding "
                "cryptographic construction rather than replacing "
                "the algorithm directly."
            ],
            "explanation": {
                "summary": (
                    f"{name} does not have a direct PQC replacement."
                ),
                "reasons": [
                    "The asset's cryptographic role is not directly "
                    "replaced by ML-KEM or ML-DSA."
                ],
            },
        }

    # ---------------------------------------------------------
    # Not applicable
    # ---------------------------------------------------------

    if migration_type == "not-applicable":
        return {
            "asset": name,
            "decision": NOT_APPLICABLE,
            "recommended_candidate": None,
            "confidence": confidence,
            "reason": (
                "No applicable PQC migration decision was identified."
            ),
            "conditions": [],
            "risks": [],
            "explanation": {
                "summary": (
                    f"No PQC migration recommendation is available "
                    f"for {name}."
                ),
                "reasons": [],
            },
        }

    # ---------------------------------------------------------
    # Architectural migration
    # ---------------------------------------------------------

    if migration_type == "architectural-migration":
        return {
            "asset": name,
            "decision": ARCHITECTURAL_MIGRATION,
            "recommended_candidate": (
                ranked_candidates[0]["candidate"]
                if ranked_candidates
                else None
            ),
            "confidence": "MEDIUM",
            "reason": (
                "The asset requires architectural or usage-specific "
                "migration rather than a guaranteed one-to-one "
                "algorithm replacement."
            ),
            "conditions": [
                "Confirm the exact cryptographic purpose from source evidence.",
                "Confirm protocol and implementation compatibility.",
                "Evaluate interoperability with existing systems.",
                "Perform performance and operational testing.",
                "Validate the migration in a non-production environment.",
            ],
            "risks": [
                "The recorded classification may not uniquely identify "
                "the required PQC primitive.",
                "A protocol-level migration may affect multiple assets.",
            ],
            "explanation": {
                "summary": (
                    f"{name} requires architectural migration planning."
                ),
                "reasons": [
                    "The asset's purpose is not specific enough "
                    "for a guaranteed direct replacement.",
                    "PQC candidate selection depends on actual usage.",
                ],
            },
        }

    # ---------------------------------------------------------
    # No candidates
    # ---------------------------------------------------------

    if not ranked_candidates:
        return {
            "asset": name,
            "decision": NO_DIRECT_REPLACEMENT,
            "recommended_candidate": None,
            "confidence": "LOW",
            "reason": (
                "No PQC candidates were available for this asset."
            ),
            "conditions": [
                "Review the asset classification and source evidence."
            ],
            "risks": [
                "Insufficient information for a reliable PQC recommendation."
            ],
            "explanation": {
                "summary": (
                    f"No PQC candidate could be recommended for {name}."
                ),
                "reasons": [
                    "The candidate list was empty."
                ],
            },
        }

    # ---------------------------------------------------------
    # Candidate selection
    # ---------------------------------------------------------

    compatible_candidates = [
        candidate
        for candidate in ranked_candidates
        if _candidate_family_matches(
            asset,
            candidate,
        )
    ]

    if compatible_candidates:
        selected = compatible_candidates[0]
    else:
        selected = ranked_candidates[0]

    selected_score = float(
        selected.get("score", 0)
    )

    conditions = [
        "Validate implementation support.",
        "Validate interoperability.",
        "Perform performance testing.",
        "Perform security testing.",
        "Validate migration in a controlled environment.",
    ]

    reasons = [
        f"{selected['candidate']} achieved the highest compatible "
        f"ECDAT candidate score of {selected_score:.2f}.",
        f"Current quantum-risk score is "
        f"{_quantum_risk(asset):.2f}.",
    ]

    # ---------------------------------------------------------
    # Decision thresholds
    # ---------------------------------------------------------

    if (
        selected_score >= 80
        and confidence == "HIGH"
        and not _is_high_impact(asset)
    ):
        decision = RECOMMENDED

    elif selected_score >= 70:
        decision = CONDITIONALLY_RECOMMENDED

        conditions.extend([
            "Review the asset's migration priority before scheduling migration.",
            "Assess dependency and blast-radius impact.",
        ])

    else:
        decision = CONDITIONALLY_RECOMMENDED

        conditions.extend([
            "Perform detailed engineering review before migration.",
            "Confirm that the selected candidate fits the application architecture.",
        ])

    # High-impact assets should not be represented as automatically safe
    # production recommendations.
    if _is_high_impact(asset):
        decision = CONDITIONALLY_RECOMMENDED

        conditions.extend([
            "Because this asset has significant migration impact, "
            "perform dependency-aware migration planning.",
            "Define rollback and recovery procedures.",
        ])

    return {
        "asset": name,
        "decision": decision,
        "recommended_candidate": selected["candidate"],
        "recommended_candidate_score": round(
            selected_score,
            2,
        ),
        "confidence": confidence,
        "reason": (
            "The recommendation is based on ECDAT candidate ranking, "
            "cryptographic purpose compatibility, quantum risk, "
            "migration impact and implementation considerations."
        ),
        "conditions": conditions,
        "risks": [
            "Candidate ranking is a decision-support heuristic.",
            "Production compatibility must be validated independently.",
        ],
        "explanation": {
            "summary": (
                f"{name} is {decision} for migration to "
                f"{selected['candidate']}."
            ),
            "reasons": reasons,
        },
    }
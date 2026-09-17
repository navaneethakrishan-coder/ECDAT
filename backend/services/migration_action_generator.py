from typing import Any, Dict, List

from knowledge import migration_strategy_policy as policy


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _get_migration_type(migration: Dict[str, Any]) -> str:
    value = migration.get("migration_type")

    if value:
        return _normalize(value)

    pqc_analysis = migration.get("pqc_analysis", {})

    if isinstance(pqc_analysis, dict):
        value = pqc_analysis.get("migration_type")

        if value:
            return _normalize(value)

    migration_section = migration.get("migration", {})

    if isinstance(migration_section, dict):
        value = migration_section.get("migration_type")

        if value:
            return _normalize(value)

    return ""


def _get_pqc_candidate(migration: Dict[str, Any]) -> str:
    candidates = migration.get("ranked_candidates", [])

    if not isinstance(candidates, list) or not candidates:
        return ""

    first = candidates[0]

    if not isinstance(first, dict):
        return ""

    return str(first.get("candidate", ""))


def _get_pqc_family(migration: Dict[str, Any]) -> str:
    candidates = migration.get("ranked_candidates", [])

    if not isinstance(candidates, list) or not candidates:
        return ""

    first = candidates[0]

    if not isinstance(first, dict):
        return ""

    return str(first.get("family", ""))


def _get_migration_strategy(migration: Dict[str, Any]):
    """
    The purpose-aware strategy decided by services/migration_strategy.py
    and recorded by generate_pqc_migration_plan.py, if present.
    """

    strategy = migration.get("migration_strategy")

    if isinstance(strategy, dict) and strategy.get("strategy"):
        return strategy

    return None


def _purpose_list(mapping: Dict[str, Any]) -> List[str]:
    classification = mapping.get("classification", {})

    if not isinstance(classification, dict):
        return []

    purposes = classification.get("purpose", [])

    if isinstance(purposes, str):
        purposes = [purposes]

    if not isinstance(purposes, list):
        return []

    return [_normalize(item) for item in purposes]


def _build_common_actions(asset: str) -> List[str]:
    return [
        "Validate the cryptographic usage.",
        "Review all identified source locations.",
        "Identify dependent interfaces and protocol assumptions.",
        "Validate implementation support for the selected migration approach.",
        "Perform interoperability testing.",
        "Perform security testing.",
        "Perform performance testing.",
        "Validate the migration in a controlled environment.",
    ]


def _build_key_agreement_actions(candidate: str) -> List[str]:
    actions = [
        "Identify the current key-establishment protocol and handshake flow.",
        "Identify all inputs and outputs of the existing key-agreement operation.",
        "Evaluate replacement of the current key-agreement mechanism with a PQC KEM for post-quantum key establishment.",
    ]

    if candidate:
        actions.append(
            f"Evaluate {candidate} as the target post-quantum KEM."
        )

    actions.extend([
        "Update protocol negotiation and key-establishment handling where required.",
        "Validate key encapsulation and decapsulation integration.",
        "Validate interoperability with all communicating endpoints.",
    ])

    return actions


def _build_signature_actions(candidate: str) -> List[str]:
    actions = [
        "Identify all digital-signature generation and verification paths.",
        "Identify certificate, key, and signature-format dependencies.",
        "Evaluate migration of the current signature mechanism to a PQC signature scheme.",
    ]

    if candidate:
        actions.append(
            f"Evaluate {candidate} as the target post-quantum signature algorithm."
        )

    actions.extend([
        "Update signature generation and verification interfaces where required.",
        "Review certificate and trust-chain compatibility.",
        "Validate signature encoding and interoperability.",
    ])

    return actions


def _build_encryption_actions(candidate: str) -> List[str]:
    actions = [
        "Identify the encryption/decryption workflow.",
        "Identify key-management and key-establishment dependencies.",
        "Determine whether the asset requires direct replacement or architectural migration.",
    ]

    if candidate:
        actions.append(
            f"Evaluate {candidate} where it is applicable to the identified key-establishment function."
        )

    actions.extend([
        "Validate encryption compatibility and data-format requirements.",
        "Validate backward compatibility during migration.",
    ])

    return actions


def _build_hash_actions() -> List[str]:
    return [
        "Identify whether the hash is used for integrity, signatures, password processing, or another function.",
        "Determine whether quantum security margin is sufficient for the identified use case.",
        "Avoid treating a PQC KEM or signature algorithm as a direct hash replacement.",
        "Evaluate an appropriate hash migration independently from asymmetric PQC migration.",
        "Update dependent validation and test cases.",
    ]


def _build_architectural_actions(candidate: str) -> List[str]:
    actions = [
        "Determine the exact cryptographic purpose from source usage.",
        "Identify whether the asset performs key agreement, encryption, signing, verification, or key management.",
        "Review all affected interfaces and protocol dependencies.",
        "Do not perform a blind direct algorithm replacement.",
    ]

    if candidate:
        actions.append(
            f"Use {candidate} only as a migration direction after confirming the actual cryptographic purpose."
        )

    actions.extend([
        "Perform architectural migration planning for the target post-quantum cryptographic architecture.",
        "Validate protocol and interoperability requirements.",
        "Create a controlled migration and rollback strategy.",
    ])

    return actions


# ================================================================
# Strategy-driven actions
#
# When a purpose-aware migration strategy is available, actions are
# derived from it -- its evidence-resolved role, its selected PQC
# component (already restricted to the role's family), and hybrid vs
# direct -- instead of from the raw purpose list and the first-ranked
# candidate. That is what keeps an encryption-only finding from ever
# receiving signature actions, and an ambiguous finding from receiving
# a committed replacement.
# ================================================================

def _build_review_actions(strategy: Dict[str, Any]) -> List[str]:
    code = strategy.get("reason_code")
    options = strategy.get("review_options") or []

    actions = [
        "Do not replace this primitive until its migration-strategy review is resolved.",
    ]

    if code == "ambiguous-purpose" and options:
        labels = [option.get("purpose_class_label") for option in options]
        actions.append(
            f"Confirm from source usage which role this finding performs: {' or '.join(labels)}."
        )

        for option in options:
            if option.get("top_candidate"):
                actions.append(
                    f"If it performs {option.get('purpose_class_label')}, evaluate "
                    f"{option.get('top_candidate')} ({option.get('pqc_family')})."
                )

    elif code == "conflicting-purpose-evidence":
        actions.append(
            "Reconcile the conflicting CBOM primitive and source-context evidence for this finding."
        )

    elif code in {
        "governing-algorithm-needs-review",
        "key-material-governed-by-conflicting-strategies",
        "key-material-without-governing-algorithm",
    }:
        actions.append(
            "Resolve the migration strategy of the algorithm that uses this key material first; the key material follows that decision."
        )

    elif code == "no-suitable-pqc-mapping":
        actions.append(
            "Identify a standardized post-quantum algorithm for this role; none is available in the current PQC mapping."
        )

    elif code == "protocol-components-unresolved":
        actions.append(
            "Identify the protocol's key-exchange and authentication components and assess each separately."
        )

    elif code == "quantum-status-unconfirmed":
        actions.append(
            "Confirm the primitive and its parameters to determine whether it is quantum-vulnerable."
        )

    else:
        actions.append(
            "Determine this finding's cryptographic purpose from source usage."
        )

    # Close with what the review actually has to establish: a finding
    # whose role is already resolved still needs its quantum status or a
    # PQC mapping confirmed, not its purpose.
    if code == "quantum-status-unconfirmed":
        actions.append(
            "Record the confirmed quantum status so a migration strategy can be derived."
        )
    elif code == "no-suitable-pqc-mapping":
        actions.append(
            "Record the selected post-quantum algorithm so a migration strategy can be derived."
        )
    else:
        actions.append(
            "Record the confirmed purpose so a migration strategy can be derived."
        )

    return actions


def _build_keep_actions(strategy: Dict[str, Any]) -> List[str]:
    hardening = strategy.get("classical_hardening") or {}
    status = hardening.get("status")
    reason = hardening.get("reason")

    actions = [
        "No post-quantum algorithm replacement is required for this cryptographic role.",
    ]

    if status == "required":
        actions.append(f"Replace this primitive with a stronger classical alternative: {reason}")
    elif status == "recommended":
        actions.append(f"Consider classical hardening: {reason}")
    elif status == "review":
        actions.append(f"Confirm the configuration: {reason}")
    elif reason:
        actions.append(f"Record the assessment against Grover's algorithm: {reason}")

    if status == "required":
        actions.append(
            "Track the classical replacement in the cryptographic inventory until it is complete."
        )
    else:
        actions.append(
            "Keep this primitive in the cryptographic inventory and re-assess if its usage changes."
        )

    return actions


def _build_hybrid_actions(strategy: Dict[str, Any]) -> List[str]:
    role = strategy.get("purpose_class")
    family = strategy.get("pqc_family")
    pqc = strategy.get("pqc_component")
    classical = strategy.get("classical_component")

    if role == policy.KEY_MATERIAL:
        return [
            f"Generate {pqc} key material to be used alongside this existing key during the hybrid transition.",
            "Update key storage, distribution and rotation to handle both keys.",
            "Retire this key once the governing algorithm's classical component is removed.",
        ]

    if family == "KEM":
        return [
            f"Introduce {pqc} key encapsulation alongside the existing {classical} operation.",
            "Derive the session or content key from both shared secrets through a KDF combiner (hybrid key establishment).",
            "Negotiate hybrid support with peers, keeping the classical path only for peers without PQC support.",
            "Validate encapsulation, decapsulation and combiner outputs in interoperability tests.",
            f"Plan removal of the classical component once every peer supports {pqc}.",
        ]

    if family == "digital-signature":
        return [
            f"Add {pqc} signatures alongside existing {classical} signatures (composite or dual signing).",
            f"Update verification to accept the dual-signature format while legacy verifiers still validate {classical}.",
            "Review certificate, key and signature-format dependencies for the dual-signature transition.",
            f"Plan retirement of {classical} signatures once every verifier supports {pqc}.",
        ]

    return _build_common_actions("")


def _build_direct_actions(strategy: Dict[str, Any]) -> List[str]:
    role = strategy.get("purpose_class")
    pqc = strategy.get("pqc_component") or ""

    if role == policy.KEY_MATERIAL:
        return [
            f"Generate replacement {pqc} key material.",
            "Retire and securely destroy this key after the governing algorithm is migrated.",
        ]

    if role == policy.KEY_ESTABLISHMENT:
        return _build_key_agreement_actions(pqc)

    if role == policy.PUBLIC_KEY_ENCRYPTION:
        return _build_encryption_actions(pqc)

    if role == policy.DIGITAL_SIGNATURE:
        return _build_signature_actions(pqc)

    return _build_common_actions("")


_STRATEGY_BUILDERS = {
    "NEEDS_REVIEW": _build_review_actions,
    "KEEP": _build_keep_actions,
    "HYBRID": _build_hybrid_actions,
    "DIRECT_PQC": _build_direct_actions,
}


def _deduplicate(actions: List[str]) -> List[str]:
    result = []
    seen = set()

    for action in actions:
        normalized = _normalize(action)

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(action)

    return result


# Purposes that each select a different PQC family.
_ROLE_SPECIFIC_PURPOSES = ("key-agreement", "digital-signature", "encryption")


def generate_migration_actions(
    mapping: Dict[str, Any],
    impact: Dict[str, Any],
    migration: Dict[str, Any],
) -> Dict[str, Any]:

    asset = str(mapping.get("asset", "UNKNOWN"))

    migration_type = _get_migration_type(migration)
    strategy = _get_migration_strategy(migration)

    if strategy:
        candidate = strategy.get("pqc_component") or ""
        family = strategy.get("pqc_family") or ""
    else:
        candidate = _get_pqc_candidate(migration)
        family = _get_pqc_family(migration)

    purposes = _purpose_list(mapping)

    actions = []
    reasons = []

    if strategy:

        builder = _STRATEGY_BUILDERS.get(strategy["strategy"], lambda _: _build_common_actions(asset))

        actions.extend(builder(strategy))

        reasons.append(
            f"Migration strategy {strategy['strategy']}: {strategy.get('rationale')}"
        )

    elif migration_type == "pqc-candidate":

        role_purposes = [
            purpose for purpose in _ROLE_SPECIFIC_PURPOSES if purpose in purposes
        ]

        if len(role_purposes) > 1:

            # Several possible roles need different PQC families;
            # picking one by branch order would silently choose a role.
            actions.extend(
                _build_architectural_actions("")
            )

            reasons.append(
                "The asset's recorded purposes span multiple cryptographic roles "
                f"({', '.join(role_purposes)}), so no role-specific actions are "
                "generated until the actual usage is confirmed."
            )

        elif "key-agreement" in purposes:

            actions.extend(
                _build_key_agreement_actions(candidate)
            )

            reasons.append(
                "The asset performs key agreement and can be evaluated against a PQC KEM."
            )

        elif "digital-signature" in purposes:

            actions.extend(
                _build_signature_actions(candidate)
            )

            reasons.append(
                "The asset performs digital signatures and can be evaluated against a PQC signature scheme."
            )

        elif "encryption" in purposes:

            actions.extend(
                _build_encryption_actions(candidate)
            )

            reasons.append(
                "The asset performs encryption and requires usage-specific migration analysis."
            )

        elif "hash" in purposes:

            actions.extend(
                _build_hash_actions()
            )

            reasons.append(
                "Hash functions require usage-specific migration analysis rather than direct PQC replacement."
            )

        else:

            actions.extend(
                _build_common_actions(asset)
            )

            reasons.append(
                "The asset is marked as a PQC migration candidate but its exact purpose requires source validation."
            )

    elif migration_type == "architectural-migration":

        actions.extend(
            _build_architectural_actions(candidate)
        )

        reasons.append(
            "The asset requires usage-specific or architectural migration planning."
        )

    elif migration_type == "no-direct-pqc-replacement":

        actions.extend([
            "Validate the current cryptographic purpose.",
            "Determine whether the asset requires PQC migration or conventional cryptographic hardening.",
            "Do not apply a PQC algorithm as a blind direct replacement.",
            "Review dependent protocols and cryptographic constructions.",
            "Evaluate an architectural migration if the surrounding protocol is quantum-vulnerable.",
            "Perform security and interoperability testing.",
        ])

        reasons.append(
            "No direct PQC replacement is currently available for the identified asset."
        )

    else:

        actions.extend(
            _build_common_actions(asset)
        )

        reasons.append(
            "Migration classification is unavailable, so conservative validation actions are recommended."
        )

    actions.extend([
        "Review the identified affected source files before implementation.",
        "Update automated tests for the migrated cryptographic path.",
        "Document the migration decision and validation results.",
    ])

    actions = _deduplicate(actions)

    affected_files = impact.get("affected_files", [])
    affected_classes = impact.get("affected_classes", [])
    affected_functions = impact.get("affected_functions", [])

    return {
        "asset": asset,
        "bom_ref": mapping.get("bom_ref") or mapping.get("asset_id"),
        "migration_type": (
            migration.get("migration_type")
            or migration.get("pqc_analysis", {}).get("migration_type")
        ),
        "migration_strategy": strategy["strategy"] if strategy else None,
        "pqc_candidate": candidate if candidate else None,
        "pqc_family": family if family else None,
        "affected_files": affected_files,
        "affected_file_count": len(affected_files),
        "affected_classes": affected_classes,
        "affected_class_count": len(affected_classes),
        "affected_functions": affected_functions,
        "affected_function_count": len(affected_functions),
        "impact_level": impact.get("impact_level", "UNKNOWN"),
        "actions": [
            {
                "step": index,
                "action": action,
            }
            for index, action in enumerate(actions, start=1)
        ],
        "action_count": len(actions),
        "explanation": {
            "summary": (
                f"ECDAT generated {len(actions)} "
                f"migration action(s) for {asset}."
            ),
            "reasons": reasons,
        },
    }


def generate_all_migration_actions(
    mappings: List[Dict[str, Any]],
    impacts: List[Dict[str, Any]],
    migrations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    impact_map = {
        item.get("bom_ref"): item
        for item in impacts
        if isinstance(item, dict)
    }

    migration_map = {
        item.get("bom_ref"): item
        for item in migrations
        if isinstance(item, dict)
    }

    results = []

    for mapping in mappings:

        asset = mapping.get("asset")
        bom_ref = mapping.get("bom_ref") or mapping.get("asset_id")

        impact = impact_map.get(
            bom_ref,
            {
                "asset": asset,
                "bom_ref": bom_ref,
                "affected_files": [],
                "affected_classes": [],
                "affected_functions": [],
                "impact_level": "UNKNOWN",
            },
        )

        migration = migration_map.get(
            bom_ref,
            {
                "asset": asset,
                "bom_ref": bom_ref,
                "migration_type": None,
                "ranked_candidates": [],
            },
        )

        results.append(
            generate_migration_actions(
                mapping,
                impact,
                migration,
            )
        )

    return results


def summarize_migration_actions(
    actions: List[Dict[str, Any]],
) -> Dict[str, Any]:

    total_assets = len(actions)

    total_actions = sum(
        item.get("action_count", 0)
        for item in actions
    )

    action_distribution = {}
    strategy_distribution = {}

    for item in actions:

        migration_type = item.get(
            "migration_type"
        )

        if migration_type is None:
            migration_type = "none"

        action_distribution[migration_type] = (
            action_distribution.get(
                migration_type,
                0,
            )
            + 1
        )

        strategy = item.get("migration_strategy") or "none"

        strategy_distribution[strategy] = (
            strategy_distribution.get(strategy, 0) + 1
        )

    assets_with_candidates = sum(
        1
        for item in actions
        if item.get("pqc_candidate")
    )

    return {
        "total_assets": total_assets,
        "total_migration_actions": total_actions,
        "assets_with_pqc_candidates": assets_with_candidates,
        "migration_type_distribution": action_distribution,
        "migration_strategy_distribution": strategy_distribution,
    }

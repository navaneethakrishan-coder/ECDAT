from typing import Any, Dict, List


DIRECT_REPLACEMENT = "direct-replacement"
PQC_CANDIDATE = "pqc-candidate"
ARCHITECTURAL_MIGRATION = "architectural-migration"
NO_DIRECT_REPLACEMENT = "no-direct-pqc-replacement"
NOT_APPLICABLE = "not-applicable"


def _candidate(
    name: str,
    family: str,
    compatibility: str,
    reason: str,
    tradeoffs: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "family": family,
        "compatibility": compatibility,
        "reason": reason,
        "tradeoffs": tradeoffs or [],
    }


def map_asset_to_pqc(asset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a classified cryptographic asset to plausible PQC migration
    candidates.

    This function is deterministic and intentionally conservative.
    It does not claim that a candidate is production-compatible.
    """

    name = str(asset.get("name", ""))
    classification = asset.get("classification", {})

    category = classification.get("category")
    purposes = classification.get("purpose", [])
    quantum_status = classification.get("quantum_status")

    if isinstance(purposes, str):
        purposes = [purposes]

    purposes = [str(p).lower() for p in purposes]

    result = {
        "asset": name,
        "category": category,
        "purpose": purposes,
        "quantum_status": quantum_status,
        "migration_type": NOT_APPLICABLE,
        "pqc_applicable": False,
        "candidates": [],
        "reason": "",
        "confidence": "HIGH",
    }

    # ---------------------------------------------------------
    # Key agreement / key establishment
    # ---------------------------------------------------------

    if category == "asymmetric" and (
        "key-agreement" in purposes
        or "key-establishment" in purposes
    ):
        result["migration_type"] = PQC_CANDIDATE
        result["pqc_applicable"] = True
        result["candidates"] = [
            _candidate(
                "ML-KEM-512",
                "KEM",
                "HIGH",
                "ML-KEM is a standardized post-quantum key-encapsulation "
                "mechanism suitable for key establishment.",
                ["Lower security parameter than ML-KEM-768/1024."],
            ),
            _candidate(
                "ML-KEM-768",
                "KEM",
                "HIGH",
                "ML-KEM-768 provides a standardized post-quantum "
                "key-establishment mechanism and is a strong general "
                "candidate for migration planning.",
                ["Requires compatibility and performance validation."],
            ),
            _candidate(
                "ML-KEM-1024",
                "KEM",
                "HIGH",
                "ML-KEM-1024 is a standardized post-quantum KEM with "
                "a higher parameter set.",
                ["Higher computational and communication overhead "
                 "than lower parameter sets."],
            ),
        ]
        result["reason"] = (
            "The asset performs key agreement or key establishment, "
            "so a post-quantum KEM is a plausible migration family."
        )
        return result

    # ---------------------------------------------------------
    # Digital signatures
    # ---------------------------------------------------------

    if category == "asymmetric" and "digital-signature" in purposes:
        result["migration_type"] = PQC_CANDIDATE
        result["pqc_applicable"] = True

        result["candidates"] = [
            _candidate(
                "ML-DSA-44",
                "digital-signature",
                "HIGH",
                "ML-DSA is a standardized post-quantum digital-signature "
                "family and can be evaluated as a signature migration "
                "candidate.",
                ["Lower ML-DSA parameter set."],
            ),
            _candidate(
                "ML-DSA-65",
                "digital-signature",
                "HIGH",
                "ML-DSA-65 is a standardized post-quantum digital-signature "
                "candidate.",
                ["Requires application and interoperability testing."],
            ),
            _candidate(
                "ML-DSA-87",
                "digital-signature",
                "HIGH",
                "ML-DSA-87 is a standardized post-quantum digital-signature "
                "candidate with a higher parameter set.",
                ["Higher computational and signature-size overhead."],
            ),
            _candidate(
                "SLH-DSA",
                "digital-signature",
                "MEDIUM",
                "SLH-DSA provides a standardized post-quantum "
                "digital-signature alternative based on a different "
                "cryptographic construction.",
                ["Different performance and signature-size characteristics "
                 "require application-specific evaluation."],
            ),
        ]

        result["reason"] = (
            "The asset performs digital signatures, so standardized "
            "post-quantum signature algorithms are plausible migration "
            "candidates."
        )
        return result

    # ---------------------------------------------------------
    # Generic asymmetric / public-key cryptography
    # ---------------------------------------------------------

    if category == "asymmetric":
        result["migration_type"] = ARCHITECTURAL_MIGRATION
        result["pqc_applicable"] = True

        result["candidates"] = [
            _candidate(
                "ML-KEM-768",
                "KEM",
                "MEDIUM",
                "ML-KEM may be relevant if the asymmetric usage is "
                "actually key establishment or key agreement.",
                ["Exact usage must be confirmed from source evidence."],
            ),
            _candidate(
                "ML-DSA-65",
                "digital-signature",
                "MEDIUM",
                "ML-DSA may be relevant if the asymmetric usage is "
                "actually digital signing.",
                ["Exact cryptographic purpose must be confirmed."],
            ),
        ]

        result["reason"] = (
            "The asset is asymmetric but its recorded purpose does not "
            "identify a sufficiently specific migration function. "
            "PQC selection requires source-usage validation."
        )
        result["confidence"] = "MEDIUM"
        return result

    # ---------------------------------------------------------
    # Symmetric encryption
    # ---------------------------------------------------------

    if category == "symmetric" and "encryption" in purposes:
        result["migration_type"] = NO_DIRECT_REPLACEMENT
        result["pqc_applicable"] = False
        result["reason"] = (
            "Symmetric encryption does not have a direct ML-KEM or "
            "ML-DSA replacement. PQC migration normally focuses on "
            "quantum-sensitive public-key operations, while symmetric "
            "algorithm strength and key sizes should be evaluated separately."
        )
        return result

    # ---------------------------------------------------------
    # Hash functions
    # ---------------------------------------------------------

    if category == "hash" or "hash" in purposes:
        result["migration_type"] = NO_DIRECT_REPLACEMENT
        result["pqc_applicable"] = False
        result["reason"] = (
            "Hash functions do not have a direct ML-KEM or ML-DSA "
            "replacement. Quantum impact should instead be evaluated "
            "according to the hash's role, strength and security margin."
        )
        return result

    # ---------------------------------------------------------
    # MAC
    # ---------------------------------------------------------

    if category == "mac":
        result["migration_type"] = NO_DIRECT_REPLACEMENT
        result["pqc_applicable"] = False
        result["reason"] = (
            "Message-authentication codes do not have a direct PQC "
            "algorithm replacement in the ML-KEM/ML-DSA families."
        )
        return result

    # ---------------------------------------------------------
    # Protocol
    # ---------------------------------------------------------

    if category == "protocol":
        result["migration_type"] = ARCHITECTURAL_MIGRATION
        result["pqc_applicable"] = False
        result["reason"] = (
            "Protocols such as TLS are not themselves replaced by a "
            "single PQC algorithm. Migration is architectural and may "
            "involve selecting PQC or hybrid cryptographic mechanisms "
            "within the protocol."
        )
        result["confidence"] = "MEDIUM"
        return result

    # ---------------------------------------------------------
    # Key material
    # ---------------------------------------------------------

    if category == "crypto-material":
        result["migration_type"] = ARCHITECTURAL_MIGRATION
        result["pqc_applicable"] = False
        result["reason"] = (
            "Cryptographic key material is not itself a PQC algorithm. "
            "Migration depends on the algorithm and purpose associated "
            "with the key."
        )
        result["confidence"] = "HIGH"
        return result

    # ---------------------------------------------------------
    # Cryptographic components / formats / KDF
    # ---------------------------------------------------------

    if category in {
        "cryptographic-component",
        "cryptographic-format",
        "key-derivation",
    }:
        result["migration_type"] = NO_DIRECT_REPLACEMENT
        result["pqc_applicable"] = False
        result["reason"] = (
            "This cryptographic component does not have a direct "
            "ML-KEM or ML-DSA replacement. Its migration impact should "
            "be evaluated through the surrounding cryptographic workflow."
        )
        return result

    # ---------------------------------------------------------
    # Unknown category
    # ---------------------------------------------------------

    result["migration_type"] = NOT_APPLICABLE
    result["reason"] = (
        "No sufficiently specific PQC migration rule was identified "
        "for this asset."
    )
    result["confidence"] = "LOW"

    return result


def map_assets_to_pqc(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Map a list of classified assets to PQC migration candidates.
    """

    return [
        map_asset_to_pqc(asset)
        for asset in assets
    ]
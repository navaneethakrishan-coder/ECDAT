from typing import Any, Dict, List

from services.purpose_resolver import classify_context


def _normalize_asset_name(name: str) -> str:
    return str(name or "").strip().lower()


def _normalize_location(location: str) -> str:
    return str(location or "").strip().replace("\\", "/")


def _get_evidence_locations(
    asset: Dict[str, Any],
) -> List[Dict[str, Any]]:
    evidence = asset.get("evidence", {})

    if not isinstance(evidence, dict):
        return []

    locations = evidence.get("locations", [])

    if not isinstance(locations, list):
        return []

    return [
        location
        for location in locations
        if isinstance(location, dict)
    ]


def _infer_usage(
    asset: Dict[str, Any],
    evidence: Dict[str, Any],
) -> str:
    """
    Infer this ONE occurrence's usage label.

    Delegates the actual API-context classification to
    services/purpose_resolver.classify_context() -- the same function
    the earlier, finding-level purpose-resolution stage
    (classify_cbom.py) uses -- so this per-occurrence label and the
    finding-level resolved purpose can never independently drift apart
    by keeping two separate keyword lists. This function only adds the
    fallback chain appropriate for a single occurrence: the context
    for *this* occurrence, then the finding's already-resolved
    purpose, then its CBOM primitive, then a generic label.
    """

    name = _normalize_asset_name(
        asset.get("name", "")
    )

    primitive = str(
        asset.get("primitive", "")
    ).lower()

    classification = asset.get(
        "classification",
        {},
    )

    if not isinstance(classification, dict):
        classification = {}

    purpose = classification.get(
        "purpose",
        [],
    )

    if isinstance(purpose, str):
        purpose = [purpose]

    purpose = [
        str(item).lower()
        for item in purpose
    ]

    context_label = classify_context(evidence.get("context"))

    if context_label:
        return context_label

    if "key-agreement" in purpose:
        return "key-agreement"

    if "digital-signature" in purpose:
        return "digital-signature"

    if "encryption" in purpose:
        return "encryption"

    if "message-authentication" in purpose:
        return "message-authentication"

    if "hash" in purpose:
        return "hash"

    if primitive in {
        "key-agree",
        "key-agreement",
    }:
        return "key-agreement"

    if name:
        return "cryptographic-usage"

    return "unknown"


def map_asset_source_usage(
    asset: Dict[str, Any],
) -> Dict[str, Any]:

    asset_id = asset.get("bom_ref") or asset.get("id")

    name = asset.get(
        "name",
        asset.get("asset", "UNKNOWN"),
    )

    asset_type = asset.get(
        "asset_type",
        asset.get("type"),
    )

    classification = asset.get(
        "classification",
        {},
    )

    if not isinstance(classification, dict):
        classification = {}

    category = classification.get(
        "category"
    )

    purpose = classification.get(
        "purpose",
        [],
    )

    quantum_status = classification.get(
        "quantum_status"
    )

    locations = _get_evidence_locations(
        asset
    )

    source_usage = []

    for evidence in locations:

        location = _normalize_location(
            evidence.get("location", "")
        )

        line = evidence.get("line")

        offset = evidence.get("offset")

        context = evidence.get(
            "context",
            "",
        )

        usage = _infer_usage(
            asset,
            evidence,
        )

        source_usage.append(
            {
                "file": location,
                "line": line,
                "offset": offset,
                "usage": usage,
                "context": context,
            }
        )

    affected_files = sorted(
        {
            item["file"]
            for item in source_usage
            if item.get("file")
        }
    )

    evidence_count = len(source_usage)

    if evidence_count >= 10:
        migration_surface = "CRITICAL"

    elif evidence_count >= 5:
        migration_surface = "HIGH"

    elif evidence_count >= 2:
        migration_surface = "MEDIUM"

    elif evidence_count == 1:
        migration_surface = "LOW"

    else:
        migration_surface = "UNKNOWN"

    return {
        "asset": name,
        "asset_id": asset_id,
        "bom_ref": asset_id,
        "asset_type": asset_type,
        "classification": {
            "category": category,
            "purpose": purpose,
            "quantum_status": quantum_status,
        },
        "source_usage": source_usage,
        "evidence_count": evidence_count,
        "affected_files": affected_files,
        "affected_file_count": len(
            affected_files
        ),
        "migration_surface": migration_surface,
    }


def map_assets_to_source(
    assets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    return [
        map_asset_source_usage(asset)
        for asset in assets
    ]


def summarize_source_mapping(
    mappings: List[Dict[str, Any]],
) -> Dict[str, Any]:

    total_assets = len(mappings)

    assets_with_source = sum(
        1
        for mapping in mappings
        if mapping.get(
            "evidence_count",
            0,
        ) > 0
    )

    total_evidence = sum(
        mapping.get(
            "evidence_count",
            0,
        )
        for mapping in mappings
    )

    total_files = len(
        {
            file
            for mapping in mappings
            for file in mapping.get(
                "affected_files",
                [],
            )
        }
    )

    surface_distribution = {}

    for mapping in mappings:

        surface = mapping.get(
            "migration_surface",
            "UNKNOWN",
        )

        surface_distribution[surface] = (
            surface_distribution.get(
                surface,
                0,
            )
            + 1
        )

    return {
        "total_assets": total_assets,
        "assets_with_source_evidence": (
            assets_with_source
        ),
        "assets_without_source_evidence": (
            total_assets
            - assets_with_source
        ),
        "total_evidence_locations": (
            total_evidence
        ),
        "unique_source_files": total_files,
        "migration_surface_distribution": (
            surface_distribution
        ),
    }

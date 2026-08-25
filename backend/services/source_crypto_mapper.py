from typing import Any, Dict, List


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

    context = str(
        evidence.get("context", "")
    ).lower()

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

    if "keyagreement" in context:
        return "key-agreement"

    if "signature" in context:
        return "digital-signature"

    if "cipher" in context:
        return "encryption"

    if "hash" in context:
        return "hash"

    if "key-agreement" in purpose:
        return "key-agreement"

    if "digital-signature" in purpose:
        return "digital-signature"

    if "encryption" in purpose:
        return "encryption"

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

    asset_id = asset.get("id")

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
from typing import Any, Dict, List, Optional
import re


def _normalize_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/")


def _extract_file_name(path: str) -> str:
    normalized = _normalize_path(path)

    if not normalized:
        return ""

    return normalized.rsplit("/", 1)[-1]


def _extract_class_name(
    file_name: str,
    context: str,
) -> Optional[str]:
    """
    Best-effort extraction of a Java class/interface name
    from source evidence context.

    This does not claim source parsing is complete.
    """

    context = str(context or "")

    patterns = [
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, context)

        if match:
            return match.group(1)

    match = re.search(
        r"([A-Za-z_][A-Za-z0-9_]*)\.java$",
        file_name,
    )

    if match:
        return match.group(1)

    return None


def _extract_function_name(
    context: str,
) -> Optional[str]:
    """
    Best-effort extraction of a function/method name.

    Examples:
        KeyAgreement#getInstance(...)
        Cipher.getInstance(...)
    """

    context = str(context or "")

    patterns = [
        r"#([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"\.([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            context,
        )

        if match:
            return match.group(1)

    return None


def _classify_impact(
    usage: str,
    purpose: List[str],
) -> str:
    usage = str(
        usage or ""
    ).lower()

    normalized_purpose = [
        str(item).lower()
        for item in purpose
    ]

    if usage in {
        "key-agreement",
        "digital-signature",
        "encryption",
    }:
        return "HIGH"

    if (
        "key-agreement" in normalized_purpose
        or "digital-signature" in normalized_purpose
        or "encryption" in normalized_purpose
    ):
        return "HIGH"

    if usage in {
        "hash",
        "message-authentication",
    }:
        return "MEDIUM"

    if usage:
        return "LOW"

    return "UNKNOWN"


def analyze_source_usage(
    mapping: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze one source-to-crypto mapping produced by
    source_crypto_mapper.py.

    The result identifies:
      - affected files
      - source locations
      - classes
      - functions/methods
      - impact level
    """

    asset = mapping.get(
        "asset",
        "UNKNOWN",
    )

    classification = mapping.get(
        "classification",
        {},
    )

    if not isinstance(
        classification,
        dict,
    ):
        classification = {}

    purpose = classification.get(
        "purpose",
        [],
    )

    if isinstance(purpose, str):
        purpose = [purpose]

    source_usage = mapping.get(
        "source_usage",
        [],
    )

    if not isinstance(
        source_usage,
        list,
    ):
        source_usage = []

    affected_files = set()
    affected_classes = set()
    affected_functions = set()

    locations = []

    impact_levels = []

    for usage in source_usage:

        if not isinstance(
            usage,
            dict,
        ):
            continue

        file_path = _normalize_path(
            usage.get(
                "file",
                "",
            )
        )

        line = usage.get(
            "line"
        )

        offset = usage.get(
            "offset"
        )

        context = usage.get(
            "context",
            "",
        )

        usage_type = usage.get(
            "usage",
            "unknown",
        )

        file_name = _extract_file_name(
            file_path
        )

        class_name = _extract_class_name(
            file_name,
            context,
        )

        function_name = _extract_function_name(
            context
        )

        impact = _classify_impact(
            usage_type,
            purpose,
        )

        if file_path:
            affected_files.add(
                file_path
            )

        if class_name:
            affected_classes.add(
                class_name
            )

        if function_name:
            affected_functions.add(
                function_name
            )

        impact_levels.append(
            impact
        )

        locations.append(
            {
                "file": file_path,
                "file_name": file_name,
                "line": line,
                "offset": offset,
                "usage": usage_type,
                "context": context,
                "class": class_name,
                "function": function_name,
                "impact": impact,
            }
        )

    severity_order = {
        "UNKNOWN": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    if impact_levels:
        impact_level = max(
            impact_levels,
            key=lambda item: severity_order.get(
                item,
                0,
            ),
        )
    else:
        impact_level = "UNKNOWN"

    return {
        "asset": asset,
        "bom_ref": mapping.get("bom_ref") or mapping.get("asset_id"),
        "affected_file_count": len(
            affected_files
        ),
        "affected_files": sorted(
            affected_files
        ),
        "affected_class_count": len(
            affected_classes
        ),
        "affected_classes": sorted(
            affected_classes
        ),
        "affected_function_count": len(
            affected_functions
        ),
        "affected_functions": sorted(
            affected_functions
        ),
        "source_location_count": len(
            locations
        ),
        "impact_level": impact_level,
        "locations": locations,
    }


def analyze_all_source_usage(
    mappings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Analyze source impact for all mapped assets.
    """

    return [
        analyze_source_usage(mapping)
        for mapping in mappings
    ]


def summarize_source_impact(
    analyses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate Stage 9.2 summary statistics.
    """

    total_assets = len(
        analyses
    )

    assets_with_files = sum(
        1
        for analysis in analyses
        if analysis.get(
            "affected_file_count",
            0,
        ) > 0
    )

    assets_with_functions = sum(
        1
        for analysis in analyses
        if analysis.get(
            "affected_function_count",
            0,
        ) > 0
    )

    unique_files = {
        file_path
        for analysis in analyses
        for file_path in analysis.get(
            "affected_files",
            [],
        )
    }

    unique_classes = {
        class_name
        for analysis in analyses
        for class_name in analysis.get(
            "affected_classes",
            [],
        )
    }

    unique_functions = {
        function_name
        for analysis in analyses
        for function_name in analysis.get(
            "affected_functions",
            [],
        )
    }

    impact_distribution = {}

    for analysis in analyses:

        impact = analysis.get(
            "impact_level",
            "UNKNOWN",
        )

        impact_distribution[impact] = (
            impact_distribution.get(
                impact,
                0,
            )
            + 1
        )

    return {
        "total_assets": total_assets,
        "assets_with_affected_files": (
            assets_with_files
        ),
        "assets_with_detected_functions": (
            assets_with_functions
        ),
        "unique_affected_files": len(
            unique_files
        ),
        "unique_affected_classes": len(
            unique_classes
        ),
        "unique_affected_functions": len(
            unique_functions
        ),
        "impact_distribution": (
            impact_distribution
        ),
    }

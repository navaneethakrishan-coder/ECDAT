def calculate_evidence_quality(asset):
    """
    Calculate evidence quality from CBOM evidence.

    Maximum score: 100
    """

    occurrences = asset.get(
        "occurrences",
        []
    )

    if not occurrences:
        return {
            "score": 0,
            "quality": "LOW",
            "evidence_count": 0,
            "breakdown": {
                "source_location": 0,
                "line_number": 0,
                "cryptographic_context": 0,
                "multiple_occurrences": 0
            }
        }

    source_score = 0
    line_score = 0
    context_score = 0
    multiple_occurrence_score = 0

    # -----------------------------------------
    # Source location
    # -----------------------------------------

    if any(
        occurrence.get("location")
        for occurrence in occurrences
    ):
        source_score = 40

    # -----------------------------------------
    # Line number
    # -----------------------------------------

    if any(
        occurrence.get("line") is not None
        for occurrence in occurrences
    ):
        line_score = 20

    # -----------------------------------------
    # Cryptographic context
    # -----------------------------------------

    if any(
        occurrence.get("additionalContext")
        or occurrence.get("context")
        for occurrence in occurrences
    ):
        context_score = 25

    # -----------------------------------------
    # Multiple occurrences
    # -----------------------------------------

    if len(occurrences) > 1:
        multiple_occurrence_score = 15

    score = (
        source_score
        + line_score
        + context_score
        + multiple_occurrence_score
    )

    score = min(score, 100)

    if score >= 80:
        quality = "HIGH"

    elif score >= 50:
        quality = "MEDIUM"

    else:
        quality = "LOW"

    return {
        "score": score,
        "quality": quality,
        "evidence_count": len(occurrences),
        "breakdown": {
            "source_location": source_score,
            "line_number": line_score,
            "cryptographic_context": context_score,
            "multiple_occurrences": multiple_occurrence_score
        }
    }


def extract_evidence(asset):
    """
    Extract normalized CBOM evidence locations.
    """

    occurrences = asset.get(
        "occurrences",
        []
    )

    evidence = []

    for occurrence in occurrences:

        evidence.append({
            "location": occurrence.get(
                "location"
            ),

            "line": occurrence.get(
                "line"
            ),

            "offset": occurrence.get(
                "offset"
            ),

            "context": (
                occurrence.get("additionalContext")
                or occurrence.get("context")
            )
        })

    return {
        "evidence_count": len(evidence),
        "locations": evidence
    }
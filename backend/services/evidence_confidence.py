def calculate_evidence_confidence(asset):
    """
    Calculate confidence in the cryptographic asset assessment
    based on the quality and completeness of CBOM evidence.

    Maximum confidence score: 100
    """

    occurrences = asset.get("occurrences", [])

    if not occurrences:
        return {
            "score": 0,
            "confidence": "LOW",
            "reasons": [
                "No CBOM evidence occurrences were found."
            ]
        }

    score = 0
    reasons = []

    # -----------------------------------------
    # Source location
    # -----------------------------------------

    has_location = any(
        occurrence.get("location")
        for occurrence in occurrences
    )

    if has_location:
        score += 40
        reasons.append(
            "Source-code location is available."
        )

    # -----------------------------------------
    # Line number
    # -----------------------------------------

    has_line = any(
        occurrence.get("line") is not None
        for occurrence in occurrences
    )

    if has_line:
        score += 20
        reasons.append(
            "Source line information is available."
        )

    # -----------------------------------------
    # Cryptographic context
    # -----------------------------------------

    has_context = any(
        occurrence.get("additionalContext")
        or occurrence.get("context")
        for occurrence in occurrences
    )

    if has_context:
        score += 25
        reasons.append(
            "Cryptographic API or usage context is available."
        )

    # -----------------------------------------
    # Multiple occurrences
    # -----------------------------------------

    if len(occurrences) > 1:
        score += 15
        reasons.append(
            f"{len(occurrences)} evidence occurrences "
            "were identified."
        )

    score = min(score, 100)

    # -----------------------------------------
    # Confidence level
    # -----------------------------------------

    if score >= 80:
        confidence = "HIGH"

    elif score >= 50:
        confidence = "MEDIUM"

    else:
        confidence = "LOW"

    return {
        "score": score,
        "confidence": confidence,
        "evidence_count": len(occurrences),
        "reasons": reasons
    }
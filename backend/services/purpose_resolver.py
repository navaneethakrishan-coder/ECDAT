"""
Resolves a cryptographic finding's *purpose* (encryption, digital
signature, key agreement, ...) from repository-specific evidence,
instead of from the algorithm's name/family alone.

WHY THIS EXISTS: services/crypto_classifier.py + knowledge/
crypto_knowledge.py answer "what algorithm family is this, and is
that family generally quantum-vulnerable?" -- a fact about the
algorithm. They do NOT answer "what is *this specific finding* in
*this specific repository* actually being used for?" -- a fact about
the finding. Before this module existed, every downstream stage
(PQC mapping, PQC ranking, migration recommendation, migration
complexity) read `classification["purpose"]`, which was always the
algorithm-family's generic purpose list -- e.g. every RSA-named
finding got `["encryption", "digital-signature"]` regardless of
whether the actual CBOM/source evidence showed it being used as a
signature key, an encryption key, or something else entirely. That is
what let RSA-OAEP (an encryption scheme) receive the same
signature-shaped PQC guidance as an RSA finding used for signing.

EVIDENCE PRIORITY (deterministic, in this order):

  1. Explicit CBOM metadata -- the `primitive` field CBOMKit already
     records (CycloneDX's `cryptoProperties.algorithmProperties.
     primitive`, e.g. "signature", "mac", "hash", "kdf", "key-agree",
     a cipher family, or the generic "pke" bucket that covers RSA/DH
     regardless of sub-usage -- see AMBIGUOUS below). Decisive when
     the primitive maps to exactly one purpose.
  2. Source evidence -- each occurrence's CBOM-recorded `context`
     (the actual API call CBOMKit resolved evidence against, e.g.
     "javax.crypto.Cipher#getInstance(...)" or "...Signature#..."),
     classified by classify_context() below. Used when (1) is absent
     or ambiguous (e.g. primitive == "pke", which this module never
     treats as decisive on its own -- see AMBIGUOUS_PRIMITIVES).
  3. Algorithm-family fallback -- crypto_classifier.py's own
     family-based `purpose` list. Used only when neither (1) nor (2)
     say anything specific, and always recorded at LOW confidence
     with evidence_source="algorithm-family-fallback" so it is never
     confused with real repository evidence.

If (1) and (2) disagree, or if multiple occurrences of the same
finding call APIs for genuinely different purposes, this module does
not guess -- it unions the conflicting signals, sets
needs_review=True, and records evidence_source="conflicting" so the
disagreement is visible rather than silently resolved one way.

This module is also the single place API-call-context classification
happens; services/source_crypto_mapper.py's per-occurrence usage
inference (used for migration-action wording) delegates to
classify_context() here instead of keeping its own separate keyword
list, so the two stages cannot silently drift apart.
"""

from typing import Any, Dict, List, Optional


# ----------------------------------------------------------------
# Tier 1: explicit CBOM primitive evidence.
#
# CycloneDX's algorithmProperties.primitive vocabulary. Mapped to a
# purpose ONLY where that primitive is inherently single-purpose.
# "pke" (public-key encryption/decryption OR signing OR key transport,
# depending on the scanner) is deliberately excluded here: observed
# real CBOM data shows CBOMKit assigns "pke" to RSA and DH alike
# regardless of which of those roles the code actually uses, so
# treating "pke" as decisively "encryption" would be exactly the kind
# of name/family-shaped assumption this module exists to avoid.
# ----------------------------------------------------------------

DECISIVE_PRIMITIVE_PURPOSE: Dict[str, List[str]] = {
    "signature": ["digital-signature"],
    "mac": ["message-authentication"],
    "hash": ["hash"],
    "xof": ["hash"],
    "kdf": ["key-derivation"],
    "block-cipher": ["encryption"],
    "stream-cipher": ["encryption"],
    "authenticated-encryption": ["encryption"],
    "key-agree": ["key-agreement"],
    "key-agreement": ["key-agreement"],
    "kem": ["key-agreement"],
    "drbg": ["random-generation"],
}

# Primitives that exist but are known not to single-handedly determine
# purpose -- kept as an explicit set (rather than "anything not in the
# map above") so the ambiguity is a documented, deliberate decision.
AMBIGUOUS_PRIMITIVES = {"pke", "combiner", "other", "unknown", ""}


# ----------------------------------------------------------------
# Tier 2: source/API-context evidence.
#
# Classifies one occurrence's CBOM-recorded `context` string (the
# actual API call CBOMKit found evidence against) into a purpose
# label. Deliberately narrow: only API families that are exclusively
# used for one cryptographic purpose (a Cipher is only ever used to
# encrypt/decrypt; a Signature object is only ever used to sign/
# verify) are matched. Generic key-material APIs (KeyFactory,
# KeyPairGenerator, PublicNumbers/PrivateNumbers, generate_private_key)
# are intentionally NOT matched here -- they are used to construct
# keys for *any* purpose, so treating them as decisive would be
# exactly the kind of invented certainty this module must avoid.
# ----------------------------------------------------------------

_CONTEXT_PURPOSE_RULES = (
    (("keyagreement", "key-agreement"), "key-agreement"),
    (("signature",), "digital-signature"),
    (("cipher",), "encryption"),
    (("hmac", "mac#", "mac.", " mac(", "/mac"), "message-authentication"),
    (("messagedigest", "digest", "hash"), "hash"),
)


def classify_context(context: Optional[str]) -> Optional[str]:
    """
    Classify one occurrence's API-call context into a purpose label,
    or None if it isn't decisive (e.g. generic key-material APIs like
    KeyFactory/PublicNumbers/generate_private_key).

    Only context strings that look like an actual API/method
    reference (contain "#" or "(", e.g.
    "javax.crypto.Cipher#getInstance(...)") are treated as decisive.
    A bare construction-name mention with no call syntax (e.g. CBOMKit
    tagging a hash's own occurrence context as plain "HMAC" or "HKDF"
    because that hash is used as a component *inside* an HMAC/HKDF
    construction elsewhere) says something about the surrounding
    construction, not necessarily about this occurrence's own
    purpose -- a hash being embedded in a MAC/KDF is normal and
    expected, not evidence that the hash itself has a different
    purpose. Verified against real CBOM data: this is exactly what
    distinguishes a real conflict (a decisive primitive contradicted
    by an actual differing API call) from a false one (a hash whose
    only "conflicting" evidence was being named inside its own
    caller's construction).
    """

    text = str(context or "").lower()

    if not text:
        return None

    if "#" not in text and "(" not in text:
        return None

    for keywords, label in _CONTEXT_PURPOSE_RULES:
        if any(keyword in text for keyword in keywords):
            return label

    return None


def _normalize_primitive(primitive: Any) -> str:
    return str(primitive or "").strip().lower()


def _context_labels(occurrences: List[Dict[str, Any]]) -> List[str]:
    labels: List[str] = []

    for occurrence in occurrences or []:
        if not isinstance(occurrence, dict):
            continue

        label = classify_context(occurrence.get("context"))

        if label and label not in labels:
            labels.append(label)

    return labels


def _source_contexts(occurrences: List[Dict[str, Any]]) -> List[str]:
    contexts = []

    for occurrence in occurrences or []:
        if not isinstance(occurrence, dict):
            continue

        context = occurrence.get("context")

        if context and context not in contexts:
            contexts.append(str(context))

    return contexts


def _result(
    purpose: List[str],
    usage: Optional[str],
    confidence: str,
    evidence_source: str,
    reason: str,
    needs_review: bool,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "purpose": purpose,
        "usage": usage,
        "confidence": confidence,
        "evidence_source": evidence_source,
        "evidence_reason": reason,
        "needs_review": needs_review,
        "evidence": evidence,
    }


def resolve_purpose(asset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve one classified asset's cryptographic purpose from
    repository evidence, following the tier-1/2/3 priority described
    in this module's docstring.

    `asset` is expected to already carry:
      - "primitive": the raw CBOM primitive string (may be missing)
      - "occurrences": the asset's CBOM evidence occurrences
      - "classification": {"category", "purpose", ...} as already
        produced by services/crypto_classifier.py (the family-based
        fallback answer)

    Returns a dict with the resolved "purpose" (a list, so every
    existing consumer of classification["purpose"] keeps working
    unchanged) plus new "usage"/"confidence"/"evidence_source"/
    "evidence_reason"/"needs_review"/"evidence" fields.
    """

    classification = asset.get("classification") or {}
    family_purpose = list(classification.get("purpose") or [])
    family_category = classification.get("category")

    primitive = _normalize_primitive(asset.get("primitive"))
    occurrences = asset.get("occurrences") or []

    context_labels = _context_labels(occurrences)

    evidence = {
        "cbom_primitive": primitive or None,
        "source_contexts": _source_contexts(occurrences),
        "family_fallback_purpose": family_purpose,
    }

    # ------------------------------------------------------------
    # Tier 1: decisive CBOM primitive evidence.
    # ------------------------------------------------------------

    primitive_purposes = (
        DECISIVE_PRIMITIVE_PURPOSE.get(primitive)
        if primitive not in AMBIGUOUS_PRIMITIVES
        else None
    )

    if primitive_purposes:

        conflicting = [
            label for label in context_labels if label not in primitive_purposes
        ]

        if conflicting:
            merged = sorted(set(primitive_purposes) | set(context_labels))

            return _result(
                purpose=merged,
                usage=None,
                confidence="LOW",
                evidence_source="conflicting",
                reason=(
                    f"The CBOM records this finding's primitive as "
                    f"'{primitive}' (implying {primitive_purposes}), but "
                    f"its source usage indicates {conflicting} -- flagged "
                    "for manual review rather than resolved automatically."
                ),
                needs_review=True,
                evidence=evidence,
            )

        return _result(
            purpose=primitive_purposes,
            usage=primitive_purposes[0],
            confidence="HIGH",
            evidence_source="cbom-primitive",
            reason=(
                f"The CBOM explicitly records this finding's cryptographic "
                f"primitive as '{primitive}'."
            ),
            needs_review=False,
            evidence=evidence,
        )

    # ------------------------------------------------------------
    # Tier 2: source/API-context evidence (primitive absent or
    # ambiguous, e.g. the generic "pke" bucket).
    # ------------------------------------------------------------

    if len(context_labels) == 1:
        label = context_labels[0]

        return _result(
            purpose=[label],
            usage=label,
            confidence="MEDIUM",
            evidence_source="source-context",
            reason=(
                f"Source occurrence(s) call a {label}-specific API, which "
                "disambiguates this finding's purpose where the CBOM "
                f"primitive ('{primitive or 'unspecified'}') alone does not."
            ),
            needs_review=False,
            evidence=evidence,
        )

    if len(context_labels) > 1:
        return _result(
            purpose=sorted(context_labels),
            usage=None,
            confidence="LOW",
            evidence_source="conflicting",
            reason=(
                f"Different occurrences of this finding call APIs "
                f"associated with different purposes {sorted(context_labels)} "
                "-- flagged for manual review rather than resolved "
                "automatically."
            ),
            needs_review=True,
            evidence=evidence,
        )

    # ------------------------------------------------------------
    # Tier 3: algorithm-family fallback -- only reached when neither
    # explicit CBOM metadata nor source context says anything
    # specific about this particular finding.
    # ------------------------------------------------------------

    if family_purpose:
        return _result(
            purpose=family_purpose,
            usage=family_purpose[0] if len(family_purpose) == 1 else None,
            confidence="LOW",
            evidence_source="algorithm-family-fallback",
            reason=(
                f"Neither the CBOM primitive ('{primitive or 'unspecified'}') "
                "nor the source occurrence context identifies a specific "
                f"usage for this finding, so the '{family_category}' "
                "algorithm family's general-purpose knowledge is used as a "
                "documented, lower-confidence fallback -- not repository "
                "evidence."
            ),
            needs_review=False,
            evidence=evidence,
        )

    return _result(
        purpose=[],
        usage=None,
        confidence="LOW",
        evidence_source="insufficient-evidence",
        reason=(
            "No CBOM primitive, source-context, or algorithm-family "
            "evidence was available to determine this finding's "
            "cryptographic purpose."
        ),
        needs_review=True,
        evidence=evidence,
    )

"""
Classifies a normalized ECDAT crypto asset by cryptographic role.

Classification order (most specific / most reliable evidence first):

  1. Asset-type-driven material classification. CBOMKit's own
     `asset_type: "related-crypto-material"` plus a name prefix
     (public-key@/private-key@/secret-key@/key@) is stronger, more
     direct evidence than a name substring, so it is checked before
     any name-based family matching -- a key-material record should
     never be mis-routed into an algorithm family just because CBOMKit
     happened to embed an algorithm-like token in its generated name.
  2. Family/alias/pattern-based classification, delegated to
     knowledge/crypto_knowledge.py's algorithm-family registry. See
     that module's docstring for why classification is organized by
     family (with aliases and patterns) instead of one if/elif branch
     per exact algorithm name -- that is what makes this
     repository-agnostic and extensible to algorithms not seen in any
     one analyzed project.
  3. Unknown. If neither of the above can classify the asset from the
     evidence actually present in the CBOM, it is recorded as unknown
     rather than guessed -- ECDAT's risk/PQC pipeline already treats
     "unknown" as "quantum_status: unknown" -> zero quantum-risk
     contribution, which is the honest outcome when there truly is no
     matching evidence, not when a rule was merely missing.
"""

from knowledge.crypto_knowledge import resolve_family_classification


_MATERIAL_NAME_PREFIXES = (
    ("public-key@", "public-key"),
    ("private-key@", "private-key"),
    ("secret-key@", "secret-key"),
    ("key@", "key"),
)


def _classify_related_crypto_material(name, asset_type):
    """
    Classify CBOM key/certificate material by asset_type + name
    prefix, independent of algorithm-name matching. Returns None if
    this asset is not CBOMKit-flagged crypto material at all.
    """

    if asset_type != "related-crypto-material":
        return None

    material_type = "cryptographic-material"

    for prefix, label in _MATERIAL_NAME_PREFIXES:
        if name.startswith(prefix):
            material_type = label
            break

    return {
        "category": "crypto-material",
        "purpose": [material_type],
        "quantum_status": "contextual",
        "risk_reason": (
            "The cryptographic material must be associated with its "
            "governing algorithm before quantum risk can be determined."
        ),
    }


def _unknown_classification():
    return {
        "category": "unknown",
        "purpose": [],
        "quantum_status": "unknown",
        "risk_reason": (
            "No classification rule currently matches this asset from "
            "the evidence available in the CBOM."
        ),
    }


def classify_asset(asset):
    """
    Classify a normalized ECDAT crypto asset.

    Never fabricates a classification: an asset that doesn't match any
    known material pattern or algorithm family is recorded as
    category="unknown" rather than assigned a guessed role.
    """

    name = str(asset.get("name") or "")
    asset_type = asset.get("asset_type")

    material_classification = _classify_related_crypto_material(name, asset_type)

    if material_classification is not None:
        return {**asset, "classification": material_classification}

    family_classification = resolve_family_classification(name)

    if family_classification is not None:
        return {**asset, "classification": family_classification}

    return {**asset, "classification": _unknown_classification()}

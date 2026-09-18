"""CBOM validation and normalization.

Between a scanner and the ECDAT pipeline, the CBOM is checked so the
pipeline only ever runs on a document it can actually read, and so a bad
scan fails with a specific reason instead of producing an empty dashboard.

Normalization is deliberately minimal: it only guarantees the container
arrays the pipeline reads exist. It never edits, invents, merges or drops a
component, a bom-ref or a dependency -- every finding stays exactly as the
scanner reported it.
"""

import json
from collections import Counter


CRYPTO_PROPERTY_KEY = "cryptoProperties"


def validate_cbom(cbom) -> dict:
    """Returns {"ok", "errors", "warnings", "stats"} for a CycloneDX CBOM."""
    errors = []
    warnings = []

    if not isinstance(cbom, dict):
        return {
            "ok": False,
            "errors": [{"code": "not-an-object", "message": "The CBOM is not a JSON object."}],
            "warnings": [],
            "stats": {},
        }

    bom_format = cbom.get("bomFormat")
    if bom_format is None:
        warnings.append({"code": "missing-bom-format", "message": "CBOM has no bomFormat field."})
    elif bom_format != "CycloneDX":
        errors.append(
            {"code": "unsupported-bom-format", "message": f"Unsupported bomFormat '{bom_format}' (expected CycloneDX)."}
        )

    if not cbom.get("specVersion"):
        warnings.append({"code": "missing-spec-version", "message": "CBOM has no specVersion field."})

    components = cbom.get("components")
    if components is None:
        errors.append({"code": "missing-components", "message": "CBOM has no components array."})
        components = []
    elif not isinstance(components, list):
        errors.append({"code": "invalid-components", "message": "CBOM components is not an array."})
        components = []

    refs = []
    crypto_refs = set()
    missing_ref = 0
    crypto_components = 0
    asset_types = Counter()

    for component in components:
        if not isinstance(component, dict):
            errors.append({"code": "invalid-component", "message": "A component entry is not an object."})
            continue
        ref = component.get("bom-ref")
        if ref:
            refs.append(ref)
        else:
            missing_ref += 1
        crypto = component.get(CRYPTO_PROPERTY_KEY)
        if isinstance(crypto, dict):
            crypto_components += 1
            if ref:
                crypto_refs.add(ref)
            asset_types[crypto.get("assetType") or "unknown"] += 1

    if missing_ref:
        # bom_ref is ECDAT's only finding identity; a component without one
        # cannot be tracked through the pipeline.
        errors.append(
            {"code": "missing-bom-ref", "message": f"{missing_ref} component(s) have no bom-ref."}
        )

    # CBOMKit repeats a component entry verbatim when the same finding is
    # observed more than once, and the pipeline keys everything by bom_ref,
    # so identical repeats are normal output and only recorded. Two
    # *different* components sharing a bom-ref would break ECDAT's finding
    # identity, so that is an error.
    repeated = [ref for ref, count in Counter(refs).items() if count > 1]
    conflicting = []
    if repeated:
        fingerprints = {}
        for component in components:
            if not isinstance(component, dict):
                continue
            ref = component.get("bom-ref")
            if ref not in set(repeated):
                continue
            fingerprint = json.dumps(component, sort_keys=True)
            if ref in fingerprints and fingerprints[ref] != fingerprint:
                conflicting.append(ref)
            fingerprints.setdefault(ref, fingerprint)

        if conflicting:
            errors.append(
                {
                    "code": "conflicting-bom-ref",
                    "message": (
                        f"{len(set(conflicting))} bom-ref(s) are used by different components: "
                        f"{', '.join(sorted(set(conflicting))[:3])}."
                    ),
                }
            )
        identical = len(repeated) - len(set(conflicting))
        if identical > 0:
            warnings.append(
                {
                    "code": "repeated-component-entry",
                    "message": (
                        f"{identical} bom-ref(s) appear as repeated identical component entries; "
                        "ECDAT keys findings by bom_ref, so each is analysed once."
                    ),
                }
            )

    dependencies = cbom.get("dependencies")
    dependency_edges = 0
    if dependencies is None:
        warnings.append({"code": "missing-dependencies", "message": "CBOM has no dependencies array."})
        dependencies = []
    elif not isinstance(dependencies, list):
        errors.append({"code": "invalid-dependencies", "message": "CBOM dependencies is not an array."})
        dependencies = []

    known = set(refs)
    unknown_refs = set()
    for entry in dependencies:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("ref")
        if ref and ref not in known:
            unknown_refs.add(ref)
        for depends_on in entry.get("dependsOn") or []:
            dependency_edges += 1
            if depends_on not in known:
                unknown_refs.add(depends_on)

    if unknown_refs:
        # Recorded, not repaired: the graph stages already ignore refs that
        # are not findings, and inventing them would fabricate relationships.
        warnings.append(
            {
                "code": "dangling-dependency-ref",
                "message": f"{len(unknown_refs)} dependency ref(s) point at components that are not in this CBOM.",
            }
        )

    if not crypto_components and not errors:
        errors.append(
            {
                "code": "no-crypto-components",
                "message": "The scan produced no cryptographic components, so there is nothing for ECDAT to analyse.",
            }
        )

    stats = {
        "components": len(components),
        # Entries as the scanner reported them, and the findings ECDAT will
        # analyse: one per bom_ref, which is what the dashboard counts.
        "crypto_components": crypto_components,
        "findings": len(crypto_refs),
        "dependency_entries": len(dependencies),
        "dependency_edges": dependency_edges,
        "unique_bom_refs": len(set(refs)),
        "asset_types": dict(sorted(asset_types.items())),
    }

    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def normalize_cbom(cbom: dict) -> tuple:
    """Returns (cbom, notes) with the arrays the pipeline reads guaranteed.

    Only ever *adds* an empty container; component and dependency content is
    passed through untouched.
    """
    normalized = dict(cbom)
    notes = []

    if normalized.get("components") is None:
        normalized["components"] = []
        notes.append("Added an empty components array (the CBOM had none).")

    if normalized.get("dependencies") is None:
        normalized["dependencies"] = []
        notes.append("Added an empty dependencies array (the CBOM had none).")

    return normalized, notes

"""
Regression tests for repository-specific cryptographic-purpose
resolution (services/purpose_resolver.py), wired in via
classify_cbom.py's classify_and_resolve().

These tests verify the EVIDENCE-PRIORITY BEHAVIOR (CBOM primitive >
source/API context > algorithm-family fallback), not one hardcoded
algorithm. RSA-OAEP is covered as one instance of the general system
(test_f_*), not as a special case the resolver's code knows about --
resolve_purpose() and classify_context() never mention "RSA" or
"OAEP" anywhere.
"""

from classify_cbom import classify_and_resolve
from services.crypto_classifier import classify_asset
from services.purpose_resolver import classify_context, resolve_purpose


def _asset(name, primitive=None, occurrences=None, asset_type="algorithm"):
    return {
        "name": name,
        "asset_type": asset_type,
        "primitive": primitive,
        "occurrences": occurrences or [],
    }


def _occ(context, location="src/example.py", line=1):
    return {"location": location, "line": line, "offset": 0, "context": context}


# ================================================================
# A. Same algorithm family, different purposes across findings.
# ================================================================


def test_same_algorithm_different_purposes():
    """
    Two independent "RSA"-named findings with different source
    evidence must resolve to different purposes -- proving the
    resolver looks at each finding's own evidence, not the name.
    """

    encryption_finding = classify_and_resolve(
        _asset(
            "RSA",
            primitive="pke",
            occurrences=[_occ("javax.crypto.Cipher#getInstance(Ljava/lang/String;)V")],
        )
    )

    signature_finding = classify_and_resolve(
        _asset(
            "RSA",
            primitive="pke",
            occurrences=[_occ("java.security.Signature#getInstance(Ljava/lang/String;)V")],
        )
    )

    assert encryption_finding["classification"]["purpose"] == ["encryption"]
    assert signature_finding["classification"]["purpose"] == ["digital-signature"]
    assert (
        encryption_finding["classification"]["purpose"]
        != signature_finding["classification"]["purpose"]
    )


# ================================================================
# B. Explicit CBOM primitive/OID evidence wins over the generic
#    algorithm-family assumption.
# ================================================================


def test_explicit_primitive_overrides_family_default():
    """
    crypto_classifier's "rsa" family default purpose is
    ["encryption", "digital-signature"] (both, since a bare "RSA"
    name alone can't tell). An explicit, decisive CBOM primitive for
    one specific finding must narrow that down instead of leaving the
    generic dual-purpose family answer in place.
    """

    family_only = classify_asset(_asset("RSA"))
    assert set(family_only["classification"]["purpose"]) == {
        "encryption",
        "digital-signature",
    }

    resolved = classify_and_resolve(_asset("RSA", primitive="signature"))

    assert resolved["classification"]["purpose"] == ["digital-signature"]
    assert resolved["classification"]["purpose_confidence"] == "HIGH"
    assert resolved["classification"]["purpose_evidence_source"] == "cbom-primitive"
    assert resolved["classification"]["purpose_needs_review"] is False


# ================================================================
# C. Source API/context evidence resolves purpose when CBOM
#    primitive metadata alone is insufficient.
# ================================================================


def test_source_context_resolves_ambiguous_primitive():
    """
    primitive == "pke" is deliberately treated as ambiguous (real
    CBOM data assigns it to RSA and DH alike regardless of actual
    sub-usage). A decisive source API call must still resolve it.
    """

    resolved = classify_and_resolve(
        _asset(
            "DH",
            primitive="pke",
            occurrences=[_occ("javax.crypto.KeyAgreement#getInstance(Ljava/lang/String;)V")],
        )
    )

    assert resolved["classification"]["purpose"] == ["key-agreement"]
    assert resolved["classification"]["purpose_confidence"] == "MEDIUM"
    assert resolved["classification"]["purpose_evidence_source"] == "source-context"


# ================================================================
# D. Conflicting evidence -> needs-review, not an invented purpose.
# ================================================================


def test_conflicting_primitive_and_context_needs_review():
    """
    A decisive CBOM primitive ("signature") contradicted by a
    decisive source API call (a Cipher, which is encryption-only)
    must not be silently resolved either way.
    """

    resolved = classify_and_resolve(
        _asset(
            "EXAMPLE-ALG",
            primitive="signature",
            occurrences=[_occ("javax.crypto.Cipher#getInstance(Ljava/lang/String;)V")],
        )
    )

    classification = resolved["classification"]

    assert classification["purpose_needs_review"] is True
    assert classification["purpose_evidence_source"] == "conflicting"
    assert set(classification["purpose"]) == {"digital-signature", "encryption"}
    # The conflicting evidence itself must be preserved, not discarded.
    assert classification["purpose_evidence"]["cbom_primitive"] == "signature"
    assert any(
        "cipher" in c.lower()
        for c in classification["purpose_evidence"]["source_contexts"]
    )


def test_conflicting_source_contexts_across_occurrences_needs_review():
    """
    Even with no CBOM primitive at all, if different occurrences of
    the SAME finding call APIs for different purposes, that is a
    genuine conflict, not a fallback case.
    """

    resolved = classify_and_resolve(
        _asset(
            "EXAMPLE-ALG-2",
            occurrences=[
                _occ("javax.crypto.Cipher#getInstance(Ljava/lang/String;)V"),
                _occ("java.security.Signature#getInstance(Ljava/lang/String;)V"),
            ],
        )
    )

    classification = resolved["classification"]

    assert classification["purpose_needs_review"] is True
    assert classification["purpose_evidence_source"] == "conflicting"
    assert set(classification["purpose"]) == {"digital-signature", "encryption"}


# ================================================================
# E. No decisive source evidence -> algorithm-family fallback,
#    clearly marked as such with lower confidence.
# ================================================================


def test_no_decisive_evidence_falls_back_to_family_with_low_confidence():
    """
    Generic key-material APIs (KeyFactory, *PublicNumbers,
    generate_private_key) are deliberately NOT decisive in
    classify_context() -- using them to guess a specific purpose
    would be exactly the kind of invented certainty this system must
    avoid. With no other evidence, the family fallback is used, but
    at low confidence and explicitly labeled as a fallback.
    """

    resolved = classify_and_resolve(
        _asset(
            "RSA-2048",
            primitive="pke",
            occurrences=[_occ("java.security.KeyFactory#getInstance(Ljava/lang/String;)V")],
        )
    )

    classification = resolved["classification"]

    assert classification["purpose_confidence"] == "LOW"
    assert classification["purpose_evidence_source"] == "algorithm-family-fallback"
    assert classification["purpose_needs_review"] is False
    assert set(classification["purpose"]) == {"encryption", "digital-signature"}
    assert classification["purpose_evidence"]["family_fallback_purpose"]


def test_no_evidence_at_all_is_insufficient_not_guessed():
    """
    An asset with an unclassifiable name AND no primitive AND no
    occurrences has no evidence at any tier -- it must be marked
    insufficient/needs-review, never assigned a fabricated purpose.
    """

    resolved = classify_and_resolve(_asset("Quixotic-Cipher-9000"))

    classification = resolved["classification"]

    assert classification["purpose"] == []
    assert classification["purpose_evidence_source"] == "insufficient-evidence"
    assert classification["purpose_needs_review"] is True


# ================================================================
# F. RSA-OAEP -- one instance of the general system, not a special
#    case. Uses the exact real-world evidence shape observed in the
#    actual analyzed dataset (primitive "pke" + a javax.crypto.Cipher
#    API call).
# ================================================================


def test_rsa_oaep_resolves_to_encryption_from_its_own_evidence():
    resolved = classify_and_resolve(
        _asset(
            "RSA-OAEP",
            primitive="pke",
            occurrences=[
                _occ(
                    "javax.crypto.Cipher#getInstance(Ljava/lang/String;Ljava/lang/String;)Ljavax/crypto/Cipher;",
                    location="docs/development/custom-vectors/rsa-oaep-sha2/VerifyRSAOAEPSHA2.java",
                    line=265,
                )
            ],
        )
    )

    classification = resolved["classification"]

    assert classification["purpose"] == ["encryption"]
    assert "digital-signature" not in classification["purpose"]
    assert classification["usage"] == "encryption"
    assert classification["purpose_confidence"] == "MEDIUM"
    assert classification["purpose_evidence_source"] == "source-context"
    assert classification["purpose_needs_review"] is False

    # Sanity check: the actual decision logic (not the module's
    # explanatory docstrings/comments, which do name RSA-OAEP as a
    # motivating example) contains no algorithm-name-specific
    # branching for this to have worked.
    import inspect

    decision_logic = inspect.getsource(resolve_purpose) + inspect.getsource(
        classify_context
    )
    assert "OAEP" not in decision_logic
    assert "RSA" not in decision_logic


def test_hash_embedded_in_mac_construction_is_not_a_false_conflict():
    """
    Real-data regression: a hash whose CBOM primitive is explicitly
    "hash" can still show occurrence contexts that are bare
    construction-name mentions (e.g. "HMAC", "HKDF") rather than API
    calls, because that hash is used as a component inside those
    constructions elsewhere in the source. That must resolve cleanly
    as "hash" (the hash's own, explicit, decisive primitive) -- not
    as a conflict with "message-authentication"/"key-derivation".
    """

    resolved = classify_and_resolve(
        _asset(
            "SHA256",
            primitive="hash",
            occurrences=[
                _occ("HMAC", location="src/cryptography/fernet.py", line=81),
                _occ("HMAC", location="src/cryptography/fernet.py", line=130),
                _occ("HKDF", location="docs/development/custom-vectors/hkdf/generate_hkdf.py"),
            ],
        )
    )

    classification = resolved["classification"]

    assert classification["purpose"] == ["hash"]
    assert classification["purpose_confidence"] == "HIGH"
    assert classification["purpose_evidence_source"] == "cbom-primitive"
    assert classification["purpose_needs_review"] is False


def test_classify_context_recognizes_cipher_api():
    assert classify_context("javax.crypto.Cipher#getInstance(...)") == "encryption"
    assert classify_context("java.security.Signature#getInstance(...)") == "digital-signature"
    assert classify_context("javax.crypto.KeyAgreement#getInstance(...)") == "key-agreement"
    assert classify_context("java.security.KeyFactory#getInstance(...)") is None
    assert classify_context("RSAPublicNumbers") is None
    assert classify_context(None) is None


# ================================================================
# G. Downstream propagation -- PQC mapping must follow the resolved
#    purpose, not re-derive it from the algorithm name.
# ================================================================


def test_pqc_mapper_follows_resolved_encryption_purpose():
    """
    Given a resolved classification whose purpose is encryption-only
    (as RSA-OAEP's real evidence produces), the PQC mapper must not
    recommend a signature family the way it would for a genuinely
    signature-purposed asymmetric finding.
    """

    from services.pqc_mapper import map_asset_to_pqc

    resolved = classify_and_resolve(
        _asset(
            "RSA-OAEP",
            primitive="pke",
            occurrences=[
                _occ("javax.crypto.Cipher#getInstance(Ljava/lang/String;)V")
            ],
        )
    )

    mapping = map_asset_to_pqc(
        {
            "name": resolved["name"],
            "classification": resolved["classification"],
        }
    )

    # Encryption-purpose asymmetric findings are not routed through
    # the digital-signature PQC_CANDIDATE branch.
    assert not any(
        candidate["family"] == "digital-signature"
        for candidate in mapping["candidates"]
    )


def test_pqc_mapper_still_recommends_signature_for_signature_purpose():
    """
    Control case: a finding whose evidence genuinely resolves to
    digital-signature must still receive signature-family PQC
    candidates -- proving the fix narrows recommendations based on
    evidence, it doesn't just suppress signature recommendations
    everywhere.
    """

    from services.pqc_mapper import map_asset_to_pqc

    resolved = classify_and_resolve(_asset("RSA", primitive="signature"))

    mapping = map_asset_to_pqc(
        {
            "name": resolved["name"],
            "classification": resolved["classification"],
        }
    )

    assert any(
        candidate["family"] == "digital-signature"
        for candidate in mapping["candidates"]
    )


if __name__ == "__main__":

    test_same_algorithm_different_purposes()
    test_explicit_primitive_overrides_family_default()
    test_source_context_resolves_ambiguous_primitive()
    test_conflicting_primitive_and_context_needs_review()
    test_conflicting_source_contexts_across_occurrences_needs_review()
    test_no_decisive_evidence_falls_back_to_family_with_low_confidence()
    test_no_evidence_at_all_is_insufficient_not_guessed()
    test_rsa_oaep_resolves_to_encryption_from_its_own_evidence()
    test_hash_embedded_in_mac_construction_is_not_a_false_conflict()
    test_classify_context_recognizes_cipher_api()
    test_pqc_mapper_follows_resolved_encryption_purpose()
    test_pqc_mapper_still_recommends_signature_for_signature_purpose()

    print("\nAll purpose-resolver tests passed.")

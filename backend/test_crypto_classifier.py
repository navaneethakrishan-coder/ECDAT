"""
Regression tests for the generalized cryptographic classification
system (services/crypto_classifier.py + knowledge/crypto_knowledge.py).

These tests verify GENERAL classification behavior -- semantic
category/purpose/quantum-status for entire algorithm families -- not
the exact asset list of any one analyzed repository. The algorithms
the SIH-PS audit found misclassified (DH, Ed25519, Ed448, X25519,
X448, SHAKE256) and the KDF/HMAC ordering issue are included here as
permanent regression cases so they cannot silently regress, but the
suite also covers naming variants, unrelated algorithm families, and
deliberately unknown/malformed input, so a future change cannot pass
this file by re-special-casing just these seven names.
"""

from services.crypto_classifier import classify_asset


def _asset(name, asset_type="algorithm"):
    return {"name": name, "asset_type": asset_type, "occurrences": []}


def _classify(name, asset_type="algorithm"):
    return classify_asset(_asset(name, asset_type))["classification"]


# ================================================================
# A. Audit regression cases -- previously misclassified as
#    category="unknown" / quantum_status="unknown" despite being
#    real, quantum-vulnerable (or, for SHAKE256, a real hash).
# ================================================================


def test_dh_is_vulnerable_key_agreement():
    result = _classify("DH")

    assert result["category"] == "asymmetric"
    assert "key-agreement" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_ed25519_is_vulnerable_signature():
    result = _classify("Ed25519")

    assert result["category"] == "asymmetric"
    assert "digital-signature" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_ed448_is_vulnerable_signature():
    result = _classify("Ed448")

    assert result["category"] == "asymmetric"
    assert "digital-signature" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_x25519_is_vulnerable_key_agreement():
    result = _classify("x25519")

    assert result["category"] == "asymmetric"
    assert "key-agreement" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_x448_is_vulnerable_key_agreement():
    result = _classify("x448")

    assert result["category"] == "asymmetric"
    assert "key-agreement" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_shake256_is_a_hash_not_asymmetric():
    """
    SHAKE256 is a SHA-3-family extendable-output hash function. It
    must not be classified as asymmetric/unknown merely because it is
    "cryptographic" -- and it must not be scored quantum-vulnerable
    the way a public-key primitive is.
    """

    result = _classify("SHAKE256")

    assert result["category"] == "hash"
    assert "hash" in result["purpose"]
    assert result["quantum_status"] == "quantum-aware"
    assert result["quantum_status"] != "vulnerable"


def test_kdf_takes_precedence_over_generic_hmac_substring():
    """
    The audit-reported ordering issue: a name containing both a KDF
    token and an HMAC-shaped token (a real, common construction --
    e.g. PBKDF2 instantiated with HMAC-SHA1) must resolve as the more
    specific key-derivation classification, not as a bare MAC.
    """

    result = _classify("PBKDF2WithHmacSHA1")

    assert result["category"] == "key-derivation"
    assert result["category"] != "mac"


def test_hkdf_is_key_derivation_not_mac():
    """
    A second, differently-shaped real-world regression case for the
    same ordering issue: HKDF's name embeds "KDF" immediately after an
    "H" that could otherwise look HMAC-adjacent.
    """

    result = _classify("HKDF-SHA256")

    assert result["category"] == "key-derivation"


# ================================================================
# B. Aliases / naming variants -- same family, different spelling,
#    case, separators or standard shorthand.
# ================================================================


def test_dh_aliases_all_resolve_identically():
    canonical = _classify("DH")

    for variant in ["Diffie-Hellman", "diffie hellman", "DIFFIEHELLMAN", "DHE"]:
        result = _classify(variant)

        assert result["category"] == canonical["category"]
        assert result["purpose"] == canonical["purpose"]
        assert result["quantum_status"] == canonical["quantum_status"], variant


def test_eddsa_compound_name_resolves_as_signature():
    result = _classify("EdDSA Ed25519")

    assert result["category"] == "asymmetric"
    assert "digital-signature" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_x25519_with_trailing_description_still_matches():
    result = _classify("X25519 key agreement")

    assert result["category"] == "asymmetric"
    assert "key-agreement" in result["purpose"]


def test_ecdhe_ephemeral_variant_matches_ecdh_family():
    ecdh = _classify("ECDH")
    ecdhe = _classify("ECDHE")

    assert ecdhe["category"] == ecdh["category"]
    assert ecdhe["purpose"] == ecdh["purpose"]
    assert ecdhe["quantum_status"] == ecdh["quantum_status"]


def test_case_insensitivity_across_families():
    assert _classify("rsa")["category"] == _classify("RSA")["category"]
    assert _classify("aes-256")["quantum_status"] == _classify("AES-256")["quantum_status"]
    assert _classify("sha256")["category"] == _classify("SHA256")["category"]


def test_hkdf_and_hmac_variants_of_different_hash_sizes():
    for name in ["HKDF-SHA256", "HKDF-SHA384", "HKDF-SHA512"]:
        assert _classify(name)["category"] == "key-derivation", name

    for name in ["HMAC-SHA256", "HMAC-SHA384", "HMAC-SHA512"]:
        result = _classify(name)
        assert result["category"] == "mac", name


def test_pbkdf2_and_scrypt_and_argon2_are_all_key_derivation():
    for name in ["PBKDF2", "pbkdf2", "scrypt", "Argon2id"]:
        assert _classify(name)["category"] == "key-derivation", name


# ================================================================
# C. Unrelated algorithm families -- must remain correctly and
#    stably classified; this is the "did we break anything else"
#    check for the whole rewrite.
# ================================================================


def test_aes_quantum_status_depends_on_key_size_when_recorded():
    aes_256 = _classify("AES-256")
    aes_128 = _classify("AES-128")
    aes_unspecified = _classify("AES")

    assert aes_256["quantum_status"] == "quantum-resistant"
    assert aes_128["quantum_status"] == "reduced-security-margin"
    assert aes_unspecified["quantum_status"] == "reduced-security-margin"

    for result in (aes_256, aes_128, aes_unspecified):
        assert result["category"] == "symmetric"
        assert "encryption" in result["purpose"]


def test_aes_gcm_mode_suffix_does_not_break_key_size_detection():
    result = _classify("AES-256-GCM")

    assert result["category"] == "symmetric"
    assert result["quantum_status"] == "quantum-resistant"


def test_chacha20_poly1305_is_quantum_resistant_symmetric():
    result = _classify("ChaCha20-Poly1305")

    assert result["category"] == "symmetric"
    assert result["quantum_status"] == "quantum-resistant"


def test_sha2_family_is_hash_quantum_aware():
    for name in ["SHA-256", "SHA256", "SHA-384", "SHA512"]:
        result = _classify(name)

        assert result["category"] == "hash", name
        assert result["quantum_status"] == "quantum-aware", name


def test_sha1_and_md5_are_weak_not_vulnerable():
    for name in ["SHA1", "SHA-1", "MD5"]:
        result = _classify(name)

        assert result["category"] == "hash", name
        assert result["quantum_status"] == "weak", name


def test_rsa_family_is_vulnerable_asymmetric():
    for name in ["RSA", "RSA-2048", "RSA-OAEP"]:
        result = _classify(name)

        assert result["category"] == "asymmetric", name
        assert result["quantum_status"] == "vulnerable", name
        assert "encryption" in result["purpose"] or "digital-signature" in result["purpose"]


def test_ecdsa_and_ecdh_are_distinct_purposes_same_risk():
    ecdsa = _classify("ECDSA")
    ecdh = _classify("ECDH")

    assert ecdsa["category"] == ecdh["category"] == "asymmetric"
    assert ecdsa["quantum_status"] == ecdh["quantum_status"] == "vulnerable"

    assert "digital-signature" in ecdsa["purpose"]
    assert "key-agreement" in ecdh["purpose"]
    # These are genuinely different cryptographic roles and must not
    # collapse into the same purpose list.
    assert ecdsa["purpose"] != ecdh["purpose"]


def test_dsa_is_vulnerable_signature():
    result = _classify("DSA")

    assert result["category"] == "asymmetric"
    assert "digital-signature" in result["purpose"]
    assert result["quantum_status"] == "vulnerable"


def test_tls_is_protocol_not_asymmetric():
    result = _classify("TLS")

    assert result["category"] == "protocol"
    assert result["quantum_status"] != "vulnerable"


# ================================================================
# D. Unknown / malformed input -- must never be guessed.
# ================================================================


def test_unrecognized_algorithm_is_unknown_not_guessed():
    result = _classify("Quixotic-Cipher-9000")

    assert result["category"] == "unknown"
    assert result["purpose"] == []
    assert result["quantum_status"] == "unknown"


def test_empty_name_is_unknown():
    result = _classify("")

    assert result["category"] == "unknown"
    assert result["quantum_status"] == "unknown"


def test_missing_name_field_is_unknown():
    asset = {"asset_type": "algorithm", "occurrences": []}
    result = classify_asset(asset)["classification"]

    assert result["category"] == "unknown"


def test_none_name_does_not_raise():
    asset = {"name": None, "asset_type": "algorithm", "occurrences": []}
    result = classify_asset(asset)["classification"]

    assert result["category"] == "unknown"


# ================================================================
# E. Evidence-driven precedence: asset_type beats name substring.
# ================================================================


def test_crypto_material_asset_type_overrides_name_substring():
    """
    A key-material record whose CBOMKit-generated name happens to
    embed an algorithm-like token (e.g. an RSA key's identifier) must
    still be classified by its asset_type as crypto-material, not
    mis-routed into the RSA algorithm family by name substring alone.
    """

    result = _classify("private-key@rsa-1", asset_type="related-crypto-material")

    assert result["category"] == "crypto-material"
    assert result["purpose"] == ["private-key"]


def test_crypto_material_prefixes_are_distinguished():
    assert _classify("public-key@a", "related-crypto-material")["purpose"] == ["public-key"]
    assert _classify("private-key@b", "related-crypto-material")["purpose"] == ["private-key"]
    assert _classify("secret-key@c", "related-crypto-material")["purpose"] == ["secret-key"]
    assert _classify("key@d", "related-crypto-material")["purpose"] == ["key"]


# ================================================================
# F. Determinism and architecture integrity.
# ================================================================


def test_classification_is_deterministic():
    first = _classify("Ed25519")
    second = _classify("Ed25519")

    assert first == second


def test_family_registry_has_no_alias_collisions():
    """
    knowledge/crypto_knowledge.py raises at import time if two
    families ever claim the same alias. Successfully importing
    classify_asset (done at module load, above) already proves this
    held for the current registry; this test exists so a future
    registry change that reintroduces a collision fails loudly here
    instead of only failing whenever someone happens to import the
    module next.
    """

    from knowledge.crypto_knowledge import CRYPTO_FAMILIES, _build_alias_maps

    # Raises ValueError on collision -- reaching the assert means it
    # did not.
    alias_map, compact_map = _build_alias_maps(CRYPTO_FAMILIES)

    assert len(alias_map) > 0
    assert len(compact_map) > 0


if __name__ == "__main__":

    test_dh_is_vulnerable_key_agreement()
    test_ed25519_is_vulnerable_signature()
    test_ed448_is_vulnerable_signature()
    test_x25519_is_vulnerable_key_agreement()
    test_x448_is_vulnerable_key_agreement()
    test_shake256_is_a_hash_not_asymmetric()
    test_kdf_takes_precedence_over_generic_hmac_substring()
    test_hkdf_is_key_derivation_not_mac()

    test_dh_aliases_all_resolve_identically()
    test_eddsa_compound_name_resolves_as_signature()
    test_x25519_with_trailing_description_still_matches()
    test_ecdhe_ephemeral_variant_matches_ecdh_family()
    test_case_insensitivity_across_families()
    test_hkdf_and_hmac_variants_of_different_hash_sizes()
    test_pbkdf2_and_scrypt_and_argon2_are_all_key_derivation()

    test_aes_quantum_status_depends_on_key_size_when_recorded()
    test_aes_gcm_mode_suffix_does_not_break_key_size_detection()
    test_chacha20_poly1305_is_quantum_resistant_symmetric()
    test_sha2_family_is_hash_quantum_aware()
    test_sha1_and_md5_are_weak_not_vulnerable()
    test_rsa_family_is_vulnerable_asymmetric()
    test_ecdsa_and_ecdh_are_distinct_purposes_same_risk()
    test_dsa_is_vulnerable_signature()
    test_tls_is_protocol_not_asymmetric()

    test_unrecognized_algorithm_is_unknown_not_guessed()
    test_empty_name_is_unknown()
    test_missing_name_field_is_unknown()
    test_none_name_does_not_raise()

    test_crypto_material_asset_type_overrides_name_substring()
    test_crypto_material_prefixes_are_distinguished()

    test_classification_is_deterministic()
    test_family_registry_has_no_alias_collisions()

    print("\nAll crypto-classifier tests passed.")

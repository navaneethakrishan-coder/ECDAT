"""
Standards knowledge for purpose-aware post-quantum migration strategy.

This module answers exactly one kind of question:

    "For a cryptographic ROLE (key establishment, digital signature,
     hashing, ...), what does post-quantum migration involve?"

It never answers which role a particular repository finding actually
plays -- that is repository evidence, resolved per finding by
services/purpose_resolver.py (CBOM primitive -> source API context ->
algorithm-family fallback) and consumed by
services/migration_strategy.py. Nothing here is keyed by algorithm
name; every entry is keyed by a purpose label or a quantum-status
value the classification pipeline already emits.

Grounding:
  - NIST FIPS 203 (ML-KEM), FIPS 204 (ML-DSA), FIPS 205 (SLH-DSA): the
    post-quantum families recorded in data/pqc-algorithms.json.
  - NIST SP 800-227 (KEM recommendations), including combining a
    classical and a post-quantum shared secret through a KDF combiner.
  - Hybrid key exchange as deployed for TLS 1.3 transition, and
    composite/dual signatures for PKI transition.
  - Shor's algorithm breaks integer-factorisation and discrete-log
    public-key cryptography; Grover's algorithm gives at most a
    quadratic speed-up against symmetric primitives, hashes, MACs and
    KDFs, which therefore have no ML-KEM/ML-DSA "replacement".
"""


# ================================================================
# Purpose classes (cryptographic roles)
# ================================================================

KEY_ESTABLISHMENT = "key-establishment"
PUBLIC_KEY_ENCRYPTION = "public-key-encryption"
DIGITAL_SIGNATURE = "digital-signature"
SYMMETRIC_ENCRYPTION = "symmetric-encryption"
HASH = "hash"
MESSAGE_AUTHENTICATION = "message-authentication"
KEY_DERIVATION = "key-derivation"
RANDOM_GENERATION = "random-generation"
MASK_GENERATION = "mask-generation"
KEY_MATERIAL = "key-material"
PROTOCOL = "protocol"
UNRESOLVED = "unresolved"

CLASS_LABELS = {
    KEY_ESTABLISHMENT: "key establishment / key agreement",
    PUBLIC_KEY_ENCRYPTION: "public-key encryption / key transport",
    DIGITAL_SIGNATURE: "digital signature",
    SYMMETRIC_ENCRYPTION: "symmetric encryption",
    HASH: "hashing",
    MESSAGE_AUTHENTICATION: "message authentication (MAC/HMAC)",
    KEY_DERIVATION: "key derivation (KDF)",
    RANDOM_GENERATION: "random generation",
    MASK_GENERATION: "mask generation",
    KEY_MATERIAL: "key material",
    PROTOCOL: "protocol",
    UNRESOLVED: "unresolved role",
}

# Purpose labels whose role does not depend on the algorithm category.
_LABEL_TO_CLASS = {
    "key-agreement": KEY_ESTABLISHMENT,
    "key-establishment": KEY_ESTABLISHMENT,
    "key-encapsulation": KEY_ESTABLISHMENT,
    "digital-signature": DIGITAL_SIGNATURE,
    "hash": HASH,
    "message-authentication": MESSAGE_AUTHENTICATION,
    "key-derivation": KEY_DERIVATION,
    "random-generation": RANDOM_GENERATION,
    "mask-generation": MASK_GENERATION,
    "public-key": KEY_MATERIAL,
    "private-key": KEY_MATERIAL,
    "secret-key": KEY_MATERIAL,
    "key": KEY_MATERIAL,
    "cryptographic-material": KEY_MATERIAL,
    "secure-communication": PROTOCOL,
}


def classify_purpose(purpose_label, category):
    """
    Map one resolved purpose label to its cryptographic role.

    "encryption" is the one label whose role depends on the category:
    public-key encryption (a key-transport role, Shor-vulnerable) and
    symmetric encryption (Grover-affected only) need entirely
    different migration handling, so an "encryption" purpose with an
    unresolved category stays UNRESOLVED rather than being guessed.
    Labels that identify no specific role (e.g. a generic
    "public-key-cryptography") are UNRESOLVED too.
    """

    label = str(purpose_label or "").strip().lower()
    category = str(category or "").strip().lower()

    if label == "encryption":
        if category == "asymmetric":
            return PUBLIC_KEY_ENCRYPTION
        if category == "symmetric":
            return SYMMETRIC_ENCRYPTION
        return UNRESOLVED

    return _LABEL_TO_CLASS.get(label, UNRESOLVED)


# ================================================================
# Per-role migration policy
# ================================================================

_SYMMETRIC_THREAT = (
    "Not broken by Shor's algorithm; Grover's algorithm gives at most a "
    "quadratic speed-up, and there is no ML-KEM or ML-DSA replacement "
    "for this role."
)

POLICIES = {
    KEY_ESTABLISHMENT: {
        "pqc_family": "KEM",
        "quantum_threat": (
            "Shor's algorithm recovers the shared secret from a recorded "
            "key exchange, so traffic captured today can be decrypted "
            "once a cryptographically-relevant quantum computer exists "
            "(harvest-now-decrypt-later)."
        ),
        "harvest_now_decrypt_later": True,
        "hybrid_construction": (
            "Run the current key agreement and a post-quantum KEM side by "
            "side and derive the session secret from both shared secrets "
            "through a KDF combiner, so the result stays secure if either "
            "component holds and peers without PQC support keep working "
            "during the transition."
        ),
        "direct_construction": (
            "Replace the current key agreement with post-quantum KEM "
            "encapsulation/decapsulation for key establishment."
        ),
    },

    PUBLIC_KEY_ENCRYPTION: {
        "pqc_family": "KEM",
        "quantum_threat": (
            "Shor's algorithm recovers the private key, exposing every key "
            "or message previously encrypted to it "
            "(harvest-now-decrypt-later)."
        ),
        "harvest_now_decrypt_later": True,
        "hybrid_construction": (
            "Protect the transported/content key with both the current "
            "public-key scheme and a post-quantum KEM, combining both "
            "secrets through a KDF, so decryption requires breaking both "
            "and existing recipients keep working during the transition."
        ),
        "direct_construction": (
            "Replace public-key encryption/key transport with post-quantum "
            "KEM encapsulation followed by symmetric encryption of the "
            "payload."
        ),
    },

    DIGITAL_SIGNATURE: {
        "pqc_family": "digital-signature",
        "quantum_threat": (
            "Shor's algorithm recovers the signing key, enabling signature "
            "forgery once a cryptographically-relevant quantum computer "
            "exists."
        ),
        "harvest_now_decrypt_later": False,
        "hybrid_construction": (
            "Produce and verify both the current signature and a "
            "post-quantum signature (composite or dual signatures), so "
            "verifiers that only understand the current scheme keep "
            "working and forgery requires breaking both."
        ),
        "direct_construction": (
            "Replace the current signature scheme with the post-quantum "
            "signature scheme for both signing and verification."
        ),
    },

    SYMMETRIC_ENCRYPTION: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
    HASH: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
    MESSAGE_AUTHENTICATION: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
    KEY_DERIVATION: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
    RANDOM_GENERATION: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
    MASK_GENERATION: {"pqc_family": None, "quantum_threat": _SYMMETRIC_THREAT, "harvest_now_decrypt_later": False},
}

# Roles whose migration target is a post-quantum family.
PQC_MIGRATION_ROLES = {
    role for role, entry in POLICIES.items() if entry["pqc_family"]
}

# Roles with no asymmetric PQC replacement at all.
NO_PQC_REPLACEMENT_ROLES = {
    role for role, entry in POLICIES.items() if not entry["pqc_family"]
}


# ================================================================
# Classical hardening for roles with no PQC replacement, keyed by the
# quantum_status the classification pipeline already recorded.
# ================================================================

CLASSICAL_HARDENING = {
    "quantum-resistant": (
        "not-required",
        "Classified as quantum-resistant; no hardening is required.",
    ),
    "quantum-aware": (
        "not-required",
        "Security margin is generally considered adequate against "
        "Grover's algorithm.",
    ),
    "reduced-security-margin": (
        "recommended",
        "Grover's algorithm halves the effective security level; consider "
        "a larger key or output size (e.g. 256-bit symmetric keys).",
    ),
    "weak": (
        "required",
        "Already weak against classical attacks, independent of quantum "
        "computing; replace it with a stronger classical primitive (a PQC "
        "KEM or signature is not a replacement for this role).",
    ),
    "contextual": (
        "review",
        "Strength depends on how it is used (inputs, key sizes, underlying "
        "hash); confirm the configuration.",
    ),
    "unknown": (
        "review",
        "Quantum status could not be determined from the evidence; confirm "
        "the primitive and its parameters.",
    ),
}


def classical_hardening_for(quantum_status):
    status, reason = CLASSICAL_HARDENING.get(
        str(quantum_status or "unknown").strip().lower(),
        CLASSICAL_HARDENING["unknown"],
    )

    return {"status": status, "reason": reason}


# ================================================================
# Transition requirements (hybrid vs direct)
# ================================================================

# Exposure values (services/risk_context.py, derived from occurrence
# file paths and API-usage context) indicating communication with
# parties outside the scanned code base.
EXTERNAL_INTEROPERABILITY_EXPOSURE = {"INTERNET"}

# Complexity / blast-radius levels indicating a migration that cannot
# realistically be switched over in one step.
PHASED_TRANSITION_LEVELS = {"HIGH", "CRITICAL"}

# Effective quantum status of the migrated role, used by the what-if
# foundation (services/migration_scenario.py). A hybrid KDF combiner
# or composite signature stays secure as long as either component
# does, so both strategies remove the Shor-vulnerability of the role.
POST_MIGRATION_QUANTUM_STATUS = "quantum-resistant"

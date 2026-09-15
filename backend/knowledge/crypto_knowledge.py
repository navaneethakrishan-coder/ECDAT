"""
ECDAT cryptographic-algorithm family registry.

This is the single source of truth for mapping a CBOM component's raw
*name* to a cryptographic role: category (asymmetric/symmetric/hash/
mac/key-derivation/protocol/...), purpose (key-agreement/digital-
signature/encryption/hash/...), and quantum-vulnerability status.

WHY THIS EXISTS (see docs/CHANGELOG.md for the audit that prompted it):
The previous version of this module was a small flat dictionary of
~14 exact algorithm names, backed by an ad hoc if/elif chain of name
substring checks in services/crypto_classifier.py. That meant any
algorithm not in the dictionary AND not matching one of ~12 hand-
written substring rules silently fell to "unknown" with zero quantum
risk -- confirmed to misclassify real, definitely quantum-vulnerable
algorithms (DH, Ed25519, Ed448, X25519, X448) this way, and to have at
least one substring-ordering bug (a generic "HMAC" substring check ran
before the "KDF" check, so a KDF name that happens to also contain
"Hmac" -- e.g. a PBKDF2-with-HMAC construction -- would be misfiled as
a MAC instead of a key-derivation function).

This module replaces both the dictionary and the substring chain with
one data-driven registry: each cryptographic *family* (not each exact
algorithm name) is one entry, matched by:
  - an exact-alias set (case/spacing-insensitive), for O(1), zero-
    ambiguity lookup of known names and their common variant spellings
    ("DH", "Diffie-Hellman", "diffie hellman" all resolve the same
    way), and
  - a small set of anchored regular expressions, for names that carry
    the family token as a prefix/suffix (e.g. "AES-256-GCM",
    "SHA3-256", "HMAC-SHA512") without needing every combination
    enumerated as a literal alias.

Adding support for a new algorithm in an already-supported family
(e.g. a new hash size, a new KDF construction) means adding an alias
or loosening a pattern in ONE place -- it does not require touching
services/crypto_classifier.py, and it does not risk silently shadowing
an unrelated family, because alias collisions are checked at import
time (see _build_alias_maps) rather than depending on if/elif order.

WHAT THIS MODULE DELIBERATELY DOES NOT DO:
- It never fabricates a classification. If a name matches nothing
  here, resolve_family_classification() returns None and the caller
  (services/crypto_classifier.py) records the asset as
  category="unknown" -- evidence-driven, not guessed.
- It never infers key size, curve, mode or padding from anything but
  the name string itself (the only thing this stage has). AES is the
  one family whose displayed quantum-status genuinely depends on a
  parameter recorded in the name (key size) -- see _classify_aes().
  Every other family's quantum status depends only on which family it
  is, not on unobserved parameters.
"""

import re


def _rx(pattern):
    return re.compile(pattern, re.IGNORECASE)


def _normalize(name):
    """Case- and whitespace-insensitive form used for every comparison."""
    return str(name or "").strip().upper()


def _compact(name):
    """
    Separator-insensitive form of an already-normalized name, so
    "DIFFIE-HELLMAN", "DIFFIE HELLMAN" and "DIFFIEHELLMAN" all resolve
    to the same alias without enumerating every spacing variant.
    """
    return re.sub(r"[-_ .]", "", name)


# ================================================================
# ALGORITHM FAMILIES
#
# Order matters ONLY for the regex-pattern fallback pass (exact-alias
# lookup is order-independent, O(1), and collision-checked at import
# time). Where two families could plausibly both match a compound
# name, the MORE SPECIFIC family is listed first. This is where the
# audit-reported KDF/HMAC ordering issue is actually fixed: "kdf" is
# checked before "mac", so a name containing both tokens (e.g. a
# PBKDF2-with-HMAC construction) resolves as a key-derivation function
# -- the more specific classification -- rather than a bare MAC.
# ================================================================

CRYPTO_FAMILIES = [
    {
        "family": "rsa",
        "category": "asymmetric",
        "purpose": ["encryption", "digital-signature"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "RSA relies on integer factorization, which is broken by "
            "Shor's algorithm on a sufficiently capable quantum computer."
        ),
        "aliases": {"RSA"},
        "patterns": [_rx(r"^RSA\b"), _rx(r"^RSA[-_]?\d")],
    },
    {
        "family": "finite-field-dh",
        "category": "asymmetric",
        "purpose": ["key-agreement"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "Diffie-Hellman key agreement relies on the discrete-logarithm "
            "problem, which is broken by Shor's algorithm on a "
            "sufficiently capable quantum computer."
        ),
        "aliases": {"DH", "DHE", "DIFFIE-HELLMAN", "DIFFIEHELLMAN", "FFDH", "DHKE"},
        "patterns": [_rx(r"^DHE?\b"), _rx(r"^DIFFIE[-_ ]?HELLMAN\b"), _rx(r"^FFDHE?\d*$")],
    },
    {
        "family": "elliptic-curve-key-agreement",
        "category": "asymmetric",
        "purpose": ["key-agreement"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "Elliptic-curve key agreement relies on the elliptic-curve "
            "discrete-logarithm problem, which is broken by Shor's "
            "algorithm on a sufficiently capable quantum computer."
        ),
        # ECDHE ("ephemeral" ECDH) is a standard, widely-used TLS
        # cipher-suite shorthand for the same key-agreement family --
        # a real naming variant, not a guess.
        "aliases": {"ECDH", "ECDHE", "X25519", "X448"},
        "patterns": [_rx(r"^ECDHE?\b"), _rx(r"^X(25519|448)\b")],
    },
    {
        "family": "elliptic-curve-signature",
        "category": "asymmetric",
        "purpose": ["digital-signature"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "Elliptic-curve digital signatures rely on the elliptic-curve "
            "discrete-logarithm problem, which is broken by Shor's "
            "algorithm on a sufficiently capable quantum computer."
        ),
        "aliases": {"ECDSA", "EDDSA", "ED25519", "ED448"},
        "patterns": [
            _rx(r"^ECDSA\b"),
            _rx(r"^ED(25519|448)\b"),
            _rx(r"^EDDSA([-_ ]?ED(25519|448))?\b"),
        ],
    },
    {
        "family": "dsa",
        "category": "asymmetric",
        "purpose": ["digital-signature"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "DSA relies on the discrete-logarithm problem, which is "
            "broken by Shor's algorithm on a sufficiently capable "
            "quantum computer."
        ),
        "aliases": {"DSA"},
        "patterns": [_rx(r"^DSA$")],
    },
    {
        "family": "generic-elliptic-curve",
        "category": "asymmetric",
        "purpose": ["public-key-cryptography"],
        "quantum_status": "vulnerable",
        "risk_reason": (
            "Elliptic-curve cryptography is broken by Shor's algorithm "
            "on a sufficiently capable quantum computer."
        ),
        "aliases": {"EC"},
        "patterns": [_rx(r"^EC$")],
    },
    {
        "family": "chacha20",
        "category": "symmetric",
        "purpose": ["encryption"],
        "quantum_status": "quantum-resistant",
        "risk_reason": (
            "ChaCha20 is a 256-bit-key stream cipher with a strong "
            "security margin against quantum search (Grover's algorithm) "
            "attacks."
        ),
        "aliases": {"CHACHA20", "CHACHA20-POLY1305"},
        "patterns": [_rx(r"^CHACHA20\b")],
    },
    {
        "family": "hash-md5",
        "category": "hash",
        "purpose": ["hash"],
        "quantum_status": "weak",
        "risk_reason": (
            "MD5 is already considered cryptographically weak for modern "
            "security applications, independent of quantum considerations."
        ),
        "aliases": {"MD5"},
        "patterns": [_rx(r"^MD5$")],
    },
    {
        "family": "hash-sha1",
        "category": "hash",
        "purpose": ["hash"],
        "quantum_status": "weak",
        "risk_reason": (
            "SHA-1 is already considered cryptographically weak for "
            "modern security applications, independent of quantum "
            "considerations."
        ),
        "aliases": {"SHA1", "SHA-1"},
        "patterns": [_rx(r"^SHA-?1$")],
    },
    {
        "family": "hash-sha2",
        "category": "hash",
        "purpose": ["hash"],
        "quantum_status": "quantum-aware",
        "risk_reason": (
            "SHA-2 family hashes remain useful with a reduced theoretical "
            "security margin against quantum search (Grover's algorithm)."
        ),
        "aliases": {
            "SHA224", "SHA256", "SHA384", "SHA512",
            "SHA-224", "SHA-256", "SHA-384", "SHA-512",
        },
        "patterns": [_rx(r"^SHA-?(224|256|384|512)$")],
    },
    {
        "family": "hash-sha3",
        "category": "hash",
        "purpose": ["hash"],
        "quantum_status": "quantum-aware",
        "risk_reason": (
            "SHA-3/SHAKE family functions remain useful with a reduced "
            "theoretical security margin against quantum search (Grover's "
            "algorithm)."
        ),
        "aliases": {
            "SHA3-224", "SHA3-256", "SHA3-384", "SHA3-512",
            "SHAKE128", "SHAKE256",
        },
        "patterns": [_rx(r"^SHA3-?(224|256|384|512)$"), _rx(r"^SHAKE(128|256)\b")],
    },
    {
        # Checked before "mac" below -- see the module- and section-level
        # comments on why this ordering is the actual fix for the
        # audit-reported KDF/HMAC precedence issue.
        "family": "kdf",
        "category": "key-derivation",
        "purpose": ["key-derivation"],
        "quantum_status": "contextual",
        "risk_reason": (
            "Key-derivation security depends on the underlying primitive, "
            "parameters and application context rather than on a single "
            "quantum-vulnerability classification."
        ),
        "aliases": {
            "KDF", "PBKDF", "PBKDF2", "HKDF",
            "SCRYPT", "BCRYPT", "ARGON2", "ARGON2I", "ARGON2D", "ARGON2ID",
        },
        "patterns": [
            _rx(r"KDF"),
            _rx(r"^PBKDF2?\b"),
            _rx(r"^SCRYPT\b"),
            _rx(r"^BCRYPT\b"),
            _rx(r"^ARGON2"),
        ],
    },
    {
        "family": "mac",
        "category": "mac",
        "purpose": ["message-authentication"],
        "quantum_status": "quantum-aware",
        "risk_reason": (
            "MAC security depends on the underlying primitive and key "
            "size and should be assessed in context."
        ),
        "aliases": {"HMAC", "CMAC", "GMAC", "POLY1305"},
        "patterns": [_rx(r"^HMAC\b"), _rx(r"^CMAC\b"), _rx(r"^GMAC\b"), _rx(r"^POLY1305\b")],
    },
    {
        "family": "mgf",
        "category": "cryptographic-component",
        "purpose": ["mask-generation"],
        "quantum_status": "contextual",
        "risk_reason": (
            "MGF1 is a cryptographic construction component and should "
            "be assessed together with the construction in which it is "
            "used."
        ),
        "aliases": {"MGF1"},
        "patterns": [_rx(r"^MGF1$")],
    },
    {
        "family": "protocol-tls",
        "category": "protocol",
        "purpose": ["secure-communication"],
        "quantum_status": "contextual",
        "risk_reason": (
            "Protocol quantum safety depends on the cryptographic "
            "algorithms and key-exchange mechanisms actually negotiated "
            "by the protocol."
        ),
        "aliases": {"TLS", "SSL"},
        "patterns": [_rx(r"^(TLS|SSL)\d*$")],
    },
    {
        "family": "raw-format",
        "category": "cryptographic-format",
        "purpose": ["raw-cryptographic-representation"],
        "quantum_status": "contextual",
        "risk_reason": (
            "RAW describes a cryptographic representation or format "
            "rather than identifying a specific primitive. Quantum risk "
            "must be determined from the underlying cryptographic "
            "operation."
        ),
        "aliases": {"RAW"},
        "patterns": [_rx(r"^RAW$")],
    },
]


# ----------------------------------------------------------------
# AES is handled separately (not as a plain CRYPTO_FAMILIES entry)
# because it is the one family whose displayed quantum_status
# genuinely depends on a parameter recorded in the name -- key size --
# rather than on which family it is. Folding a per-parameter branch
# into the generic engine above would have made every other family's
# entry carry unused "variant" plumbing; keeping it as one small,
# explicit, well-tested function is the smaller, more readable design.
# ----------------------------------------------------------------

_AES_NAME_RE = _rx(r"^AES\b")
_AES_KEY_SIZE_RE = _rx(r"AES[-_]?(\d{3})\b")


def _classify_aes(normalized_name):
    match = _AES_KEY_SIZE_RE.search(normalized_name)
    key_size = match.group(1) if match else None

    if key_size == "256":
        quantum_status = "quantum-resistant"
        reason = (
            "AES-256 provides a substantially stronger security margin "
            "against quantum search (Grover's algorithm) attacks."
        )
    elif key_size in ("128", "192"):
        quantum_status = "reduced-security-margin"
        reason = (
            f"AES-{key_size} retains a reduced security margin against "
            "quantum search (Grover's algorithm) attacks compared with "
            "larger key sizes."
        )
    else:
        # Evidence-driven, not guessed: the name did not record a key
        # size, so this does not assume 128 vs. 256 -- it says so and
        # falls back to the same conservative default the rest of
        # ECDAT has always used for AES with an unspecified key size.
        quantum_status = "reduced-security-margin"
        reason = (
            "AES key size could not be determined from the available "
            "CBOM evidence; assessed conservatively pending confirmation "
            "of the key size."
        )

    return {
        "category": "symmetric",
        "purpose": ["encryption"],
        "quantum_status": quantum_status,
        "risk_reason": reason,
    }


# ================================================================
# ALIAS MAPS (built once at import time)
# ================================================================


def _build_alias_maps(families):
    """
    Flatten every family's aliases into O(1) lookup maps, raising
    immediately if two families ever claim the same alias -- a family
    registry only generalizes safely if "which family owns this exact
    name" is unambiguous by construction, not by if/elif order.
    """

    alias_map = {}
    compact_map = {}

    for family in families:
        for alias in family["aliases"]:
            key = _normalize(alias)
            existing = alias_map.get(key)

            if existing is not None and existing is not family:
                raise ValueError(
                    f"Alias collision: '{alias}' is claimed by both "
                    f"'{existing['family']}' and '{family['family']}'."
                )

            alias_map[key] = family

            compact_key = _compact(key)
            existing_compact = compact_map.get(compact_key)

            if existing_compact is not None and existing_compact is not family:
                raise ValueError(
                    f"Compact alias collision: '{alias}' ('{compact_key}') "
                    f"is claimed by both '{existing_compact['family']}' "
                    f"and '{family['family']}'."
                )

            compact_map[compact_key] = family

    return alias_map, compact_map


_ALIAS_TO_FAMILY, _COMPACT_ALIAS_TO_FAMILY = _build_alias_maps(CRYPTO_FAMILIES)


def _classification_for(family):
    return {
        "category": family["category"],
        "purpose": list(family["purpose"]),
        "quantum_status": family["quantum_status"],
        "risk_reason": family["risk_reason"],
    }


def resolve_family_classification(name):
    """
    Resolve a raw CBOM component name to a classification dict, or
    None if no family recognizes it (the caller is responsible for
    recording that as "unknown" -- this function never guesses).

    Lookup order:
      1. AES (parameter-dependent quantum status -- see _classify_aes).
      2. Exact alias match (case/spacing-insensitive) -- unambiguous,
         collision-checked at import time.
      3. Regex pattern fallback, in CRYPTO_FAMILIES order, for names
         that carry a family token as a prefix/suffix rather than
         matching a known alias outright.
    """

    normalized = _normalize(name)

    if not normalized:
        return None

    if _AES_NAME_RE.match(normalized):
        return _classify_aes(normalized)

    family = _ALIAS_TO_FAMILY.get(normalized)

    if family is None:
        family = _COMPACT_ALIAS_TO_FAMILY.get(_compact(normalized))

    if family is not None:
        return _classification_for(family)

    for family in CRYPTO_FAMILIES:
        for pattern in family["patterns"]:
            if pattern.search(normalized):
                return _classification_for(family)

    return None

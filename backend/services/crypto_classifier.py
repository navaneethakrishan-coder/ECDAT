from knowledge.crypto_knowledge import CRYPTO_KNOWLEDGE


def classify_asset(asset):
    """
    Classify a normalized ECDAT crypto asset.

    Classification order:
    1. Exact knowledge-base match
    2. Pattern-based algorithm matching
    3. Crypto-material classification
    4. Unknown fallback
    """

    name = asset.get("name", "")
    asset_type = asset.get("asset_type")

    # --------------------------------------------------
    # 1. Exact knowledge-base match
    # --------------------------------------------------

    if name in CRYPTO_KNOWLEDGE:

        return {
            **asset,
            "classification": CRYPTO_KNOWLEDGE[name]
        }

    # Case-insensitive exact match
    for algorithm, knowledge in CRYPTO_KNOWLEDGE.items():

        if name.lower() == algorithm.lower():

            return {
                **asset,
                "classification": knowledge
            }

    # --------------------------------------------------
    # 2. RSA-based algorithms
    # --------------------------------------------------

    if "RSA" in name.upper():

        return {
            **asset,
            "classification": {
                "category": "asymmetric",
                "purpose": ["digital-signature"],
                "quantum_status": "vulnerable",
                "risk_reason": (
                    "The asset uses RSA-based cryptography, "
                    "which is vulnerable to sufficiently capable "
                    "quantum attacks."
                )
            }
        }

    # --------------------------------------------------
    # 3. DSA
    # --------------------------------------------------

    if "DSA" in name.upper():

        return {
            **asset,
            "classification": {
                "category": "asymmetric",
                "purpose": ["digital-signature"],
                "quantum_status": "vulnerable",
                "risk_reason": (
                    "The asset uses DSA-based public-key cryptography, "
                    "which is vulnerable to quantum attacks."
                )
            }
        }

    # --------------------------------------------------
    # 4. Elliptic Curve
    # --------------------------------------------------

    if name.upper() == "EC":

        return {
            **asset,
            "classification": {
                "category": "asymmetric",
                "purpose": ["public-key-cryptography"],
                "quantum_status": "vulnerable",
                "risk_reason": (
                    "Elliptic-curve cryptography is vulnerable "
                    "to sufficiently capable quantum attacks."
                )
            }
        }

    # --------------------------------------------------
    # 5. AES family
    # --------------------------------------------------

    if name.upper().startswith("AES"):

        return {
            **asset,
            "classification": {
                "category": "symmetric",
                "purpose": ["encryption"],
                "quantum_status": "reduced-security-margin",
                "risk_reason": (
                    "Symmetric cryptography is affected by quantum "
                    "search attacks, resulting in a reduced security margin."
                )
            }
        }

    # --------------------------------------------------
    # 6. Hash algorithms
    # --------------------------------------------------

    if name.upper() in ["MD5", "SHA1"]:

        return {
            **asset,
            "classification": {
                "category": "hash",
                "purpose": ["hash"],
                "quantum_status": "weak",
                "risk_reason": (
                    f"{name} is considered cryptographically weak "
                    "for modern security applications."
                )
            }
        }

    # --------------------------------------------------
    # 7. HMAC
    # --------------------------------------------------

    if "HMAC" in name.upper():

        return {
            **asset,
            "classification": {
                "category": "mac",
                "purpose": ["message-authentication"],
                "quantum_status": "quantum-aware",
                "risk_reason": (
                    "HMAC security depends on its underlying hash "
                    "function, key size and usage context."
                )
            }
        }

    # --------------------------------------------------
    # 8. MGF1
    # --------------------------------------------------

    if name.upper() == "MGF1":

        return {
            **asset,
            "classification": {
                "category": "cryptographic-component",
                "purpose": ["mask-generation"],
                "quantum_status": "contextual",
                "risk_reason": (
                    "MGF1 is a cryptographic construction component "
                    "and should be assessed together with the construction "
                    "in which it is used."
                )
            }
        }

    # --------------------------------------------------
    # 9. KDF
    # --------------------------------------------------

    if "KDF" in name.upper():

        return {
            **asset,
            "classification": {
                "category": "key-derivation",
                "purpose": ["key-derivation"],
                "quantum_status": "contextual",
                "risk_reason": (
                    "Key derivation security depends on the underlying "
                    "primitive, parameters and application context."
                )
            }
        }

    # --------------------------------------------------
    # 10. TLS
    # --------------------------------------------------

    if name.upper() == "TLS":

        return {
            **asset,
            "classification": {
                "category": "protocol",
                "purpose": ["secure-communication"],
                "quantum_status": "contextual",
                "risk_reason": (
                    "TLS quantum safety depends on the cryptographic "
                    "algorithms and key exchange mechanisms used by the protocol."
                )
            }
        }

    # --------------------------------------------------
    # 11. RAW
    # --------------------------------------------------

    if name.upper() == "RAW":

        return {
            **asset,
            "classification": {
                "category": "cryptographic-format",
                "purpose": ["raw-cryptographic-representation"],
                "quantum_status": "contextual",
                "risk_reason": (
                    "RAW describes a cryptographic representation or "
                    "format rather than identifying a specific primitive. "
                    "Quantum risk must be determined from the underlying "
                    "cryptographic operation."
                )
            }
        }

    # --------------------------------------------------
    # 12. Related cryptographic material
    # --------------------------------------------------

    if asset_type == "related-crypto-material":

        if name.startswith("public-key@"):
            material_type = "public-key"

        elif name.startswith("private-key@"):
            material_type = "private-key"

        elif name.startswith("secret-key@"):
            material_type = "secret-key"

        elif name.startswith("key@"):
            material_type = "key"

        else:
            material_type = "cryptographic-material"

        return {
            **asset,
            "classification": {
                "category": "crypto-material",
                "purpose": [material_type],
                "quantum_status": "contextual",
                "risk_reason": (
                    "The cryptographic material must be associated "
                    "with its governing algorithm before quantum risk "
                    "can be determined."
                )
            }
        }

    # --------------------------------------------------
    # 13. Unknown
    # --------------------------------------------------

    return {
        **asset,
        "classification": {
            "category": "unknown",
            "purpose": [],
            "quantum_status": "unknown",
            "risk_reason": (
                "No classification rule currently matches this asset."
            )
        }
    }
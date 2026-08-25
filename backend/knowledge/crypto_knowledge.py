CRYPTO_KNOWLEDGE = {

    # -------------------------
    # Public Key / Asymmetric
    # -------------------------

    "RSA": {
        "category": "asymmetric",
        "purpose": [
            "encryption",
            "digital-signature"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "RSA relies on integer factorization, which is vulnerable to sufficiently capable quantum computers."
    },

    "RSA-2048": {
        "category": "asymmetric",
        "purpose": [
            "encryption",
            "digital-signature"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "RSA-2048 is vulnerable to quantum attacks based on Shor's algorithm."
    },

    "ECDH": {
        "category": "asymmetric",
        "purpose": [
            "key-agreement"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "Elliptic-curve key agreement is vulnerable to sufficiently capable quantum computers."
    },

    "ECDSA": {
        "category": "asymmetric",
        "purpose": [
            "digital-signature"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "ECDSA relies on elliptic-curve discrete logarithm assumptions that are vulnerable to quantum attacks."
    },

    "DSA": {
        "category": "asymmetric",
        "purpose": [
            "digital-signature"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "DSA relies on discrete logarithm assumptions vulnerable to quantum attacks."
    },

    "EdDSA": {
        "category": "asymmetric",
        "purpose": [
            "digital-signature"
        ],
        "quantum_status": "vulnerable",
        "risk_reason": "EdDSA is based on elliptic-curve cryptography and is vulnerable to sufficiently capable quantum computers."
    },

    # -------------------------
    # Symmetric
    # -------------------------

    "AES-128": {
        "category": "symmetric",
        "purpose": [
            "encryption"
        ],
        "quantum_status": "reduced-security-margin",
        "risk_reason": "Quantum search provides a theoretical security reduction compared with classical brute force."
    },

    "AES-256": {
        "category": "symmetric",
        "purpose": [
            "encryption"
        ],
        "quantum_status": "quantum-resistant",
        "risk_reason": "AES-256 provides a substantially stronger security margin against quantum search attacks."
    },

    # -------------------------
    # Hash
    # -------------------------

    "SHA1": {
        "category": "hash",
        "purpose": [
            "hash"
        ],
        "quantum_status": "weak",
        "risk_reason": "SHA-1 is already considered cryptographically weak and should not be used for modern security applications."
    },

    "SHA256": {
        "category": "hash",
        "purpose": [
            "hash"
        ],
        "quantum_status": "quantum-aware",
        "risk_reason": "SHA-256 remains useful with a reduced theoretical security margin against quantum search."
    },

    "SHA384": {
        "category": "hash",
        "purpose": [
            "hash"
        ],
        "quantum_status": "quantum-aware",
        "risk_reason": "SHA-384 provides a stronger hash security margin against quantum search."
    },

    "SHA512": {
        "category": "hash",
        "purpose": [
            "hash"
        ],
        "quantum_status": "quantum-aware",
        "risk_reason": "SHA-512 provides a strong hash security margin against quantum search."
    },

    # -------------------------
    # MAC
    # -------------------------

    "HMAC-SHA256": {
        "category": "mac",
        "purpose": [
            "message-authentication"
        ],
        "quantum_status": "quantum-aware",
        "risk_reason": "HMAC security depends on the underlying hash and key size and should be assessed in context."
    },

    "HMAC-SHA512": {
        "category": "mac",
        "purpose": [
            "message-authentication"
        ],
        "quantum_status": "quantum-aware",
        "risk_reason": "HMAC-SHA512 provides a strong security margin but should still be assessed in context."
    }
}
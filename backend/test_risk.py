from services.risk_engine import calculate_base_risk


def test_rsa():

    asset = {
        "name": "RSA-2048",
        "classification": {
            "category": "asymmetric",
            "quantum_status": "vulnerable"
        }
    }

    result = calculate_base_risk(asset)

    print("\nRSA-2048")
    print(result)

    assert result["score"] == 100
    assert result["severity"] == "CRITICAL"


def test_sha1():

    asset = {
        "name": "SHA1",
        "classification": {
            "category": "hash",
            "quantum_status": "weak"
        }
    }

    result = calculate_base_risk(asset)

    print("\nSHA1")
    print(result)

    assert result["score"] == 85
    assert result["severity"] == "CRITICAL"


def test_aes():

    asset = {
        "name": "AES128",
        "classification": {
            "category": "symmetric",
            "quantum_status": "reduced-security-margin"
        }
    }

    result = calculate_base_risk(asset)

    print("\nAES128")
    print(result)

    assert result["score"] == 50
    assert result["severity"] == "MEDIUM"


if __name__ == "__main__":

    test_rsa()
    test_sha1()
    test_aes()

    print("\nAll risk tests passed.")
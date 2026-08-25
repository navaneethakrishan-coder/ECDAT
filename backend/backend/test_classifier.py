from services.crypto_classifier import classify_asset


def test_ecdh():

    asset = {
        "name": "ECDH",
        "asset_type": "algorithm",
        "primitive": "key-agree"
    }

    result = classify_asset(asset)

    assert result["classification"]["category"] == "asymmetric"

    assert (
        result["classification"]["quantum_status"]
        == "vulnerable"
    )


def test_sha1():

    asset = {
        "name": "SHA1",
        "asset_type": "algorithm",
        "primitive": "hash"
    }

    result = classify_asset(asset)

    assert result["classification"]["category"] == "hash"


def test_unknown():

    asset = {
        "name": "UNKNOWN-CRYPTO"
    }

    result = classify_asset(asset)

    assert (
        result["classification"]["quantum_status"]
        == "unknown"
    )


if __name__ == "__main__":

    test_ecdh()
    test_sha1()
    test_unknown()

    print("All tests passed.")
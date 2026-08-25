from services.evidence_confidence import calculate_evidence_confidence


def test_high_confidence():

    asset = {
        "name": "ECDH",
        "occurrences": [
            {
                "location": "example/A.java",
                "line": 183,
                "additionalContext": "KeyAgreement#getInstance"
            },
            {
                "location": "example/B.java",
                "line": 208,
                "additionalContext": "KeyAgreement#getInstance"
            }
        ]
    }

    result = calculate_evidence_confidence(asset)

    print("\nHigh-confidence evidence:")
    print(result)

    assert result["score"] == 100
    assert result["confidence"] == "HIGH"


def test_low_confidence():

    asset = {
        "name": "UNKNOWN",
        "occurrences": []
    }

    result = calculate_evidence_confidence(asset)

    print("\nLow-confidence evidence:")
    print(result)

    assert result["score"] == 0
    assert result["confidence"] == "LOW"


if __name__ == "__main__":

    test_high_confidence()
    test_low_confidence()

    print("\nAll evidence-confidence tests passed.")
from services.pqc_registry import (
    get_pqc_algorithms,
    find_pqc_algorithm,
    get_algorithms_by_family
)


def test_pqc_registry():

    print()
    print("================================")
    print("PQC REGISTRY TEST")
    print("================================")

    algorithms = get_pqc_algorithms()

    print(
        "Total algorithms:",
        len(algorithms)
    )

    assert len(algorithms) == 7

    ml_kem = find_pqc_algorithm(
        "ML-KEM-768"
    )

    assert ml_kem is not None
    assert ml_kem["standard"] == "FIPS 203"
    assert ml_kem["family"] == "KEM"
    assert ml_kem["standardization_status"] == "final"

    ml_dsa = find_pqc_algorithm(
        "ML-DSA-65"
    )

    assert ml_dsa is not None
    assert ml_dsa["standard"] == "FIPS 204"
    assert ml_dsa["family"] == "digital-signature"
    assert ml_dsa["standardization_status"] == "final"

    slh_dsa = find_pqc_algorithm(
        "SLH-DSA"
    )

    assert slh_dsa is not None
    assert slh_dsa["standard"] == "FIPS 205"
    assert slh_dsa["family"] == "digital-signature"

    kem_algorithms = get_algorithms_by_family(
        "KEM"
    )

    signature_algorithms = get_algorithms_by_family(
        "digital-signature"
    )

    assert len(kem_algorithms) == 3
    assert len(signature_algorithms) == 4

    print()
    print("Registered algorithms:")

    for algorithm in algorithms:
        print(
            f"{algorithm['name']} | "
            f"{algorithm['standard']} | "
            f"{algorithm['family']} | "
            f"{algorithm['standardization_status']}"
        )

    print()
    print("KEM algorithms:", len(kem_algorithms))
    print(
        "Signature algorithms:",
        len(signature_algorithms)
    )

    print()
    print("PQC registry test passed.")


if __name__ == "__main__":
    test_pqc_registry()
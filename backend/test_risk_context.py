import json
import tempfile
from pathlib import Path

import services.business_context as business_context
from services.risk_context import (
    derive_risk_context,
    DEFAULT_QUANTUM_THREAT_HORIZON_YEARS,
)


def _occurrence(location, context="", line=1):
    return {"location": location, "line": line, "offset": 0, "context": context}


def _use_config(config_dict, test_fn):
    """
    Point services.business_context at a throwaway config file for
    the duration of `test_fn`, then restore the real config path --
    same helper as test_business_context.py, duplicated locally so
    this file stays independently runnable.
    """

    original_path = business_context.CONFIG_PATH

    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "business-context.json"
        config_path.write_text(json.dumps(config_dict), encoding="utf-8")

        business_context.CONFIG_PATH = config_path
        business_context.reload_config()

        try:
            test_fn()
        finally:
            business_context.CONFIG_PATH = original_path
            business_context.reload_config()


def test_network_exposure_detected_from_evidence():
    """
    An asset whose only evidence is in an SSH-related source file
    should be classified INTERNET-exposed -- a real signal (the file
    path CBOMKit recorded), not a guess.
    """

    asset = {
        "name": "DSA",
        "asset_type": "algorithm",
        "classification": {"category": "asymmetric"},
        "occurrences": [
            _occurrence("src/cryptography/hazmat/primitives/serialization/ssh.py"),
        ],
    }

    context = derive_risk_context(asset)

    print("\n==============================")
    print("RISK CONTEXT: network exposure")
    print("==============================")
    print(context)

    assert context.exposure == "INTERNET"


def test_purely_local_evidence_stays_internal():
    """
    An asset with no network-related evidence at all should default
    to INTERNAL exposure, matching the prior universal default for
    the ambiguous/common case.
    """

    asset = {
        "name": "SHAKE256",
        "asset_type": "algorithm",
        "classification": {"category": "hash"},
        "occurrences": [
            _occurrence("src/cryptography/hazmat/primitives/twofactor/totp.py", context="generate"),
        ],
    }

    context = derive_risk_context(asset)

    print("\n==============================")
    print("RISK CONTEXT: internal-only evidence")
    print("==============================")
    print(context)

    assert context.exposure == "INTERNAL"


def test_test_vector_only_asset_is_low_criticality():
    """
    An asset that only ever occurs in test/demo/doc paths (test
    vectors, sample generators) should be treated as LOW business
    criticality -- it is not shipped production code.
    """

    asset = {
        "name": "RSA-OAEP",
        "asset_type": "algorithm",
        "classification": {"category": "asymmetric"},
        "occurrences": [
            _occurrence("docs/development/custom-vectors/rsa-oaep-sha2/VerifyRSAOAEPSHA2.java"),
            _occurrence("docs/development/custom-vectors/rsa-oaep-sha2/generate_rsa_oaep_sha2.py"),
        ],
    }

    context = derive_risk_context(asset)

    print("\n==============================")
    print("RISK CONTEXT: test-vector-only asset")
    print("==============================")
    print(context)

    assert context.business_criticality == "LOW"


def test_widely_used_asset_is_high_criticality():
    """
    An asset recurring across many distinct evidence locations (none
    of them test/demo/doc paths) is more deeply embedded in the
    codebase, and should be treated as HIGH business criticality.
    """

    asset = {
        "name": "AES128",
        "asset_type": "algorithm",
        "classification": {"category": "symmetric"},
        "occurrences": [
            _occurrence(f"src/cryptography/module_{i}.py")
            for i in range(6)
        ],
    }

    context = derive_risk_context(asset)

    print("\n==============================")
    print("RISK CONTEXT: widely-used asset")
    print("==============================")
    print(context)

    assert context.business_criticality == "HIGH"


def test_ambiguous_asset_defaults_to_medium_criticality():
    """
    An asset with a handful of production-path occurrences -- not
    test-only, not numerous enough to be HIGH -- keeps the sensible
    middle-ground default, matching the prior universal default.
    """

    asset = {
        "name": "DH",
        "asset_type": "algorithm",
        "classification": {"category": "unknown"},
        "occurrences": [
            _occurrence("src/cryptography/hazmat/primitives/asymmetric/dsa.py"),
        ],
    }

    context = derive_risk_context(asset)

    print("\n==============================")
    print("RISK CONTEXT: ambiguous asset")
    print("==============================")
    print(context)

    assert context.business_criticality == "MEDIUM"


def test_migration_time_scales_with_usage_and_category():
    """
    migration_time_years should grow with how many places the asset
    occurs (more integration points to change), and slow-to-migrate
    categories (asymmetric/protocol, which typically involve
    cross-party interoperability) should add to that.
    """

    light_asset = {
        "name": "light",
        "classification": {"category": "hash"},
        "occurrences": [_occurrence("src/a.py")],
    }

    heavy_asymmetric_asset = {
        "name": "heavy",
        "classification": {"category": "asymmetric"},
        "occurrences": [_occurrence(f"src/f{i}.py") for i in range(8)],
    }

    light_context = derive_risk_context(light_asset)
    heavy_context = derive_risk_context(heavy_asymmetric_asset)

    print("\n==============================")
    print("RISK CONTEXT: migration time scaling")
    print("==============================")
    print("light:", light_context.migration_time_years)
    print("heavy asymmetric:", heavy_context.migration_time_years)

    assert light_context.migration_time_years == 1
    assert heavy_context.migration_time_years > light_context.migration_time_years


def test_deterministic_for_identical_input():
    """
    The same asset record must always derive the exact same context
    -- no randomness, no hidden state.
    """

    asset = {
        "name": "RSA-2048",
        "asset_type": "algorithm",
        "classification": {"category": "asymmetric"},
        "occurrences": [_occurrence("src/cryptography/x.py")],
    }

    first = derive_risk_context(asset)
    second = derive_risk_context(dict(asset))

    assert first == second


def test_quantum_threat_horizon_is_not_derived_per_asset():
    """
    quantum_threat_horizon_years is a documented, fixed threat-model
    assumption -- not something a CBOM can reveal -- so every asset
    must get the same value regardless of its evidence.
    """

    network_asset = {
        "name": "a",
        "occurrences": [_occurrence("src/ssh.py")],
    }

    local_asset = {
        "name": "b",
        "occurrences": [_occurrence("src/hash.py")],
    }

    a = derive_risk_context(network_asset)
    b = derive_risk_context(local_asset)

    assert (
        a.quantum_threat_horizon_years
        == b.quantum_threat_horizon_years
        == DEFAULT_QUANTUM_THREAT_HORIZON_YEARS
    )


def test_data_lifetime_is_unknown_without_business_context():
    """
    data_lifetime_years must NOT be a fixed default like
    quantum_threat_horizon_years above -- it is an organizational
    fact (how long THIS finding's protected data must stay
    confidential) that no CBOM evidence and no shared assumption can
    supply. Without any data/business-context.json entry, it must be
    None (UNKNOWN) for every asset -- never silently 5, 0, or any
    other guessed number, regardless of how different their evidence
    otherwise is.
    """

    def check():
        network_asset = {
            "name": "a",
            "bom_ref": "no-config-ref-a",
            "occurrences": [_occurrence("src/ssh.py")],
        }

        local_asset = {
            "name": "b",
            "bom_ref": "no-config-ref-b",
            "occurrences": [_occurrence("src/hash.py")],
        }

        a = derive_risk_context(network_asset)
        b = derive_risk_context(local_asset)

        assert a.data_lifetime_years is None
        assert b.data_lifetime_years is None

    _use_config({}, check)


def test_data_lifetime_uses_explicit_per_finding_configuration():
    """
    Tier 2 of the evidence-priority chain: an explicit
    data/business-context.json "findings"."<bom_ref>" entry, looked
    up by the finding's own bom_ref (never by algorithm name).
    """

    def check():
        asset = {"name": "RSA-OAEP", "bom_ref": "configured-ref", "occurrences": []}

        context = derive_risk_context(asset)

        assert context.data_lifetime_years == 20.0

    _use_config(
        {"findings": {"configured-ref": {"data_lifetime_years": 20}}},
        check,
    )


def test_data_lifetime_falls_back_to_repository_default():
    """
    Tier 3: a repository-wide "default" entry applies to any finding
    without its own explicit override.
    """

    def check():
        unconfigured_asset = {"name": "AES", "bom_ref": "no-specific-entry", "occurrences": []}

        context = derive_risk_context(unconfigured_asset)

        assert context.data_lifetime_years == 8.0

    _use_config({"default": {"data_lifetime_years": 8}}, check)


def test_duplicate_algorithm_name_findings_get_independent_data_lifetime():
    """
    Two findings that would display with the same algorithm name but
    have different bom_refs must resolve independently -- lookups are
    keyed by bom_ref, never by name (see services/business_context.py).
    """

    def check():
        finding_a = {"name": "RSA-2048", "bom_ref": "rsa-2048-a", "occurrences": []}
        finding_b = {"name": "RSA-2048", "bom_ref": "rsa-2048-b", "occurrences": []}

        context_a = derive_risk_context(finding_a)
        context_b = derive_risk_context(finding_b)

        assert context_a.data_lifetime_years == 30.0
        assert context_b.data_lifetime_years is None

    _use_config(
        {"findings": {"rsa-2048-a": {"data_lifetime_years": 30}}},
        check,
    )


if __name__ == "__main__":

    test_network_exposure_detected_from_evidence()
    test_purely_local_evidence_stays_internal()
    test_test_vector_only_asset_is_low_criticality()
    test_widely_used_asset_is_high_criticality()
    test_ambiguous_asset_defaults_to_medium_criticality()
    test_migration_time_scales_with_usage_and_category()
    test_deterministic_for_identical_input()

    test_quantum_threat_horizon_is_not_derived_per_asset()
    test_data_lifetime_is_unknown_without_business_context()
    test_data_lifetime_uses_explicit_per_finding_configuration()
    test_data_lifetime_falls_back_to_repository_default()
    test_duplicate_algorithm_name_findings_get_independent_data_lifetime()

    print("\nAll risk-context tests passed.")

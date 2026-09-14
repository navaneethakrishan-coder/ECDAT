"""
Derives a per-asset RiskContext from real CBOM evidence, instead of
one hardcoded RiskContext shared identically by every asset in every
analyzed repository (the previous behavior -- see
docs/ARCHITECTURE.md, "RiskContext contextualization").

Design constraints this module was built under:
  - Deterministic: the same asset record always derives the same
    context. No randomness, no external calls.
  - Grounded only in fields already present in
    ecdat-classified-assets.json (CBOM evidence occurrences +
    classification) -- nothing invented, and nothing that would
    create a dependency on a later pipeline stage (this runs inside
    explain_cbom.py, the first and only risk-calculation stage).
  - Two RiskContext dimensions are intentionally left as fixed,
    documented defaults rather than forced to vary per asset:
    `data_lifetime_years` (how long the data a given algorithm
    protects must stay confidential) and
    `quantum_threat_horizon_years` (when a cryptographically-relevant
    quantum computer is expected to exist). Neither is a fact a CBOM
    can reveal -- they are organizational/threat-model assumptions
    about the future, not observations about the code. Fabricating a
    per-asset value for either would be inventing an arbitrary score
    to look more "contextual," which is exactly what this module was
    asked not to do.

The three dimensions that DO vary per asset -- `business_criticality`,
`exposure`, and `migration_time_years` -- are derived from real,
observable CBOM evidence: the file paths and API-usage strings CBOMKit
already recorded for every occurrence of the asset, plus how many
occurrences there are, plus the asset's own classification category.
"""

from models.risk_factors import RiskContext


# ----------------------------------------------------------------
# Fixed, documented threat-model assumptions.
#
# These are NOT derived from the repository being analyzed -- see
# the module docstring for why. They previously lived as duplicated
# hardcoded literals inside score_contextual_cbom.py and
# explain_cbom.py; centralizing them here means there is exactly one
# place to change the organization's assumed data-retention window or
# quantum-threat horizon, applied uniformly and transparently instead
# of being silently baked into a "contextual" number.
# ----------------------------------------------------------------

DEFAULT_DATA_LIFETIME_YEARS = 5
DEFAULT_QUANTUM_THREAT_HORIZON_YEARS = 10


# ----------------------------------------------------------------
# Real signals used to derive `exposure`.
#
# Matched against the lowercased occurrence location (file path) and
# context (API-usage string) CBOMKit already recorded as evidence for
# each asset. Presence of any of these strongly suggests the asset is
# involved in network-facing communication (TLS/SSH handshakes,
# certificate-based authentication, raw sockets/HTTP) rather than
# purely local/internal use.
# ----------------------------------------------------------------

NETWORK_EXPOSURE_KEYWORDS = (
    "ssl",
    "tls",
    "ssh",
    "socket",
    "https",
    "http",
    "x509",
    "certificate",
    "handshake",
    "net.",
)

# CycloneDX/CBOM asset types that are inherently network protocols or
# network-identity material, regardless of where they occur.
NETWORK_ASSET_TYPES = (
    "protocol",
    "certificate",
)


# ----------------------------------------------------------------
# Real signals used to derive `business_criticality`.
#
# File-path segments conventionally used for test fixtures, sample
# code, generated test vectors, and documentation -- as opposed to
# shipped production source. An asset that only ever appears in such
# paths is far less business-critical than one embedded in the
# project's actual source tree.
# ----------------------------------------------------------------

LOW_CRITICALITY_PATH_KEYWORDS = (
    "test",
    "tests",
    "docs/",
    "doc/",
    "example",
    "examples",
    "demo",
    "sample",
    "samples",
    "fixture",
    "fixtures",
    "vector",
    "vectors",
)

# An asset that recurs across many distinct evidence locations is
# more deeply embedded in the codebase -- more callers depend on it,
# so treat it as higher business criticality than an asset that
# occurs once or twice.
HIGH_USAGE_OCCURRENCE_THRESHOLD = 5


# ----------------------------------------------------------------
# Real signal used to derive `migration_time_years`.
#
# Categories whose real-world migrations typically involve
# cross-party interoperability (certificate chains, protocol
# negotiation, key-exchange partners) tend to take longer to migrate
# than a purely internal hash or symmetric-key usage.
# ----------------------------------------------------------------

SLOW_MIGRATION_CATEGORIES = (
    "asymmetric",
    "protocol",
)


def _occurrence_texts(asset):
    """Lowercased (location, context) strings for every occurrence."""

    texts = []

    for occurrence in asset.get("occurrences") or []:

        location = str(occurrence.get("location") or "").lower()
        context = str(occurrence.get("context") or "").lower()

        texts.append(location)
        texts.append(context)

    return texts


def _derive_exposure(asset, texts):

    asset_type = str(asset.get("asset_type") or "").lower()

    if any(keyword in asset_type for keyword in NETWORK_ASSET_TYPES):
        return "INTERNET"

    for text in texts:
        if any(keyword in text for keyword in NETWORK_EXPOSURE_KEYWORDS):
            return "INTERNET"

    return "INTERNAL"


def _derive_business_criticality(asset):

    occurrences = asset.get("occurrences") or []

    if occurrences:

        locations = [
            str(occurrence.get("location") or "").lower()
            for occurrence in occurrences
        ]

        only_low_signal_paths = all(
            any(
                keyword in location
                for keyword in LOW_CRITICALITY_PATH_KEYWORDS
            )
            for location in locations
        )

        if only_low_signal_paths:
            return "LOW"

    if len(occurrences) >= HIGH_USAGE_OCCURRENCE_THRESHOLD:
        return "HIGH"

    return "MEDIUM"


def _derive_migration_time_years(asset):

    occurrence_count = len(asset.get("occurrences") or [])

    if occurrence_count <= 2:
        years = 1

    elif occurrence_count <= 6:
        years = 2

    else:
        years = 4

    category = str(
        asset.get("classification", {}).get("category") or ""
    ).lower()

    if category in SLOW_MIGRATION_CATEGORIES:
        years += 1

    return min(years, 10)


def derive_risk_context(asset):
    """
    Build a RiskContext for one asset from that asset's own CBOM
    evidence, so "contextual risk" actually reflects the analyzed
    project instead of one fixed value shared by every asset in
    every repository.
    """

    texts = _occurrence_texts(asset)

    return RiskContext(
        business_criticality=_derive_business_criticality(asset),
        data_lifetime_years=DEFAULT_DATA_LIFETIME_YEARS,
        migration_time_years=_derive_migration_time_years(asset),
        exposure=_derive_exposure(asset, texts),
        quantum_threat_horizon_years=DEFAULT_QUANTUM_THREAT_HORIZON_YEARS,
    )

"""
Derives a per-asset RiskContext from real CBOM evidence, instead of
one hardcoded RiskContext shared identically by every asset in every
analyzed repository (the previous behavior -- see
docs/ARCHITECTURE.md, "RiskContext contextualization").

Design constraints this module was built under:
  - Deterministic: the same asset record always derives the same
    context (aside from `data_lifetime_years`, which additionally
    depends on the optional, explicitly-provided
    data/business-context.json -- see services/business_context.py --
    itself deterministic for a given bom_ref).
  - Grounded only in fields already present in
    ecdat-classified-assets.json (CBOM evidence occurrences +
    classification) plus that optional business-context config --
    nothing invented, and nothing that would create a dependency on a
    later pipeline stage (this runs inside explain_cbom.py, the first
    and only risk-calculation stage).
  - `quantum_threat_horizon_years` is intentionally left as a fixed,
    documented default rather than forced to vary per asset: it is a
    shared, organization-independent estimate of when a
    cryptographically-relevant quantum computer is expected to exist
    -- not a fact a CBOM can reveal, and not something specific to
    this repository or finding either, unlike data lifetime (below).
    Fabricating a per-asset value for it would be inventing an
    arbitrary score to look more "contextual," which is exactly what
    this module was asked not to do.
  - `data_lifetime_years` (how long the data a given finding protects
    must stay confidential) is NOT a fixed default -- see below.

The three evidence-derived dimensions -- `business_criticality`,
`exposure`, and `migration_time_years` -- come from real, observable
CBOM evidence: the file paths and API-usage strings CBOMKit already
recorded for every occurrence of the asset, plus how many occurrences
there are, plus the asset's own classification category.

`data_lifetime_years` follows a DIFFERENT, explicit evidence-priority
chain (reusing services/business_context.py rather than building a
second, competing mechanism -- see that module's own docstring):

  1. Explicit repository/CBOM/source evidence -- not currently
     available: no CBOM property or source signal states how long
     protected data must remain confidential, and this module does
     not invent one (a data-retention requirement is an
     organizational/business fact, not something observable in code
     the way exposure or business-criticality proxies are).
  2. Explicit per-finding business-context configuration
     (data/business-context.json's "findings"."<bom_ref>" entry).
  3. Repository-wide configured default (that same file's "default"
     entry).
  4. UNKNOWN (None) when none of the above apply -- never silently
     replaced with a guessed number. This was previously a hardcoded
     `5` applied identically to every finding in every repository;
     see docs/CHANGELOG.md for the audit that found it.

services/business_context.get_data_lifetime_years(bom_ref) already
implements steps 2-4 (per-bom_ref lookup, falling back to the
config's repository-wide default, else None) -- reused verbatim here,
not reimplemented.
"""

from models.risk_factors import RiskContext
from services.business_context import (
    DEFAULT_QUANTUM_THREAT_HORIZON_YEARS,
    get_data_lifetime_years,
)


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

    `data_lifetime_years` is looked up by this asset's own bom_ref
    (the canonical finding identity used everywhere in ECDAT -- never
    joined by algorithm name) via services/business_context.py, and
    is None (UNKNOWN) unless an organization has explicitly
    configured it in data/business-context.json. See this module's
    own docstring for the full evidence-priority chain.
    """

    texts = _occurrence_texts(asset)

    return RiskContext(
        business_criticality=_derive_business_criticality(asset),
        data_lifetime_years=get_data_lifetime_years(asset.get("bom_ref")),
        migration_time_years=_derive_migration_time_years(asset),
        exposure=_derive_exposure(asset, texts),
        quantum_threat_horizon_years=DEFAULT_QUANTUM_THREAT_HORIZON_YEARS,
    )

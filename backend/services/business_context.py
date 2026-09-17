"""
Optional, organization-provided business-context signals for the
migration-priority model: business criticality and confidentiality
data lifetime, keyed by bom_ref -- the canonical finding identity
used throughout ECDAT.

WHY THIS EXISTS: no static analysis of a repository's source code can
tell you how important a given cryptographic finding is to an
organization's *business*, or how many years the data it protects
must stay confidential -- those are organizational/threat-model facts
that live outside the code, not technical facts a CBOM scan can
observe. (Contrast this with services/risk_context.py's
`migration_time_years`/`exposure`, which genuinely ARE derived from
observable CBOM evidence -- occurrence file paths, API-usage context,
occurrence counts -- and are reused here rather than duplicated.)

Rather than fabricate a plausible-looking default business
criticality or data lifetime for every finding, both are represented
as UNKNOWN (None) unless an organization explicitly provides them via
the optional data/business-context.json file below. The pipeline runs
completely normally without that file -- every finding is simply
UNKNOWN for these two signals, exactly as honest as no data at all.

data/business-context.json shape (the file itself, and every field in
it, is optional):

{
  "default": {
    "business_criticality": "MEDIUM",
    "data_lifetime_years": 10
  },
  "findings": {
    "<bom_ref>": {
      "business_criticality": "CRITICAL",
      "data_lifetime_years": 25
    }
  }
}

"findings" entries win over "default", which wins over UNKNOWN. This
mirrors the bom_ref-keyed lookup pattern already used everywhere else
in ECDAT (priority/blast-radius/complexity joins) -- never algorithm
name.
"""

import json
from pathlib import Path

from models.risk_factors import RiskContext
from services.mosca_analysis import calculate_mosca_risk


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "data" / "business-context.json"

# Fixed, documented threat-model assumption: a shared,
# organization-independent estimate of when a cryptographically-
# relevant quantum computer is expected to exist. Not a fact any
# repository or organization's config can override on a per-finding
# basis (unlike data_lifetime_years below) -- see
# services/risk_context.py's module docstring for the full reasoning.
# Owned here (rather than in risk_context.py) because
# calculate_mosca_urgency() below is this constant's only consumer;
# risk_context.py imports it from here rather than the reverse, so
# the two modules' import direction stays one-way.
DEFAULT_QUANTUM_THREAT_HORIZON_YEARS = 10

VALID_CRITICALITY_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

# Same 0-100 scale services/contextual_risk.py already uses for
# business criticality, so a criticality level reads the same way
# everywhere ECDAT scores it -- reused, not reinvented.
BUSINESS_CRITICALITY_SCORES = {
    "LOW": 0,
    "MEDIUM": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}

# Same scale services/contextual_risk.py already uses for Mosca
# urgency (computed there but never actually wired into a score --
# this is what wires it in).
MOSCA_URGENCY_SCORES = {
    "LOW": 0,
    "MEDIUM": 60,
    "HIGH": 80,
    "CRITICAL": 100,
}


def _load_config():
    if not CONFIG_PATH.exists():
        return {}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}

    return data if isinstance(data, dict) else {}


_CONFIG_CACHE = None


def _config():
    global _CONFIG_CACHE

    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = _load_config()

    return _CONFIG_CACHE


def reload_config():
    """Force the next lookup to re-read data/business-context.json from disk."""

    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def _entry_for(bom_ref):
    config = _config()

    findings = config.get("findings")
    entry = {}

    if isinstance(findings, dict):
        candidate = findings.get(bom_ref)

        if isinstance(candidate, dict):
            entry = candidate

    default = config.get("default")

    if isinstance(default, dict):
        merged = dict(default)
        merged.update(entry)
        return merged

    return entry


def get_business_criticality(bom_ref):
    """
    Return this finding's organization-provided business criticality
    ("LOW"/"MEDIUM"/"HIGH"/"CRITICAL"), or None if nothing was
    configured for it -- never guessed from the algorithm, its
    category, or the repository.
    """

    entry = _entry_for(bom_ref)
    value = entry.get("business_criticality")

    if isinstance(value, str) and value.strip().upper() in VALID_CRITICALITY_LEVELS:
        return value.strip().upper()

    return None


def get_data_lifetime_years(bom_ref):
    """
    Return this finding's organization-provided confidentiality data
    lifetime in years, or None if nothing was configured for it.
    """

    entry = _entry_for(bom_ref)
    value = entry.get("data_lifetime_years")

    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)

    return None


def calculate_mosca_urgency(bom_ref, migration_time_years):
    """
    Compute Mosca-style migration urgency for one finding, reusing
    services/mosca_analysis.py's existing, already-tested
    calculate_mosca_risk() rather than recomputing the same
    data-lifetime-vs-threat-horizon comparison a second way.

    Returns None (UNKNOWN) whenever data_lifetime_years has not been
    configured for this finding: Mosca urgency is fundamentally a
    question about how long protected data must outlive the
    migration -- with no data-lifetime figure, that question has no
    honest answer, so this never substitutes a fabricated one.
    `migration_time_years` is expected to be the same per-asset value
    services/risk_context.py already derives from real CBOM evidence
    (falls back to 0 only if literally absent, never fabricated
    upward).
    """

    data_lifetime_years = get_data_lifetime_years(bom_ref)

    if data_lifetime_years is None:
        return None

    context = RiskContext(
        data_lifetime_years=data_lifetime_years,
        migration_time_years=migration_time_years if migration_time_years is not None else 0,
        quantum_threat_horizon_years=DEFAULT_QUANTUM_THREAT_HORIZON_YEARS,
    )

    return calculate_mosca_risk(context)

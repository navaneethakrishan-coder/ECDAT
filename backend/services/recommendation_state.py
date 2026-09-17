"""
The migration recommendation as it may be *presented*: derived from the
authoritative purpose-aware migration strategy
(services/migration_strategy.py), never from the ranking model alone.

The PQC ranking model always ranks candidates for a PQC-applicable
finding, including one whose migration strategy is NEEDS_REVIEW. Its
top candidate is ranking output, not a decision: for a NEEDS_REVIEW
finding the cryptographic role is unresolved, so no candidate may be
presented as a recommendation. This module reconciles the plan/report
`recommendation` record with the strategy:

    DIRECT_PQC / HYBRID  confirmed; `selected_component` is the strategy's
                         PQC component
    NEEDS_REVIEW         decision "NEEDS_REVIEW", candidate cleared
    KEEP                 no PQC candidate

The ranking model's own values are never discarded: they are kept,
labelled, under `ranking_model`. Nothing here changes the strategy, the
ranking, or any score -- only how the recommendation record states them.
"""

import copy
from typing import Any, Dict, Iterable, Mapping, Optional


DIRECT_PQC = "DIRECT_PQC"
HYBRID = "HYBRID"
NEEDS_REVIEW = "NEEDS_REVIEW"
KEEP = "KEEP"

MIGRATING_STRATEGIES = (DIRECT_PQC, HYBRID)

_RANKING_FIELDS = (
    "decision",
    "candidate",
    "candidate_rank",
    "candidate_score",
    "confidence",
    "reason",
)

RANKING_MODEL_NOTE = (
    "Output of the PQC candidate-ranking model only. The migration "
    "recommendation is decided by the migration strategy."
)

NEEDS_REVIEW_REASON = (
    "The migration strategy needs review: the evidence does not resolve "
    "this finding's cryptographic role, so no PQC candidate is "
    "recommended. The ranking model's output is kept under ranking_model "
    "for reference only."
)

KEEP_REASON = "No post-quantum migration applies to this finding's role."


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def strategy_name(strategy: Optional[Mapping[str, Any]]) -> Optional[str]:
    return _as_dict(strategy).get("strategy")


def selected_pqc_component(strategy: Optional[Mapping[str, Any]]) -> Optional[str]:
    """The PQC component a DIRECT_PQC/HYBRID strategy selected, else None."""

    strategy = _as_dict(strategy)

    if strategy.get("strategy") in MIGRATING_STRATEGIES:
        return strategy.get("pqc_component") or None

    return None


def has_selected_pqc_path(strategy: Optional[Mapping[str, Any]]) -> bool:
    return selected_pqc_component(strategy) is not None


def reconcile_recommendation(
    recommendation: Optional[Mapping[str, Any]],
    strategy: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    The recommendation record, restated so it cannot contradict the
    strategy. Idempotent: reconciling an already-reconciled record gives
    the same record. Without a strategy (datasets generated before
    strategies existed) the record is returned unchanged.
    """

    record = copy.deepcopy(dict(recommendation or {}))
    name = strategy_name(strategy)

    if not name:
        return record

    ranking = record.get("ranking_model")
    if not isinstance(ranking, dict):
        ranking = {field: record.get(field) for field in _RANKING_FIELDS}
        ranking["note"] = RANKING_MODEL_NOTE

    record["ranking_model"] = ranking
    record["strategy"] = name
    record["selected_component"] = selected_pqc_component(strategy)
    record["confirmed"] = record["selected_component"] is not None

    if name == NEEDS_REVIEW:
        record.update({
            "decision": NEEDS_REVIEW,
            "candidate": None,
            "candidate_rank": None,
            "candidate_score": None,
            "confidence": _as_dict(strategy).get("confidence"),
            "reason": NEEDS_REVIEW_REASON,
        })

    elif name == KEEP:
        record.update({
            "candidate": None,
            "candidate_rank": None,
            "candidate_score": None,
            "reason": record.get("reason") or KEEP_REASON,
        })

    else:
        # DIRECT_PQC / HYBRID: the ranking-derived decision stays; any
        # candidate shown must be the component the strategy selected.
        for field in _RANKING_FIELDS:
            record[field] = ranking.get(field)

        if record.get("candidate") and record["candidate"] != record["selected_component"]:
            record.update({"candidate": None, "candidate_rank": None, "candidate_score": None})

    return record


def count_selected_pqc_paths(strategies: Iterable[Optional[Mapping[str, Any]]]) -> int:
    """Findings whose strategy selected a PQC replacement path (DIRECT_PQC + HYBRID)."""

    return sum(1 for strategy in strategies if has_selected_pqc_path(strategy))

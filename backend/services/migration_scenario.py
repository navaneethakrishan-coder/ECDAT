"""
What-if migration foundation.

Answers "what happens if this finding is migrated to PQC option X?"
for one finding or a set of findings, without mutating the real
finding and without re-running the pipeline. This is the backend/domain
layer behind the What-If Migration Simulator: backend/main.py's
/api/what-if/* endpoints delegate every check and calculation here.

It introduces no new scoring model. It reuses the real engines:
  - services.contextual_risk.calculate_contextual_risk  (risk)
  - services.migration_priority.calculate_migration_priority  (priority)
  - services.migration_strategy decisions  (role and PQC family)
  - data/pqc-algorithms.json via services.pqc_registry  (option validity)

Inputs a what-if cannot honestly change are carried forward unchanged
and labelled as such rather than re-estimated:
  - blast radius: the CBOM dependency graph does not change by picking
    an algorithm; its dependents are reported as findings to migrate
    together.
  - migration complexity: its factors are dependency counts, evidence
    surface and migration time, none of which depend on the chosen
    option.
  - Mosca urgency: it describes the pre-migration timeline.

Both "before" and "after" risk/priority are computed by the same engines
from the same snapshot, so a delta always compares like with like; the
pipeline's recorded values are reported alongside for traceability.
"""

import copy
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from knowledge import migration_strategy_policy as policy
from models.risk_factors import RiskContext
from services.contextual_risk import calculate_contextual_risk
from services.migration_priority import calculate_migration_priority
from services.migration_strategy import DIRECT_PQC, HYBRID, NEEDS_REVIEW
from services.pqc_registry import get_pqc_algorithms


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_RISK_CONTEXT_FIELDS = (
    "business_criticality",
    "data_lifetime_years",
    "migration_time_years",
    "exposure",
    "quantum_threat_horizon_years",
)

_HIGH_PRIORITY_LEVELS = {"HIGH", "CRITICAL"}


@dataclass(frozen=True)
class FindingSnapshot:
    """
    Everything a what-if needs about one finding, deep-copied out of the
    pipeline records. Simulations deep-copy again before any use, so
    neither the snapshot nor the records it was built from are ever
    mutated.
    """

    bom_ref: str
    name: str
    asset: Dict[str, Any]
    risk_context: Dict[str, Any]
    recorded_risk_score: Optional[float]
    recorded_risk_severity: Optional[str]
    blast_radius_score: float
    affected_findings: Tuple[str, ...]
    complexity_score: float
    business_criticality: Optional[str]
    mosca_urgency: Optional[str]
    recorded_priority_score: Optional[float]
    recorded_priority_level: Optional[str]
    strategy: Dict[str, Any]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_finding_snapshot(
    risk_record: Mapping[str, Any],
    blast_record: Mapping[str, Any],
    complexity_record: Mapping[str, Any],
    priority_record: Mapping[str, Any],
    strategy: Mapping[str, Any],
) -> FindingSnapshot:
    risk_assessment = _as_dict(risk_record.get("risk_assessment"))
    migration_priority = _as_dict(priority_record.get("migration_priority"))
    mosca = _as_dict(priority_record.get("mosca_analysis"))

    return FindingSnapshot(
        bom_ref=str(risk_record.get("bom_ref")),
        name=str(risk_record.get("name") or "Unknown"),
        asset=copy.deepcopy({
            "name": risk_record.get("name"),
            "classification": _as_dict(risk_record.get("classification")),
            "occurrences": risk_record.get("occurrences") or [],
        }),
        risk_context=copy.deepcopy(_as_dict(risk_assessment.get("context"))),
        recorded_risk_score=_as_float(risk_assessment.get("final_score")),
        recorded_risk_severity=risk_assessment.get("severity"),
        blast_radius_score=_as_float(blast_record.get("blast_radius_score"), 0.0),
        affected_findings=tuple(_as_dict(blast_record.get("direct_dependents")).get("refs") or ()),
        complexity_score=_as_float(complexity_record.get("score"), 0.0),
        business_criticality=priority_record.get("business_criticality"),
        mosca_urgency=mosca.get("migration_urgency"),
        recorded_priority_score=_as_float(migration_priority.get("priority_score")),
        recorded_priority_level=migration_priority.get("priority"),
        strategy=copy.deepcopy(dict(strategy or {})),
    )


def load_finding_snapshots(data_dir: Path = DATA_DIR) -> Dict[str, FindingSnapshot]:
    """Build snapshots for every finding from the active pipeline's outputs."""

    def by_ref(filename):
        with (Path(data_dir) / filename).open(encoding="utf-8") as file:
            return {
                record["bom_ref"]: record
                for record in json.load(file).get("assets", [])
                if record.get("bom_ref")
            }

    risk = by_ref("ecdat-explainable-risk.json")
    blast = by_ref("ecdat-blast-radius.json")
    complexity = by_ref("ecdat-migration-complexity.json")
    priority = by_ref("ecdat-migration-priority.json")
    plan = by_ref("ecdat-pqc-migration-plan.json")

    return {
        bom_ref: build_finding_snapshot(
            risk_record,
            blast.get(bom_ref, {}),
            complexity.get(bom_ref, {}),
            priority.get(bom_ref, {}),
            _as_dict(plan.get(bom_ref, {}).get("migration_strategy")),
        )
        for bom_ref, risk_record in risk.items()
    }


# ================================================================
# Single-finding what-if
# ================================================================

_REGISTRY_FAMILY_CACHE = None


def _registry_families():
    global _REGISTRY_FAMILY_CACHE

    if _REGISTRY_FAMILY_CACHE is None:
        _REGISTRY_FAMILY_CACHE = {
            algorithm["name"]: algorithm.get("family")
            for algorithm in get_pqc_algorithms()
        }

    return _REGISTRY_FAMILY_CACHE


def _target_family(strategy):
    role = strategy.get("purpose_class")
    family = policy.POLICIES.get(role, {}).get("pqc_family")

    if family:
        return family

    # Key material has no family of its own; it follows the algorithm
    # it was inherited from (see resolve_key_material_strategies).
    if strategy.get("inherited_from"):
        return strategy.get("pqc_family")

    return None


def _risk_and_priority(snapshot, asset):
    context = RiskContext(**{
        field: snapshot.risk_context[field]
        for field in _RISK_CONTEXT_FIELDS
        if field in snapshot.risk_context
    })

    risk = calculate_contextual_risk(asset, context)

    priority = calculate_migration_priority(
        risk["final_score"],
        snapshot.blast_radius_score,
        snapshot.complexity_score,
        business_criticality=snapshot.business_criticality,
        mosca_urgency=snapshot.mosca_urgency,
    )

    return risk, priority


def _role_eligibility(current):
    """
    The finding-level checks every what-if applies before looking at a
    particular option: NEEDS_REVIEW findings have no resolved role to
    migrate, and KEEP roles (hashing, MACs, KDFs, ...) have no PQC
    family to migrate to.
    """

    if current.get("strategy") == NEEDS_REVIEW:
        return {
            "simulatable": False,
            "reason_code": "finding-needs-review",
            "reason": (
                "This finding's migration strategy needs review; a what-if "
                "cannot choose its cryptographic role."
            ),
            "review_options": copy.deepcopy(current.get("review_options") or []),
        }

    target = _target_family(current)

    if target is None or not current.get("pqc_migration_required"):
        return {
            "simulatable": False,
            "reason_code": "no-pqc-migration-for-role",
            "reason": (
                f"This finding's role ({current.get('purpose_class_label', 'unknown')}) "
                "has no post-quantum migration target."
            ),
        }

    return {"simulatable": True, "target_family": target}


def simulation_eligibility(snapshot: FindingSnapshot) -> Dict[str, Any]:
    """
    Whether this finding can be simulated with its own decided strategy,
    independent of any particular option -- the same checks
    simulate_pqc_option applies, so a UI never offers a simulation the
    engine would reject for finding-level reasons.
    """

    current = snapshot.strategy
    eligibility = _role_eligibility(current)

    if eligibility["simulatable"] and current.get("strategy") not in (DIRECT_PQC, HYBRID):
        return {
            "simulatable": False,
            "reason_code": "unsupported-strategy",
            "reason": f"A what-if migration uses {DIRECT_PQC} or {HYBRID}, not {current.get('strategy')}.",
        }

    if eligibility["simulatable"]:
        eligibility["strategy"] = current.get("strategy")

    return eligibility


def load_ranked_candidates(data_dir: Path = DATA_DIR) -> Dict[str, list]:
    """The PQC ranking stage's candidates per finding, keyed by bom_ref."""

    with (Path(data_dir) / "ecdat-pqc-migration-plan.json").open(encoding="utf-8") as file:
        return {
            record["bom_ref"]: copy.deepcopy(record.get("ranked_candidates") or [])
            for record in json.load(file).get("assets", [])
            if record.get("bom_ref")
        }


def simulation_options(
    snapshot: FindingSnapshot,
    ranked_by_ref: Mapping[str, list],
    registry_families: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    The PQC options a what-if may choose for this finding: the ranking
    stage's candidates restricted to the family the finding's role
    accepts, in rank order, then any other registry algorithm of that
    family -- reported as unranked, never given an invented score. Key
    material has no ranking of its own, so it reads the ranking of the
    algorithm its strategy was inherited from, by bom_ref.
    """

    registry_families = registry_families or _registry_families()
    eligibility = simulation_eligibility(snapshot)
    result = {"eligibility": eligibility, "options": [], "ranking_source_bom_ref": None}

    if not eligibility["simulatable"]:
        return result

    target = eligibility["target_family"]
    source_ref = snapshot.bom_ref

    if not ranked_by_ref.get(source_ref) and snapshot.strategy.get("inherited_from"):
        source_ref = snapshot.strategy["inherited_from"]

    result["ranking_source_bom_ref"] = source_ref
    recommended = snapshot.strategy.get("pqc_component")
    seen = set()

    ranked = sorted(
        ranked_by_ref.get(source_ref) or [],
        key=lambda candidate: _as_float(candidate.get("rank"), math.inf),
    )

    for candidate in ranked:
        name = candidate.get("candidate") or candidate.get("name")

        if not name or name in seen or registry_families.get(name) != target:
            continue

        seen.add(name)
        result["options"].append({
            "name": name,
            "family": target,
            "ranked": True,
            "rank": candidate.get("rank"),
            "score": candidate.get("score"),
            "recommended": name == recommended,
        })

    for name, family in registry_families.items():
        if family == target and name not in seen:
            seen.add(name)
            result["options"].append({
                "name": name,
                "family": target,
                "ranked": False,
                "rank": None,
                "score": None,
                "recommended": name == recommended,
            })

    return result


def simulate_pqc_option(
    snapshot: FindingSnapshot,
    option_name: str,
    strategy: Optional[str] = None,
    registry_families: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate migrating one finding to `option_name` (a PQC registry
    algorithm) using `strategy` (DIRECT_PQC or HYBRID; defaults to the
    finding's own decided strategy). Returns `applied: False` with a
    reason instead of guessing whenever the option does not fit the
    finding's evidence-resolved role.
    """

    registry_families = registry_families or _registry_families()
    current = snapshot.strategy

    result = {
        "bom_ref": snapshot.bom_ref,
        "current_algorithm": snapshot.name,
        "option": option_name,
        "applied": False,
    }

    option_family = registry_families.get(option_name)

    if option_family is None:
        result.update({
            "reason_code": "unknown-pqc-option",
            "reason": f"{option_name} is not in the PQC registry (data/pqc-algorithms.json).",
        })
        return result

    result["option_family"] = option_family

    role_check = _role_eligibility(current)

    if not role_check["simulatable"]:
        result.update({key: value for key, value in role_check.items() if key != "simulatable"})
        return result

    target = role_check["target_family"]

    if option_family != target:
        result.update({
            "reason_code": "option-family-does-not-match-role",
            "reason": (
                f"{option_name} is a {option_family} algorithm, but this "
                f"finding's role ({current.get('purpose_class_label')}) requires "
                f"a {target} algorithm."
            ),
        })
        return result

    chosen = strategy or current.get("strategy")

    if chosen not in (DIRECT_PQC, HYBRID):
        result.update({
            "reason_code": "unsupported-strategy",
            "reason": f"A what-if migration uses {DIRECT_PQC} or {HYBRID}, not {chosen}.",
        })
        return result

    baseline_asset = copy.deepcopy(snapshot.asset)
    migrated_asset = copy.deepcopy(snapshot.asset)

    before_status = _as_dict(baseline_asset.get("classification")).get("quantum_status")
    migrated_asset.setdefault("classification", {})["quantum_status"] = (
        policy.POST_MIGRATION_QUANTUM_STATUS
    )

    risk_before, priority_before = _risk_and_priority(snapshot, baseline_asset)
    risk_after, priority_after = _risk_and_priority(snapshot, migrated_asset)

    result.update({
        "applied": True,
        "strategy": chosen,
        "classical_component": snapshot.name if chosen == HYBRID else None,
        "pqc_component": option_name,
        "quantum_status": {
            "before": before_status,
            "after": policy.POST_MIGRATION_QUANTUM_STATUS,
        },
        "risk": {
            "before": {"score": risk_before["final_score"], "severity": risk_before["severity"]},
            "after": {"score": risk_after["final_score"], "severity": risk_after["severity"]},
            "delta": round(risk_after["final_score"] - risk_before["final_score"], 2),
            "recorded": {"score": snapshot.recorded_risk_score, "severity": snapshot.recorded_risk_severity},
        },
        "priority": {
            "before": {"score": priority_before["priority_score"], "level": priority_before["priority"]},
            "after": {"score": priority_after["priority_score"], "level": priority_after["priority"]},
            "delta": round(priority_after["priority_score"] - priority_before["priority_score"], 2),
            "recorded": {"score": snapshot.recorded_priority_score, "level": snapshot.recorded_priority_level},
        },
        "carried_forward": {
            "blast_radius": {
                "score": snapshot.blast_radius_score,
                "affected_findings": list(snapshot.affected_findings),
                "reason": (
                    "The CBOM dependency graph does not change by choosing a "
                    "PQC option; these dependent findings must be migrated "
                    "together with this one."
                ),
            },
            "migration_complexity": {
                "score": snapshot.complexity_score,
                "reason": (
                    "Complexity factors (dependencies, evidence surface, "
                    "migration time) do not depend on the chosen option, so "
                    "it is not recomputed."
                ),
            },
            "mosca_urgency": {
                "value": snapshot.mosca_urgency,
                "reason": "Describes the pre-migration timeline.",
            },
        },
    })

    return result


# ================================================================
# Portfolio what-if
# ================================================================

def readiness_percent(priority_levels: Iterable[Optional[str]]) -> int:
    """
    The dashboard's own readiness definition
    (frontend/src/components/HeroOverview.jsx): the share of findings
    NOT at HIGH/CRITICAL migration priority, rounded half-up like
    JavaScript's Math.round.
    """

    levels = list(priority_levels)

    if not levels:
        return 100

    high = sum(1 for level in levels if level in _HIGH_PRIORITY_LEVELS)

    return int(math.floor(100 - (high / len(levels)) * 100 + 0.5))


def simulate_portfolio(
    snapshots: Iterable[FindingSnapshot],
    replacements: Mapping[str, str],
    strategies: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Apply several per-finding what-ifs at once ({bom_ref: option}) and
    report the portfolio effect. Findings without a replacement, and
    replacements that are rejected, keep their recorded state.
    """

    snapshots = list(snapshots)
    strategies = strategies or {}
    known_refs = {snapshot.bom_ref for snapshot in snapshots}

    applied, rejected = {}, {}
    levels_before, levels_after = [], []
    vulnerable_before = vulnerable_after = 0

    for snapshot in snapshots:
        status_before = _as_dict(snapshot.asset.get("classification")).get("quantum_status")
        status_after = status_before
        level_after = snapshot.recorded_priority_level

        option = replacements.get(snapshot.bom_ref)

        if option:
            outcome = simulate_pqc_option(snapshot, option, strategies.get(snapshot.bom_ref))

            if outcome["applied"]:
                applied[snapshot.bom_ref] = outcome
                status_after = outcome["quantum_status"]["after"]
                level_after = outcome["priority"]["after"]["level"]
            else:
                rejected[snapshot.bom_ref] = outcome

        levels_before.append(snapshot.recorded_priority_level)
        levels_after.append(level_after)
        vulnerable_before += status_before == "vulnerable"
        vulnerable_after += status_after == "vulnerable"

    for bom_ref in replacements:
        if bom_ref not in known_refs:
            rejected[bom_ref] = {
                "bom_ref": bom_ref,
                "applied": False,
                "reason_code": "unknown-finding",
                "reason": "No finding with this bom_ref exists in the snapshot set.",
            }

    return {
        "finding_count": len(snapshots),
        "applied_count": len(applied),
        "rejected_count": len(rejected),
        "remaining_quantum_vulnerable": {
            "before": vulnerable_before,
            "after": vulnerable_after,
        },
        "readiness_percent": {
            "before": readiness_percent(levels_before),
            "after": readiness_percent(levels_after),
        },
        "applied": applied,
        "rejected": rejected,
    }

"""
Purpose-aware migration strategy for one repository-specific finding.

Decides, per bom_ref, between:

    KEEP          no post-quantum migration for this role (optionally
                  with classical hardening)
    DIRECT_PQC    replace the current primitive with a PQC primitive
    HYBRID        run the current primitive and a PQC primitive together
                  during the transition
    NEEDS_REVIEW  the evidence does not support a decision

The decision is a function of the finding's evidence, never of its
algorithm name:

    resolved purpose + purpose evidence/confidence
        (services/purpose_resolver.py, via the classification stage)
    -> cryptographic role (knowledge/migration_strategy_policy.py)
    -> quantum status (classification)
    -> PQC candidates of the role's family (existing PQC mapping and
       ranking; family cross-checked against data/pqc-algorithms.json)
    -> transition requirements: external-interoperability exposure
       (services/risk_context.py) and phased-transition pressure
       (migration complexity / blast radius)

The algorithm name is only ever *reported* (as the current or
classical component); no branch reads it. That is what prevents the
RSA-OAEP class of error generically: a finding whose evidence resolves
to encryption is routed to the key-encapsulation family, and signature
candidates are excluded because they do not perform that role --
regardless of what the algorithm is called or what else its family
can be used for.

FindingMigrationInputs is an immutable snapshot of those inputs, so
services/migration_scenario.py can evaluate an alternative PQC choice
without mutating the real finding.
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from knowledge import migration_strategy_policy as policy
from services.pqc_registry import get_pqc_algorithms


KEEP = "KEEP"
DIRECT_PQC = "DIRECT_PQC"
HYBRID = "HYBRID"
NEEDS_REVIEW = "NEEDS_REVIEW"

STRATEGY_LABELS = {
    KEEP: "Keep (no PQC migration)",
    DIRECT_PQC: "Direct PQC migration",
    HYBRID: "Hybrid migration",
    NEEDS_REVIEW: "Needs review",
}

_CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


# ================================================================
# Immutable inputs
# ================================================================

@dataclass(frozen=True)
class RankedCandidate:
    name: str
    family: Optional[str]
    rank: Optional[int]
    score: Optional[float]


@dataclass(frozen=True)
class FindingMigrationInputs:
    bom_ref: str
    name: str
    category: Optional[str]
    purposes: Tuple[str, ...]
    purpose_confidence: Optional[str]
    purpose_evidence_source: Optional[str]
    purpose_evidence_reason: Optional[str]
    purpose_needs_review: bool
    quantum_status: Optional[str]
    risk_reason: Optional[str]
    mapping_confidence: Optional[str]
    ranked_candidates: Tuple[RankedCandidate, ...]
    exposure: Optional[str]
    blast_radius_score: Optional[float]
    blast_severity: Optional[str]
    direct_dependents: int
    complexity_score: Optional[float]
    complexity_level: Optional[str]
    mosca_urgency: Optional[str]
    governing_refs: Tuple[str, ...]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_migration_inputs(
    risk_record: Mapping[str, Any],
    blast_record: Mapping[str, Any],
    complexity_record: Mapping[str, Any],
    priority_record: Mapping[str, Any],
    pqc_analysis: Mapping[str, Any],
    ranked_candidates,
) -> FindingMigrationInputs:
    """
    Snapshot one finding's decision inputs from the active pipeline's
    own records (all already joined by bom_ref by the caller).
    """

    classification = _as_dict(risk_record.get("classification"))
    risk_context = _as_dict(_as_dict(risk_record.get("risk_assessment")).get("context"))

    purposes = classification.get("purpose") or []

    if isinstance(purposes, str):
        purposes = [purposes]

    candidates = []

    for entry in ranked_candidates or []:
        if not isinstance(entry, dict):
            continue

        name = entry.get("candidate") or entry.get("name")

        if not name:
            continue

        rank = entry.get("rank")

        candidates.append(
            RankedCandidate(
                name=str(name),
                family=entry.get("family"),
                rank=int(rank) if isinstance(rank, (int, float)) else None,
                score=_as_float(entry.get("score")),
            )
        )

    mosca = _as_dict(priority_record.get("mosca_analysis"))

    return FindingMigrationInputs(
        bom_ref=str(risk_record.get("bom_ref")),
        name=str(risk_record.get("name") or risk_record.get("asset") or "Unknown"),
        category=classification.get("category"),
        purposes=tuple(str(p).strip().lower() for p in purposes if p),
        purpose_confidence=classification.get("purpose_confidence"),
        purpose_evidence_source=classification.get("purpose_evidence_source"),
        purpose_evidence_reason=classification.get("purpose_evidence_reason"),
        purpose_needs_review=bool(classification.get("purpose_needs_review", False)),
        quantum_status=classification.get("quantum_status"),
        risk_reason=classification.get("risk_reason"),
        mapping_confidence=pqc_analysis.get("confidence"),
        ranked_candidates=tuple(candidates),
        exposure=risk_context.get("exposure"),
        blast_radius_score=_as_float(blast_record.get("blast_radius_score")),
        blast_severity=blast_record.get("severity"),
        direct_dependents=int(_as_dict(blast_record.get("direct_dependents")).get("count") or 0),
        complexity_score=_as_float(complexity_record.get("score")),
        complexity_level=complexity_record.get("level"),
        mosca_urgency=mosca.get("migration_urgency"),
        governing_refs=tuple(_as_dict(blast_record.get("direct_dependencies")).get("refs") or ()),
    )


# ================================================================
# Helpers
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


def _min_confidence(*levels):
    known = [level for level in levels if level in _CONFIDENCE_RANK]

    if not known:
        return "LOW"

    return min(known, key=lambda level: _CONFIDENCE_RANK[level])


def _purpose_classes(inputs):
    classes = []

    for label in inputs.purposes:
        role = policy.classify_purpose(label, inputs.category)

        if role not in classes:
            classes.append(role)

    return classes


def _family_candidates(inputs, family, registry_families):
    """
    Candidates that genuinely belong to `family` -- per both the
    mapping's own label and the PQC registry -- best rank first.
    """

    eligible = [
        candidate
        for candidate in inputs.ranked_candidates
        if candidate.family == family
        and registry_families.get(candidate.name) == family
    ]

    return sorted(
        eligible,
        key=lambda candidate: (
            candidate.rank if candidate.rank is not None else 10**6,
            candidate.name,
        ),
    )


def _purpose_evidence_text(inputs):
    return (
        f"{inputs.purpose_evidence_source or 'unknown source'}: "
        f"{inputs.purpose_evidence_reason or 'no evidence reason recorded.'}"
    )


def _impact_text(inputs):
    return (
        f"Migration complexity {inputs.complexity_level or 'UNKNOWN'} "
        f"({inputs.complexity_score if inputs.complexity_score is not None else '?'}/100); "
        f"blast radius {inputs.blast_severity or 'UNKNOWN'} "
        f"({inputs.blast_radius_score if inputs.blast_radius_score is not None else '?'}/100) "
        f"with {inputs.direct_dependents} directly dependent finding(s)."
    )


def _base_result(inputs, role):
    return {
        "bom_ref": inputs.bom_ref,
        "current_algorithm": inputs.name,
        "resolved_purposes": list(inputs.purposes),
        "purpose_class": role,
        "purpose_class_label": policy.CLASS_LABELS.get(role, role),
        "purpose_confidence": inputs.purpose_confidence,
        "purpose_evidence_source": inputs.purpose_evidence_source,
        "quantum_status": inputs.quantum_status,
        "classical_component": None,
        "pqc_component": None,
        "pqc_family": None,
        "construction": None,
        "pqc_migration_required": False,
        "harvest_now_decrypt_later": None,
        "classical_hardening": None,
        "review_options": [],
        "inherited_from": None,
        "decision_factors": [],
    }


def _finish(result, inputs, strategy, confidence, reason_code, rationale, quantum_relevance, pqc_selection):
    result.update({
        "strategy": strategy,
        "label": STRATEGY_LABELS[strategy],
        "confidence": confidence,
        "reason_code": reason_code,
        "rationale": rationale,
        "explanation": {
            "detected": (
                f"{inputs.name} (category {inputs.category or 'unknown'}, "
                f"quantum status {inputs.quantum_status or 'unknown'}), "
                f"finding {inputs.bom_ref}."
            ),
            "resolved_purpose": (
                f"{', '.join(inputs.purposes) or 'none'} -> role: "
                f"{result['purpose_class_label']}."
            ),
            "purpose_evidence": _purpose_evidence_text(inputs),
            "classification_confidence": inputs.purpose_confidence or "UNKNOWN",
            "quantum_relevance": quantum_relevance,
            "pqc_selection": pqc_selection,
            "strategy_rationale": rationale,
            "expected_impact": _impact_text(inputs),
        },
    })

    return result


def _needs_review(inputs, role, reason_code, rationale, options=None):
    result = _base_result(inputs, role)
    result["review_options"] = options or []

    return _finish(
        result,
        inputs,
        NEEDS_REVIEW,
        # A review decision is only as trustworthy as the evidence
        # that forced it; it never claims more than LOW/MEDIUM.
        _min_confidence(inputs.purpose_confidence, "MEDIUM"),
        reason_code,
        rationale,
        inputs.risk_reason or "Quantum relevance cannot be assessed until the role is resolved.",
        "No PQC component selected until the review is resolved.",
    )


def _review_options(inputs, roles, registry_families):
    options = []

    for role in roles:
        family = policy.POLICIES.get(role, {}).get("pqc_family")
        top = _family_candidates(inputs, family, registry_families)[:1] if family else []

        options.append({
            "purpose_class": role,
            "purpose_class_label": policy.CLASS_LABELS.get(role, role),
            "pqc_family": family,
            "top_candidate": top[0].name if top else None,
        })

    return options


# ================================================================
# Decision
# ================================================================

def determine_migration_strategy(inputs: FindingMigrationInputs, registry_families=None) -> Dict[str, Any]:
    """Decide the migration strategy for one finding from its evidence."""

    registry_families = registry_families or _registry_families()

    # -------------------------------------------------------------
    # 1. The purpose must be resolved from repository evidence.
    # -------------------------------------------------------------

    if inputs.purpose_evidence_source == "conflicting":
        return _needs_review(
            inputs, policy.UNRESOLVED, "conflicting-purpose-evidence",
            "The repository evidence for this finding's purpose conflicts, so "
            "no purpose -- and therefore no migration strategy -- is selected "
            "automatically.",
        )

    if inputs.purpose_needs_review or not inputs.purposes:
        return _needs_review(
            inputs, policy.UNRESOLVED, "unresolved-purpose",
            "The repository evidence does not identify this finding's "
            "cryptographic purpose, so no migration strategy is selected.",
        )

    roles = _purpose_classes(inputs)

    if policy.UNRESOLVED in roles:
        return _needs_review(
            inputs, policy.UNRESOLVED, "unresolved-role",
            f"The resolved purpose ({', '.join(inputs.purposes)}) does not "
            "identify a specific cryptographic role for category "
            f"'{inputs.category or 'unknown'}', so no strategy is selected.",
        )

    if len(roles) > 1:
        return _needs_review(
            inputs, policy.UNRESOLVED, "ambiguous-purpose",
            "The evidence leaves more than one cryptographic role possible "
            f"({', '.join(policy.CLASS_LABELS[r] for r in roles)}; purpose "
            f"source: {inputs.purpose_evidence_source}, confidence "
            f"{inputs.purpose_confidence}). These roles need different PQC "
            "families, so the actual usage must be confirmed before choosing.",
            _review_options(inputs, roles, registry_families),
        )

    role = roles[0]

    if role == policy.KEY_MATERIAL:
        # Replaced by resolve_key_material_strategies() once the
        # governing algorithm's own strategy is known.
        return _needs_review(
            inputs, role, "key-material-pending-governing-algorithm",
            "Key material migrates with the algorithm that uses it; its "
            "strategy follows that algorithm's decision.",
        )

    if role == policy.PROTOCOL:
        return _needs_review(
            inputs, role, "protocol-components-unresolved",
            "A protocol finding does not identify which key-exchange and "
            "authentication components it uses, so they must be resolved "
            "before a component-level strategy can be chosen.",
        )

    entry = policy.POLICIES[role]
    result = _base_result(inputs, role)
    result["harvest_now_decrypt_later"] = entry["harvest_now_decrypt_later"]

    # -------------------------------------------------------------
    # 2. Roles with no PQC replacement: KEEP (+ classical hardening).
    # -------------------------------------------------------------

    if role in policy.NO_PQC_REPLACEMENT_ROLES:
        hardening = policy.classical_hardening_for(inputs.quantum_status)
        result["classical_hardening"] = hardening
        result["decision_factors"].append({
            "signal": "quantum_status",
            "value": inputs.quantum_status,
            "source": "classification",
            "effect": f"classical hardening {hardening['status']}",
        })

        return _finish(
            result, inputs, KEEP,
            _min_confidence(inputs.purpose_confidence),
            "no-pqc-replacement-for-role",
            f"{policy.CLASS_LABELS[role].capitalize()} is not broken by Shor's "
            "algorithm and has no ML-KEM/ML-DSA replacement, so no PQC "
            f"migration applies. Classical hardening: {hardening['status']} -- "
            f"{hardening['reason']}",
            entry["quantum_threat"],
            "Not applicable: no post-quantum family replaces this role.",
        )

    # -------------------------------------------------------------
    # 3. PQC-migration roles.
    # -------------------------------------------------------------

    quantum_status = str(inputs.quantum_status or "unknown").lower()

    if quantum_status == "quantum-resistant":
        return _finish(
            result, inputs, KEEP,
            _min_confidence(inputs.purpose_confidence),
            "already-quantum-resistant",
            "The current primitive is already classified as quantum-resistant.",
            "Classified as quantum-resistant.",
            "Not applicable: already quantum-resistant.",
        )

    if quantum_status != "vulnerable":
        return _needs_review(
            inputs, role, "quantum-status-unconfirmed",
            f"The role ({policy.CLASS_LABELS[role]}) normally requires PQC "
            f"migration, but the quantum status is '{quantum_status}' rather "
            "than confirmed vulnerable.",
        )

    family = entry["pqc_family"]
    candidates = _family_candidates(inputs, family, registry_families)

    if not candidates:
        return _needs_review(
            inputs, role, "no-suitable-pqc-mapping",
            f"No {family} candidate is available in the PQC mapping for this "
            f"finding's role ({policy.CLASS_LABELS[role]}).",
        )

    selected = candidates[0]
    excluded = sorted({
        candidate.family or "unknown"
        for candidate in inputs.ranked_candidates
        if candidate.family != family
    })

    # -------------------------------------------------------------
    # 4. Transition requirements: hybrid vs direct.
    # -------------------------------------------------------------

    external_interop = (
        str(inputs.exposure or "").upper() in policy.EXTERNAL_INTEROPERABILITY_EXPOSURE
    )
    phased_by_complexity = str(inputs.complexity_level or "").upper() in policy.PHASED_TRANSITION_LEVELS
    phased_by_blast = str(inputs.blast_severity or "").upper() in policy.PHASED_TRANSITION_LEVELS

    result["decision_factors"].extend([
        {
            "signal": "external_interoperability",
            "value": inputs.exposure,
            "source": "risk context exposure (occurrence paths / API context)",
            "effect": "favours hybrid" if external_interop else "no external-interoperability evidence",
        },
        {
            "signal": "migration_complexity",
            "value": inputs.complexity_level,
            "source": "migration complexity",
            "effect": "favours phased hybrid transition" if phased_by_complexity else "no phased-transition pressure",
        },
        {
            "signal": "blast_radius",
            "value": inputs.blast_severity,
            "source": "blast radius",
            "effect": "favours phased hybrid transition" if phased_by_blast else "no phased-transition pressure",
        },
    ])

    if inputs.mosca_urgency:
        result["decision_factors"].append({
            "signal": "mosca_urgency",
            "value": inputs.mosca_urgency,
            "source": "Mosca timeline (configured data lifetime)",
            "effect": "urgency only; does not change hybrid vs direct",
        })

    triggers = []

    if external_interop:
        triggers.append(f"network-facing exposure ({inputs.exposure})")
    if phased_by_complexity:
        triggers.append(f"{inputs.complexity_level} migration complexity")
    if phased_by_blast:
        triggers.append(f"{inputs.blast_severity} blast radius ({inputs.direct_dependents} dependent finding(s))")

    base_confidence = _min_confidence(inputs.purpose_confidence, inputs.mapping_confidence)

    result.update({
        "pqc_component": selected.name,
        "pqc_family": family,
        "pqc_migration_required": True,
    })

    pqc_selection = (
        f"{selected.name} is the highest-ranked {family} candidate for this "
        f"role (rank {selected.rank}, score {selected.score})."
    )

    if excluded:
        pqc_selection += (
            f" Candidates from other families ({', '.join(excluded)}) are "
            "excluded because they do not perform this role."
        )

    quantum_relevance = f"{entry['quantum_threat']} {inputs.risk_reason or ''}".strip()

    if triggers:
        result["classical_component"] = inputs.name
        result["construction"] = entry["hybrid_construction"]

        return _finish(
            result, inputs, HYBRID,
            base_confidence,
            "transition-requirements-favour-hybrid",
            f"Evidence of {', '.join(triggers)} means the migration must "
            f"interoperate and be phased, so {inputs.name} is kept alongside "
            f"{selected.name} during the transition.",
            quantum_relevance,
            pqc_selection,
        )

    result["construction"] = entry["direct_construction"]
    result["replaces"] = inputs.name

    return _finish(
        result, inputs, DIRECT_PQC,
        # "Direct" rests on the *absence* of transition evidence in the
        # scanned sources, which is weaker than positive evidence, so it
        # is never stated with HIGH confidence.
        _min_confidence(base_confidence, "MEDIUM"),
        "no-transition-requirements-found",
        f"The scanned evidence shows no network-facing exposure and no "
        f"HIGH/CRITICAL complexity or blast radius, so {inputs.name} can be "
        f"replaced directly by {selected.name}. Confirm no external peers "
        "still require the current scheme.",
        quantum_relevance,
        pqc_selection,
    )


# ================================================================
# Key material: inherit from the governing algorithm
# ================================================================

def resolve_key_material_strategies(strategies_by_ref, inputs_by_ref):
    """
    Return a new {bom_ref: strategy} map in which every key-material
    finding follows the strategy of the algorithm it belongs to, per
    the CBOM dependency graph (the key's own `dependsOn` edges). Never
    mutates the input dicts.
    """

    resolved = dict(strategies_by_ref)

    for bom_ref, strategy in strategies_by_ref.items():

        if strategy.get("reason_code") != "key-material-pending-governing-algorithm":
            continue

        inputs = inputs_by_ref[bom_ref]

        parents = [
            (ref, strategies_by_ref[ref])
            for ref in inputs.governing_refs
            if ref in strategies_by_ref
            and strategies_by_ref[ref].get("purpose_class") != policy.KEY_MATERIAL
        ]

        if not parents:
            resolved[bom_ref] = _needs_review(
                inputs, policy.KEY_MATERIAL, "key-material-without-governing-algorithm",
                "No governing algorithm for this key material was found in "
                "the CBOM dependency graph, so its strategy cannot be derived.",
            )
            continue

        decisions = {(parent["strategy"], parent.get("pqc_component")) for _, parent in parents}

        if len(decisions) > 1:
            resolved[bom_ref] = _needs_review(
                inputs, policy.KEY_MATERIAL, "key-material-governed-by-conflicting-strategies",
                "This key material is used by algorithms with different "
                "migration strategies, so it must be reviewed.",
            )
            continue

        parent_ref, parent = parents[0]

        if parent["strategy"] == NEEDS_REVIEW:
            resolved[bom_ref] = _needs_review(
                inputs, policy.KEY_MATERIAL, "governing-algorithm-needs-review",
                f"The algorithm this key material belongs to "
                f"({parent['current_algorithm']}) needs review, so this key "
                "material does too.",
            )
            resolved[bom_ref]["inherited_from"] = parent_ref
            continue

        result = _base_result(inputs, policy.KEY_MATERIAL)
        result.update({
            "inherited_from": parent_ref,
            "pqc_component": parent.get("pqc_component"),
            "pqc_family": parent.get("pqc_family"),
            "construction": parent.get("construction"),
            "pqc_migration_required": parent.get("pqc_migration_required", False),
            "harvest_now_decrypt_later": parent.get("harvest_now_decrypt_later"),
            "classical_hardening": parent.get("classical_hardening"),
            "classical_component": inputs.name if parent["strategy"] == HYBRID else None,
        })

        if parent["strategy"] == DIRECT_PQC:
            result["replaces"] = inputs.name

        action = {
            HYBRID: f"retained alongside new {parent.get('pqc_component')} key material",
            DIRECT_PQC: f"replaced by new {parent.get('pqc_component')} key material",
            KEEP: "kept, as its algorithm needs no PQC migration",
        }[parent["strategy"]]

        finished = _finish(
            result, inputs, parent["strategy"],
            parent["confidence"],
            "inherited-from-governing-algorithm",
            f"This key material belongs to {parent['current_algorithm']} "
            f"(CBOM dependency), whose strategy is {parent['strategy']}; the "
            f"key material is {action}.",
            parent["explanation"]["quantum_relevance"],
            parent["explanation"]["pqc_selection"],
        )

        finished["explanation"]["purpose_evidence"] = (
            f"CBOM dependency graph: this key material is used by "
            f"{parent['current_algorithm']} ({parent_ref})."
        )

        resolved[bom_ref] = finished

    return resolved

"""
Evidence Explorer: "why did ECDAT classify, score and recommend this
migration path for this finding?"

This module reads the pipeline's existing per-finding outputs and
re-arranges them into one evidence record, joined by bom_ref only. It
computes nothing: every score, level, contribution, confidence and
decision below is copied from the stage that produced it.

    data/keycloak-cbom.json              raw CycloneDX component + scan metadata
    data/ecdat-assets.json               parsed identity and source occurrences
    data/ecdat-explainable-risk.json     classification, purpose evidence,
                                         risk context, contributions,
                                         evidence quality/confidence
    data/ecdat-blast-radius.json         dependency graph impact
    data/ecdat-migration-complexity.json complexity factors
    data/ecdat-migration-priority.json   priority contributions
    data/ecdat-pqc-migration-plan.json   PQC mapping, ranked candidates,
                                         purpose-aware migration strategy

Absent evidence is never filled in. A missing value is None and, where a
stage recorded why it is unknown, that reason is carried through. A
NEEDS_REVIEW finding is reported as unresolved and its ranked candidates
are labelled as ranking-model output, never as a selected PQC component.
"""

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

CBOM_FILENAME = "keycloak-cbom.json"

PIPELINE_FILES = {
    "assets": "ecdat-assets.json",
    "risk": "ecdat-explainable-risk.json",
    "blast": "ecdat-blast-radius.json",
    "complexity": "ecdat-migration-complexity.json",
    "priority": "ecdat-migration-priority.json",
    "plan": "ecdat-pqc-migration-plan.json",
}

# services/purpose_resolver.py's evidence tiers. Only the first three
# are observations of this repository; the fallback is general
# algorithm-family knowledge, recorded at LOW confidence by design.
PURPOSE_EVIDENCE_SOURCES = {
    "cbom-primitive": ("CBOM primitive", True),
    "source-context": ("Source API context", True),
    "conflicting": ("Conflicting repository evidence", True),
    "algorithm-family-fallback": ("Algorithm-family knowledge (not repository evidence)", False),
    "insufficient-evidence": ("Insufficient evidence", False),
}

# How each RiskContext value is obtained (services/risk_context.py and
# services/business_context.py). These describe the documented method;
# the stage does not record which individual path or keyword matched.
RISK_CONTEXT_SOURCES = {
    "business_criticality": (
        "Derived from occurrence file paths and occurrence count "
        "(services/risk_context.py): test/demo/doc-only paths give LOW."
    ),
    "exposure": (
        "Derived from network/protocol keywords in occurrence paths and "
        "API contexts (services/risk_context.py)."
    ),
    "migration_time_years": (
        "Derived from occurrence count and cryptographic category "
        "(services/risk_context.py)."
    ),
    "data_lifetime_years": (
        "Organization-provided only, per bom_ref "
        "(data/business-context.json); never inferred from code."
    ),
    "quantum_threat_horizon_years": (
        "Fixed, documented default shared by all findings "
        "(services/business_context.py)."
    ),
}

KEEP = "KEEP"
NEEDS_REVIEW = "NEEDS_REVIEW"
MIGRATING_STRATEGIES = ("DIRECT_PQC", "HYBRID")


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _record_ref(record):
    identity = _as_dict(record.get("identity"))
    return record.get("bom_ref") or record.get("asset_ref") or identity.get("bom_ref")


def _index(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    records = data.get("assets", []) if isinstance(data, dict) else data

    return {
        str(_record_ref(record)): record
        for record in records or []
        if isinstance(record, dict) and _record_ref(record)
    }


def load_evidence_records(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    """Every pipeline output the explorer reads, indexed by bom_ref."""

    data_dir = Path(data_dir)
    records = {key: _index(data_dir / filename) for key, filename in PIPELINE_FILES.items()}

    cbom_path = data_dir / CBOM_FILENAME
    cbom = {}

    if cbom_path.exists():
        with cbom_path.open(encoding="utf-8") as file:
            cbom = json.load(file)

    records["cbom_components"] = {
        str(component["bom-ref"]): component
        for component in _as_list(cbom.get("components"))
        if isinstance(component, dict) and component.get("bom-ref")
    }
    records["cbom_metadata"] = _as_dict(cbom.get("metadata"))
    records["cbom_format"] = {
        "format": cbom.get("bomFormat"),
        "spec_version": cbom.get("specVersion"),
    }

    return records


def _finding_ref(bom_ref, records):
    """A dependency reference with its display name, or None for the name when unknown."""

    source = records["assets"].get(bom_ref) or {}
    return {"bom_ref": bom_ref, "name": source.get("name")}


def _scan_metadata(records):
    metadata = records.get("cbom_metadata") or {}
    properties = {
        item.get("name"): item.get("value")
        for item in _as_list(metadata.get("properties"))
        if isinstance(item, dict)
    }
    tools = [
        service.get("name")
        for service in _as_list(_as_dict(metadata.get("tools")).get("services"))
        if isinstance(service, dict) and service.get("name")
    ]

    return {
        "file": CBOM_FILENAME if records.get("cbom_components") else None,
        "format": records["cbom_format"].get("format"),
        "spec_version": records["cbom_format"].get("spec_version"),
        "tools": tools,
        "repository": properties.get("gitUrl"),
        "revision": properties.get("revision"),
        "commit": properties.get("commit"),
        "timestamp": metadata.get("timestamp"),
    }


def _identity(bom_ref, source, classification, component, records):
    crypto = _as_dict(_as_dict(component).get("cryptoProperties"))

    return {
        "bom_ref": bom_ref,
        "name": source.get("name"),
        "component_type": source.get("type"),
        "asset_type": source.get("asset_type") or crypto.get("assetType"),
        "category": classification.get("category"),
        "primitive": source.get("primitive"),
        "oid": source.get("oid") or crypto.get("oid"),
        "in_raw_cbom": bool(component),
        "cbom_crypto_properties": copy.deepcopy(crypto) if crypto else None,
        "scan": _scan_metadata(records),
    }


def _purpose(classification):
    source = classification.get("purpose_evidence_source")
    label, repository_evidence = PURPOSE_EVIDENCE_SOURCES.get(source, (None, None))

    return {
        "resolved_purposes": _as_list(classification.get("purpose")),
        "usage": classification.get("usage"),
        "confidence": classification.get("purpose_confidence"),
        "evidence_source": source,
        "evidence_source_label": label,
        "repository_evidence": repository_evidence,
        "evidence_reason": classification.get("purpose_evidence_reason"),
        "needs_review": classification.get("purpose_needs_review"),
        "supporting_evidence": copy.deepcopy(_as_dict(classification.get("purpose_evidence"))) or None,
    }


def _source(source, risk_record, blast, records):
    occurrences = [
        {
            "location": occurrence.get("location"),
            "line": occurrence.get("line"),
            "offset": occurrence.get("offset"),
            "context": occurrence.get("context"),
        }
        for occurrence in _as_list(source.get("occurrences"))
        if isinstance(occurrence, dict)
    ]

    def refs(block):
        return [_finding_ref(ref, records) for ref in _as_list(_as_dict(blast.get(block)).get("refs"))]

    return {
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "evidence_quality": copy.deepcopy(_as_dict(risk_record.get("risk_assessment")).get("evidence_quality")),
        "evidence_confidence": copy.deepcopy(risk_record.get("evidence_confidence")),
        "dependencies": {
            "depends_on": refs("direct_dependencies"),
            "direct_dependents": refs("direct_dependents"),
            "transitive_dependents": refs("transitive_dependents"),
        } if blast else None,
    }


def _quantum(classification, risk_assessment):
    base_risk = _as_dict(risk_assessment.get("base_risk"))

    return {
        "quantum_status": classification.get("quantum_status"),
        "category": classification.get("category"),
        "reason": classification.get("risk_reason"),
        "base_risk": {
            "score": base_risk.get("score"),
            "severity": base_risk.get("severity"),
            "evidence": _as_list(base_risk.get("evidence")),
        } if base_risk else None,
    }


def _risk(risk_record):
    assessment = _as_dict(risk_record.get("risk_assessment"))
    explanation = _as_dict(risk_record.get("explanation"))
    context = _as_dict(assessment.get("context"))
    contributions = copy.deepcopy(_as_list(explanation.get("contributions")))

    factors = []

    for key, method in RISK_CONTEXT_SOURCES.items():
        value = context.get(key)
        known = value is not None

        if key == "data_lifetime_years" and context.get("data_lifetime_known") is False:
            known = False

        factors.append({"factor": key, "value": value if known else None, "known": known, "source": method})

    mosca = assessment.get("mosca_analysis")

    if mosca:
        mosca_block = {"performed": True, "analysis": copy.deepcopy(mosca), "reason": None}
    elif context.get("data_lifetime_known") is False:
        mosca_block = {
            "performed": False,
            "analysis": None,
            "reason": "Not performed: no data lifetime is configured for this finding.",
        }
    else:
        mosca_block = {"performed": False, "analysis": None, "reason": None}

    return {
        "final_score": assessment.get("final_score"),
        "severity": assessment.get("severity"),
        "summary": explanation.get("summary"),
        "contributions": contributions,
        "contribution_total": explanation.get("contribution_total"),
        "unknown_factors": [
            {"factor": item.get("factor"), "label": item.get("label"), "reason": item.get("reason")}
            for item in contributions
            if item.get("known") is False
        ],
        "context": factors,
        "mosca": mosca_block,
    }


def _blast_radius(blast):
    if not blast:
        return None

    explanation = _as_dict(blast.get("explanation"))

    return {
        "score": blast.get("blast_radius_score"),
        "severity": blast.get("severity"),
        "score_breakdown": copy.deepcopy(blast.get("score_breakdown")),
        "summary": explanation.get("summary"),
        "reasons": _as_list(explanation.get("reasons")),
    }


def _complexity(complexity):
    if not complexity:
        return None

    explanation = _as_dict(complexity.get("explanation"))

    return {
        "score": complexity.get("score"),
        "level": complexity.get("level"),
        "factors": copy.deepcopy(complexity.get("factors")),
        "summary": explanation.get("summary"),
        "reasons": _as_list(explanation.get("reasons")),
    }


def _priority(priority_record):
    priority = _as_dict(priority_record.get("migration_priority"))

    if not priority:
        return None

    explanation = _as_dict(priority.get("explanation"))

    contributions = []

    for factor, block in _as_dict(priority.get("score_breakdown")).items():
        block = _as_dict(block)
        contributions.append({
            "factor": factor,
            "known": block.get("known", True),
            "raw_score": block.get("raw_score"),
            "weight": block.get("weight"),
            "weighted_score": block.get("weighted_score"),
            "reason": block.get("reason"),
        })

    return {
        "score": priority.get("priority_score"),
        "level": priority.get("priority"),
        "contributions": contributions,
        "unknown_factors": _as_list(priority.get("unknown_factors")),
        "summary": explanation.get("summary"),
        "reasons": _as_list(explanation.get("reasons")),
    }


_STRATEGY_FIELDS = (
    "strategy",
    "label",
    "confidence",
    "reason_code",
    "rationale",
    "purpose_class",
    "purpose_class_label",
    "pqc_family",
    "pqc_component",
    "classical_component",
    "construction",
    "pqc_migration_required",
    "harvest_now_decrypt_later",
    "classical_hardening",
    "decision_factors",
    "review_options",
    "explanation",
)


def _strategy(strategy, records):
    if not strategy:
        return None

    result = {key: copy.deepcopy(strategy.get(key)) for key in _STRATEGY_FIELDS}
    inherited = strategy.get("inherited_from")
    result["governing_finding"] = _finding_ref(inherited, records) if inherited else None
    result["resolved"] = strategy.get("strategy") != NEEDS_REVIEW

    return result


def _pqc(bom_ref, plan_record, strategy, records):
    decision = strategy.get("strategy")
    role_family = strategy.get("pqc_family")
    analysis = _as_dict(plan_record.get("pqc_analysis"))

    ranking_source = bom_ref
    ranked = _as_list(plan_record.get("ranked_candidates"))

    # Key material is not ranked itself; its strategy names the finding it
    # inherits from, whose ranking the strategy's own selection came from.
    if not ranked and strategy.get("inherited_from"):
        ranking_source = strategy["inherited_from"]
        ranked = _as_list(_as_dict(records["plan"].get(ranking_source)).get("ranked_candidates"))

    candidates = [
        {
            "rank": candidate.get("rank"),
            "candidate": candidate.get("candidate") or candidate.get("name"),
            "family": candidate.get("family"),
            "score": candidate.get("score"),
            "compatibility": candidate.get("compatibility"),
            "fits_role": (candidate.get("family") == role_family) if role_family else None,
        }
        for candidate in ranked
        if isinstance(candidate, dict)
    ]

    if decision in MIGRATING_STRATEGIES and strategy.get("pqc_component"):
        status = "selected"
        note = "Selected by the purpose-aware migration strategy."
    elif decision in MIGRATING_STRATEGIES:
        status = "no-candidate"
        note = "The strategy requires a PQC migration but no suitable candidate is available."
    elif decision == NEEDS_REVIEW:
        status = "unresolved"
        note = (
            "No PQC component is selected: the migration strategy needs review. "
            "Ranked candidates are ranking-model output only, not a confirmed recommendation."
        )
    elif decision == KEEP:
        status = "not-applicable"
        note = "No post-quantum migration applies to this finding's role."
    else:
        status = "unknown"
        note = None

    return {
        "status": status,
        "note": note,
        "selected_component": strategy.get("pqc_component") if status == "selected" else None,
        "role_family": role_family,
        "mapping": {
            "migration_type": analysis.get("migration_type"),
            "pqc_applicable": analysis.get("pqc_applicable"),
            "confidence": analysis.get("confidence"),
            "reason": analysis.get("reason"),
        } if analysis else None,
        "ranking_source_bom_ref": ranking_source if candidates else None,
        "ranked_candidates": candidates,
    }


def _join(values):
    return ", ".join(str(value) for value in values) if values else None


def _chain(identity, purpose, source, quantum, risk, priority, strategy, pqc):
    """
    The evidence -> purpose -> risk -> migration decision path, one step
    per stage, stated only from values already in this record.
    """

    steps = []

    count = source["occurrence_count"]
    quality = _as_dict(source.get("evidence_quality")).get("quality")
    steps.append({
        "key": "evidence",
        "label": "Evidence",
        "status": "established" if count else "unknown",
        "statement": (
            f"{count} source occurrence(s) recorded in the CBOM"
            + (f"; evidence quality {quality}." if quality else ".")
            if count
            else "No source occurrence is recorded for this finding."
        ),
    })

    purposes = _join(purpose["resolved_purposes"])
    if purpose["needs_review"]:
        purpose_status = "unresolved"
    elif not purposes:
        purpose_status = "unknown"
    elif purpose["repository_evidence"] is False:
        purpose_status = "low-confidence"
    else:
        purpose_status = "established"
    steps.append({
        "key": "purpose",
        "label": "Purpose",
        "status": purpose_status,
        "statement": (
            f"Resolved as {purposes} from {purpose['evidence_source_label'] or purpose['evidence_source'] or 'an unrecorded source'}"
            f" ({purpose['confidence'] or 'unknown'} confidence)."
            if purposes
            else "No purpose was resolved."
        ),
    })

    steps.append({
        "key": "quantum",
        "label": "Quantum status",
        "status": "established" if quantum["quantum_status"] else "unknown",
        "statement": (
            f"{quantum['quantum_status']}" + (f": {quantum['reason']}" if quantum["reason"] else ".")
            if quantum["quantum_status"]
            else "Quantum status is not recorded."
        ),
    })

    unknown_risk = _join(item["label"] or item["factor"] for item in risk["unknown_factors"])
    steps.append({
        "key": "risk",
        "label": "Risk",
        "status": "established" if risk["final_score"] is not None else "unknown",
        "statement": (
            f"Risk {risk['final_score']} ({risk['severity']})"
            + (f"; unknown and excluded: {unknown_risk}." if unknown_risk else ".")
            if risk["final_score"] is not None
            else "Risk is not recorded."
        ),
    })

    if priority:
        unknown_priority = _join(item.replace("_", " ") for item in priority["unknown_factors"])
        steps.append({
            "key": "priority",
            "label": "Priority",
            "status": "established",
            "statement": (
                f"Priority {priority['score']} ({priority['level']}) from risk, blast radius and complexity"
                + (f"; unknown and excluded: {unknown_priority}." if unknown_priority else ".")
            ),
        })
    else:
        steps.append({"key": "priority", "label": "Priority", "status": "unknown", "statement": "Priority is not recorded."})

    if strategy:
        steps.append({
            "key": "strategy",
            "label": "Migration strategy",
            "status": "established" if strategy["resolved"] else "unresolved",
            "statement": (
                f"{strategy['label'] or strategy['strategy']} ({strategy['confidence'] or 'unknown'} confidence)"
                + (f": {strategy['rationale']}" if strategy["rationale"] else ".")
            ),
        })
    else:
        steps.append({"key": "strategy", "label": "Migration strategy", "status": "unknown", "statement": "No migration strategy is recorded."})

    pqc_status = {
        "selected": "established",
        "unresolved": "unresolved",
        "not-applicable": "not-applicable",
    }.get(pqc["status"], "unknown")
    steps.append({
        "key": "pqc",
        "label": "PQC path",
        "status": pqc_status,
        "statement": (
            f"{pqc['selected_component']} ({pqc['role_family']})."
            if pqc["status"] == "selected"
            else pqc["note"] or "No PQC path is recorded."
        ),
    })

    return steps


def build_finding_evidence(bom_ref: str, records: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The evidence record for one finding, or None if bom_ref is not a finding."""

    source = records["assets"].get(bom_ref)

    if source is None:
        return None

    risk_record = records["risk"].get(bom_ref) or {}
    blast = records["blast"].get(bom_ref) or {}
    complexity = records["complexity"].get(bom_ref) or {}
    priority_record = records["priority"].get(bom_ref) or {}
    plan_record = records["plan"].get(bom_ref) or {}
    component = records["cbom_components"].get(bom_ref)

    classification = _as_dict(risk_record.get("classification"))
    strategy_record = _as_dict(plan_record.get("migration_strategy"))

    identity = _identity(bom_ref, source, classification, component, records)
    purpose = _purpose(classification)
    source_evidence = _source(source, risk_record, blast, records)
    quantum = _quantum(classification, _as_dict(risk_record.get("risk_assessment")))
    risk = _risk(risk_record)
    priority = _priority(priority_record)
    strategy = _strategy(strategy_record, records)
    pqc = _pqc(bom_ref, plan_record, strategy_record, records)

    return {
        "bom_ref": bom_ref,
        "identity": identity,
        "purpose": purpose,
        "source": source_evidence,
        "quantum": quantum,
        "risk": risk,
        "migration": {
            "blast_radius": _blast_radius(blast),
            "complexity": _complexity(complexity),
            "priority": priority,
            "strategy": strategy,
            "pqc": pqc,
        },
        "chain": _chain(identity, purpose, source_evidence, quantum, risk, priority, strategy, pqc),
    }

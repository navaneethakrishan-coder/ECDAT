"""The ECDAT facts the chat assistant is allowed to see.

The assistant is only useful if it answers from ECDAT's own analysis
rather than from general knowledge about cryptography, so this module
assembles a context from the generated dataset: the repository that was
scanned, the portfolio summary, and -- when the user has a finding
selected -- that finding's evidence, risk, strategy, impact and actions.

Two rules shape everything here:

* **Only ECDAT results.** Nothing is computed, inferred or invented; every
  value is copied from a pipeline output. Absent values stay absent so the
  assistant can say "ECDAT did not record that" instead of guessing.
* **Only ECDAT results.** No environment variables, no file paths, no
  credentials, no request internals. `build_context` reads the same
  generated JSON the dashboard reads and nothing else.
"""

import json
from pathlib import Path

from services.evidence_explorer import build_finding_evidence, load_evidence_records
from services.recommendation_state import selected_pqc_component, strategy_name

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR.parent / "data"

REPORT_FILE = "ecdat-migration-report.json"
BLAST_FILE = "ecdat-blast-radius.json"
PRIORITY_FILE = "ecdat-migration-priority.json"
CBOM_FILE = "keycloak-cbom.json"
SCAN_FILE = "ecdat-scan.json"

# How many findings the portfolio context lists. Enough for "what should I
# migrate first", small enough to keep the prompt focused.
TOP_FINDINGS = 8

# How many source occurrences the evidence context carries, and how much of
# each captured line. Enough to recognise the call sites; not a source dump.
MAX_OCCURRENCES = 6
MAX_SNIPPET_CHARS = 200


def _load(filename, data_dir=None):
    path = Path(data_dir or DATA_DIR) / filename
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def _repository(data_dir=None):
    """Which repository the current dataset came from, if it is recorded."""
    cbom = _load(CBOM_FILE, data_dir) or {}
    properties = {
        item.get("name"): item.get("value")
        for item in (cbom.get("metadata", {}).get("properties") or [])
        if isinstance(item, dict)
    }

    repository = {
        "git_url": properties.get("gitUrl"),
        "branch": properties.get("revision"),
        "commit": properties.get("commit"),
        "cbom_components": len(cbom.get("components") or []),
    }

    # The scan record adds provenance: whether this CBOM came from a scan
    # just run or from one CBOMKit already held.
    scan = _load(SCAN_FILE, data_dir) or {}
    source = (scan.get("result") or {}).get("source") or {}
    if source.get("freshness"):
        repository["cbom_freshness"] = source["freshness"]
        repository["cbom_created_at"] = source.get("cbom_created_at")
    if scan.get("status"):
        repository["last_scan_status"] = scan["status"]

    return {key: value for key, value in repository.items() if value not in (None, "")}


def _finding_context(record, blast=None, priority=None):
    """One finding, as ECDAT recorded it."""
    strategy = record.get("migration_strategy") or {}
    recommendation = record.get("recommendation") or {}
    classification = record.get("classification") or {}
    risk = record.get("current_risk") or {}

    context = {
        "bom_ref": record.get("bom_ref"),
        "name": record.get("asset"),
        "category": classification.get("category"),
        "quantum_status": classification.get("quantum_status"),
        "purpose": {
            "resolved": strategy.get("resolved_purposes"),
            "confidence": strategy.get("purpose_confidence"),
            "evidence_source": strategy.get("purpose_evidence_source"),
        },
        "risk": {
            "score": risk.get("score"),
            "severity": risk.get("severity"),
        },
        "migration_strategy": {
            "strategy": strategy_name(strategy) or strategy.get("strategy"),
            "confidence": strategy.get("confidence"),
            "reason_code": strategy.get("reason_code"),
            "rationale": strategy.get("rationale"),
            "pqc_component": selected_pqc_component(strategy),
            "construction": strategy.get("construction"),
            "inherited_from": strategy.get("inherited_from"),
            "review_options": strategy.get("review_options"),
        },
        "recommendation_state": {
            "decision": recommendation.get("decision"),
            "confirmed": recommendation.get("confirmed"),
            "selected_component": recommendation.get("selected_component"),
            # Ranking output is passed through labelled, never as a
            # recommendation -- the strategy layer is authoritative.
            "ranking_model_candidate": (recommendation.get("ranking_model") or {}).get("candidate"),
        },
        "ranked_candidates": [
            {"algorithm": item.get("algorithm") or item.get("candidate"), "score": item.get("score")}
            for item in (record.get("ranked_candidates") or [])[:3]
        ],
        "source_impact": record.get("source_impact"),
        "migration_actions": (record.get("migration_actions") or [])[:5],
        "action_count": record.get("action_count"),
        "risk_explanation": (record.get("explanation") or {}).get("summary")
        if isinstance(record.get("explanation"), dict)
        else record.get("explanation"),
    }

    if blast:
        context["blast_radius"] = {
            "score": blast.get("blast_radius_score"),
            "severity": blast.get("severity"),
            "direct_dependencies": (blast.get("direct_dependencies") or {}).get("count"),
            "direct_dependents": (blast.get("direct_dependents") or {}).get("count"),
            "transitive_dependents": (blast.get("transitive_dependents") or {}).get("count"),
            "relationship_source": "CycloneDX dependsOn relationships recorded in the CBOM",
        }

    if priority:
        migration_priority = priority.get("migration_priority") or {}
        context["migration_priority"] = {
            "priority": migration_priority.get("priority"),
            "score": migration_priority.get("priority_score"),
            "unknown_factors": migration_priority.get("unknown_factors"),
        }
        context["migration_complexity"] = priority.get("migration_complexity")
        context["business_criticality"] = priority.get("business_criticality")
        context["mosca_analysis"] = priority.get("mosca_analysis")

    return context


def _evidence_context(bom_ref, data_dir=None):
    """What ECDAT actually observed for this finding.

    The Evidence Explorer's record, trimmed to what an explanation needs:
    where the finding was seen in the *scanned repository*, how confident
    ECDAT is in that observation, and the dependency refs the blast radius
    was computed from. Repository-relative locations are ECDAT findings and
    are already on screen; nothing here reads the host filesystem.
    """
    try:
        records = load_evidence_records(Path(data_dir or DATA_DIR))
        evidence = build_finding_evidence(bom_ref, records)
    except (OSError, ValueError, KeyError):
        return None

    if not evidence:
        return None

    source = evidence.get("source") or {}
    occurrences = [
        {
            "location": item.get("location"),
            "line": item.get("line"),
            "context": (item.get("context") or "")[:MAX_SNIPPET_CHARS] or None,
        }
        for item in (source.get("occurrences") or [])[:MAX_OCCURRENCES]
    ]

    context = {
        "occurrence_count": source.get("occurrence_count"),
        "occurrences": occurrences,
        "evidence_quality": source.get("evidence_quality"),
        "evidence_confidence": source.get("evidence_confidence"),
        "detection": {
            "in_raw_cbom": (evidence.get("identity") or {}).get("in_raw_cbom"),
            "asset_type": (evidence.get("identity") or {}).get("asset_type"),
            "oid": (evidence.get("identity") or {}).get("oid"),
        },
        "purpose_evidence": evidence.get("purpose"),
        # The recorded dependency relationships, so blast radius can be
        # explained from what the CBOM states rather than from inference.
        "dependencies": source.get("dependencies"),
        # ECDAT's own derivation chain, finding -> strategy.
        "reasoning_chain": evidence.get("chain"),
    }

    return {key: value for key, value in context.items() if value not in (None, [], {})}


def build_context(bom_ref=None, data_dir=None):
    """The ECDAT context for a chat turn.

    With a `bom_ref`, the selected finding is the primary context and the
    portfolio is summarised around it. Without one, the whole portfolio is
    described so questions like "what should I migrate first" can be
    answered from real records.
    """
    report = _load(REPORT_FILE, data_dir)
    if not report:
        return {
            "dataset_available": False,
            "note": "No ECDAT analysis is present in this deployment yet; scan a repository first.",
        }

    assets = report.get("assets") or []
    summary = report.get("summary") or {}
    blast_by_ref = {
        item.get("bom_ref"): item for item in ((_load(BLAST_FILE, data_dir) or {}).get("assets") or [])
    }
    priority_by_ref = {
        item.get("bom_ref"): item for item in ((_load(PRIORITY_FILE, data_dir) or {}).get("assets") or [])
    }

    context = {
        "dataset_available": True,
        "repository": _repository(data_dir),
        "portfolio": {
            "total_findings": summary.get("total_assets", len(assets)),
            "risk_severity_distribution": summary.get("risk_severity_distribution"),
            "migration_strategy_distribution": summary.get("migration_strategy_distribution"),
            "assets_with_pqc_candidates": summary.get("assets_with_pqc_candidates"),
            "high_or_critical_priority_assets": summary.get("high_or_critical_priority_assets"),
            "total_migration_actions": summary.get("total_migration_actions"),
        },
    }

    # Highest-priority findings, so "what first" is answerable from records.
    def priority_score(record):
        priority = (priority_by_ref.get(record.get("bom_ref")) or {}).get("migration_priority") or {}
        return priority.get("priority_score") or 0

    context["top_findings"] = [
        {
            "bom_ref": record.get("bom_ref"),
            "name": record.get("asset"),
            "risk": (record.get("current_risk") or {}).get("severity"),
            "risk_score": (record.get("current_risk") or {}).get("score"),
            "priority": ((priority_by_ref.get(record.get("bom_ref")) or {}).get("migration_priority") or {}).get(
                "priority"
            ),
            "strategy": (record.get("migration_strategy") or {}).get("strategy"),
            "pqc_component": (record.get("migration_strategy") or {}).get("pqc_component"),
        }
        for record in sorted(assets, key=priority_score, reverse=True)[:TOP_FINDINGS]
    ]

    if bom_ref:
        record = next((item for item in assets if item.get("bom_ref") == bom_ref), None)
        if record:
            selected = _finding_context(
                record,
                blast_by_ref.get(bom_ref),
                priority_by_ref.get(bom_ref),
            )
            evidence = _evidence_context(bom_ref, data_dir)
            if evidence:
                selected["evidence"] = evidence
            context["selected_finding"] = selected
        else:
            # Say so plainly rather than answering about a different finding.
            context["selected_finding_error"] = (
                f"No finding with bom_ref '{bom_ref}' exists in the current ECDAT dataset."
            )

    return context

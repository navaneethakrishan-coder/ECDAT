import json
from pathlib import Path

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:14b"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR.parent / "data"


def load_json(filename):
    path = DATA_DIR / filename

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


REPORT_FILE = "ecdat-migration-report.json"


def find_report_asset(report, asset_name):
    """
    Look up one asset record in the unified ECDAT migration report.

    ecdat-migration-report.json is the same authoritative dataset that
    backend/main.py's /api/asset/{name}, /api/migration-report/assets,
    and the dashboard itself are built from (see generate_migration_report.py).
    Reading it here -- instead of re-deriving risk/priority/pqc figures
    from separate intermediate pipeline files -- is what guarantees the
    AI advisor can never report a different risk/migration value than
    the rest of the UI for the same asset. See docs/ARCHITECTURE.md §5
    and docs/CHANGELOG.md (2026-09-14 AI data-consistency fix).

    Matching uses the canonical CBOM bom-ref, so duplicate algorithm
    names cannot return advice for the wrong source finding.
    """

    if not isinstance(report, dict):
        return None

    assets = report.get("assets", [])

    if not isinstance(assets, list):
        return None

    target = str(asset_name).strip()

    for record in assets:

        if not isinstance(record, dict):
            continue

        if record.get("bom_ref") and str(record["bom_ref"]).strip() == target:
            return record

    return None


def build_context(asset_name):

    context = {
        "asset": asset_name
    }

    report = load_json(REPORT_FILE)

    record = find_report_asset(report, asset_name)

    if record is None:
        return context

    context["asset"] = record.get("asset", asset_name)
    context["bom_ref"] = record.get("bom_ref")

    # ---------------------------------------------------------
    # Risk (identical source/values to the dashboard's "current risk")
    # ---------------------------------------------------------

    current_risk = record.get("current_risk", {}) or {}
    classification = record.get("classification", {}) or {}

    context["risk"] = {
        "score": current_risk.get("score"),
        "severity": current_risk.get("severity"),
        "quantum_status": classification.get("quantum_status"),
        "category": classification.get("category"),
    }

    # Repository-specific purpose (see services/purpose_resolver.py):
    # what this finding is actually used for, resolved from this
    # asset's own CBOM/source evidence rather than assumed from its
    # algorithm name -- and how confident that resolution is, so the
    # model doesn't state a low-confidence guess as settled fact.
    context["purpose"] = {
        "resolved": classification.get("purpose"),
        "usage": classification.get("usage"),
        "confidence": classification.get("purpose_confidence"),
        "evidence_source": classification.get("purpose_evidence_source"),
        "needs_review": classification.get("purpose_needs_review", False),
    }

    # ---------------------------------------------------------
    # Migration impact: priority / blast radius / complexity
    # ---------------------------------------------------------

    migration_impact = record.get("migration_impact", {}) or {}
    priority = migration_impact.get("priority", {}) or {}
    blast_radius = migration_impact.get("blast_radius", {}) or {}
    complexity = migration_impact.get("complexity", {}) or {}

    context["priority"] = {
        "priority_score": priority.get("score"),
        "priority": priority.get("level"),
    }

    context["blast_radius"] = {
        "score": blast_radius.get("score"),
        "severity": blast_radius.get("severity"),
    }

    context["complexity"] = {
        "score": complexity.get("score"),
        "level": complexity.get("level"),
    }

    # ---------------------------------------------------------
    # PQC migration + recommended candidate
    # ---------------------------------------------------------

    pqc_migration = record.get("pqc_migration", {}) or {}
    recommendation = record.get("recommendation", {}) or {}
    ranked_candidates = record.get("ranked_candidates", []) or []

    context["pqc"] = {
        "migration_type": pqc_migration.get("migration_type"),
        "pqc_applicable": pqc_migration.get("pqc_applicable"),
        "confidence": pqc_migration.get("confidence"),
    }

    if recommendation.get("candidate"):

        recommended = {
            "candidate": recommendation.get("candidate"),
            "score": recommendation.get("candidate_score"),
            "rank": recommendation.get("candidate_rank"),
            "confidence": recommendation.get("confidence"),
            "reason": recommendation.get("reason"),
        }

        if isinstance(ranked_candidates, list) and ranked_candidates:

            top = ranked_candidates[0]

            if isinstance(top, dict):
                recommended["family"] = top.get("family")
                recommended["compatibility"] = top.get("compatibility")
                recommended["tradeoffs"] = top.get("tradeoffs", [])

        context["pqc"]["recommended_candidate"] = recommended

    # ---------------------------------------------------------
    # Source impact (previously omitted, despite the dashboard's AI
    # advisor panel already claiming to review it)
    # ---------------------------------------------------------

    source_impact = record.get("source_impact", {}) or {}

    context["source_impact"] = {
        "impact_level": source_impact.get("impact_level"),
        "affected_file_count": source_impact.get("affected_file_count"),
        "affected_class_count": source_impact.get("affected_class_count"),
        "affected_function_count": source_impact.get("affected_function_count"),
    }

    # ---------------------------------------------------------
    # Migration actions
    # ---------------------------------------------------------

    actions = record.get("migration_actions", [])

    if isinstance(actions, list):
        context["actions"] = actions[:5]

    return context


def generate_advice(asset_name):

    context = build_context(asset_name)

    prompt = f"""
You are the ECDAT AI Migration Advisor.

Use ONLY the supplied ECDAT results as factual
information.

Do not invent scores, assets, dependencies,
PQC algorithms, or migration decisions.

The supplied "purpose" field shows how this finding's cryptographic
purpose was resolved and how confident that resolution is. If its
confidence is LOW or needs_review is true, say so plainly rather than
stating the purpose as settled fact.

Asset:
{asset_name}

ECDAT results:
{json.dumps(context, separators=(",", ":"))}

Give a concise developer-oriented answer.

Use exactly these sections:

RISK:
Explain the current risk.

MIGRATION:
Explain the ECDAT migration decision.

PQC:
Explain the recommended PQC candidate, if available.

ACTIONS:
Give the most important developer actions.

IMPACT:
Explain the expected source-code or architectural impact.

SUMMARY:
Give one short recommendation.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "think": False,
    "options": {
        "temperature": 0.2,
        "num_predict": 300,
    },
},
        timeout=300,
    )

    response.raise_for_status()

    result = response.json()

    return {
        "asset": asset_name,
        "model": MODEL,
        "advice": result.get(
            "response",
            ""
        ).strip(),
    }

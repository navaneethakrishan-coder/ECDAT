import json
from pathlib import Path

import requests

from services.recommendation_state import NEEDS_REVIEW, selected_pqc_component, strategy_name


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

    strategy_record = record.get("migration_strategy") or {}

    if strategy_name(strategy_record):

        # The migration strategy is authoritative. Only a DIRECT_PQC /
        # HYBRID strategy has a recommended PQC component; a NEEDS_REVIEW
        # finding gets no recommended_candidate at all (its ranking
        # output, if any, is passed separately and labelled as such), and
        # KEEP gets neither.
        selected = selected_pqc_component(strategy_record)

        if selected:
            recommended = {
                "candidate": selected,
                "strategy": strategy_record.get("strategy"),
                "family": strategy_record.get("pqc_family"),
                "confidence": strategy_record.get("confidence"),
            }

            match = next(
                (
                    candidate
                    for candidate in ranked_candidates
                    if isinstance(candidate, dict) and candidate.get("candidate") == selected
                ),
                None,
            )

            if match:
                recommended["rank"] = match.get("rank")
                recommended["score"] = match.get("score")
                recommended["compatibility"] = match.get("compatibility")
                recommended["tradeoffs"] = match.get("tradeoffs", [])

            context["pqc"]["recommended_candidate"] = recommended

        elif strategy_name(strategy_record) == NEEDS_REVIEW and ranked_candidates:
            top = ranked_candidates[0] if isinstance(ranked_candidates[0], dict) else {}
            context["pqc"]["ranking_model_output"] = {
                "top_ranked_candidate": top.get("candidate"),
                "family": top.get("family"),
                "score": top.get("score"),
                "status": "NOT A RECOMMENDATION",
                "note": (
                    "Ranking-model output only. The migration strategy is "
                    "NEEDS_REVIEW, so no PQC candidate is selected until the "
                    "cryptographic role is confirmed."
                ),
            }

    elif recommendation.get("candidate"):

        # Legacy dataset without migration strategies.
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
    # Purpose-aware migration strategy (services/migration_strategy.py)
    # -- the evidence-based decision (KEEP / DIRECT_PQC / HYBRID /
    # NEEDS_REVIEW), so the model explains it rather than inventing one.
    # ---------------------------------------------------------

    strategy = record.get("migration_strategy") or {}

    if strategy:
        context["migration_strategy"] = {
            "strategy": strategy.get("strategy"),
            "label": strategy.get("label"),
            "role": strategy.get("purpose_class_label"),
            "classical_component": strategy.get("classical_component"),
            "pqc_component": strategy.get("pqc_component"),
            "confidence": strategy.get("confidence"),
            "rationale": strategy.get("rationale"),
            "harvest_now_decrypt_later": strategy.get("harvest_now_decrypt_later"),
            "classical_hardening": (strategy.get("classical_hardening") or {}).get("status"),
        }

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

The supplied "migration_strategy" field is ECDAT's evidence-based
migration decision (KEEP, DIRECT_PQC, HYBRID or NEEDS_REVIEW). Explain
that decision; do not recommend a different strategy or PQC algorithm.
If it is NEEDS_REVIEW, say that the cryptographic role must be
confirmed before any replacement is chosen.

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
Explain the recommended PQC candidate only if "recommended_candidate"
is supplied. If only "ranking_model_output" is supplied, state that it
is ranking-model output, not a recommendation, and that no PQC
candidate is selected until the review is resolved.

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

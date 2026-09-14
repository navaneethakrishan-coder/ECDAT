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


def get_records(data):
    if not data:
        return []

    if isinstance(data, list):
        return data

    return data.get(
        "assets",
        data.get("records", [])
    )


def find_asset(data, asset_name):

    records = get_records(data)

    for record in records:

        name = (
            record.get("name")
            or record.get("asset")
            or record.get("asset_name")
        )

        if name == asset_name:
            return record

    return None

def build_context(asset_name):

    context = {
        "asset": asset_name
    }

    # ---------------------------------------------------------
    # Risk
    # ---------------------------------------------------------

    risk_data = load_json(
        "ecdat-contextual-risk-assets.json"
    )

    risk_record = find_asset(
        risk_data,
        asset_name
    )

    if risk_record:
        risk = risk_record.get(
            "contextual_risk",
            {}
        )

        context["risk"] = {
            "final_score": risk.get(
                "final_score"
            ),
            "severity": risk.get(
                "severity"
            ),
            "quantum_status": risk.get(
                "base_risk",
                {}
            ).get("quantum_status"),
            "category": risk.get(
                "base_risk",
                {}
            ).get("category"),
            "migration_urgency": risk.get(
                "mosca_analysis",
                {}
            ).get("migration_urgency"),
        }

    # ---------------------------------------------------------
    # Priority
    # ---------------------------------------------------------

    priority_data = load_json(
        "ecdat-migration-priority.json"
    )

    priority_record = find_asset(
        priority_data,
        asset_name
    )

    if priority_record:

        priority = priority_record.get(
            "migration_priority",
            {}
        )

        context["priority"] = {
            "priority_score": priority.get(
                "priority_score"
            ),
            "priority": priority.get(
                "priority"
            ),
        }

        context["blast_radius"] = {
            "score": priority_record.get(
                "blast_radius",
                {}
            ).get("score"),
            "severity": priority_record.get(
                "blast_radius",
                {}
            ).get("severity"),
        }

        context["complexity"] = {
            "score": priority_record.get(
                "migration_complexity",
                {}
            ).get("score"),
            "level": priority_record.get(
                "migration_complexity",
                {}
            ).get("level"),
        }

    # ---------------------------------------------------------
    # PQC Migration Plan
    # ---------------------------------------------------------

    pqc_data = load_json(
        "ecdat-pqc-migration-plan.json"
    )

    pqc_record = find_asset(
        pqc_data,
        asset_name
    )

    if pqc_record:

        context["pqc"] = {
            "migration_type": pqc_record.get(
                "pqc_analysis",
                {}
            ).get("migration_type"),
            "pqc_applicable": pqc_record.get(
                "pqc_analysis",
                {}
            ).get("pqc_applicable"),
            "confidence": pqc_record.get(
                "pqc_analysis",
                {}
            ).get("confidence"),
        }

        candidates = pqc_record.get(
            "ranked_candidates",
            []
        )

        if candidates:

            best = candidates[0]

            context["pqc"]["recommended_candidate"] = {
                "candidate": best.get(
                    "candidate"
                ),
                "family": best.get(
                    "family"
                ),
                "score": best.get(
                    "score"
                ),
                "rank": best.get(
                    "rank"
                ),
                "compatibility": best.get(
                    "compatibility"
                ),
                "reason": best.get(
                    "reason"
                ),
                "tradeoffs": best.get(
                    "tradeoffs",
                    []
                ),
            }

    # ---------------------------------------------------------
    # Migration Actions
    # ---------------------------------------------------------

    actions_data = load_json(
        "ecdat-migration-actions.json"
    )

    actions_record = find_asset(
        actions_data,
        asset_name
    )

    if actions_record:

        actions = actions_record.get(
            "actions",
            []
        )

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
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, ConfigDict, Field
from services.ai_advisor import generate_advice
from services.scanning import ScanService, TargetError
from services.blast_radius_view import build_blast_radius_view, load_blast_radius_records
from services.evidence_explorer import build_finding_evidence, load_evidence_records
from services.recommendation_state import has_selected_pqc_path, reconcile_recommendation
from services.migration_scenario import (
    load_finding_snapshots,
    load_ranked_candidates,
    simulate_pqc_option,
    simulate_portfolio,
    simulation_options,
)



# ============================================================
# ECDAT API CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


app = FastAPI(
    title="ECDAT API",
    description=(
        "ECDAT Cryptographic Discovery and "
        "Post-Quantum Migration API"
    ),
    version="1.0.0",
)
class AnalyzeRequest(BaseModel):
    repository: str
    branch: str = "main"


class AIAdvisorRequest(BaseModel):
    asset_name: str


# The scan lifecycle lives in services/scanning: target validation →
# scanner selection → CBOMKit → CBOM validation/normalization → the
# existing ECDAT pipeline. The API only starts scans and reports the
# service's real state.
scan_service = ScanService()


def analysis_status_payload():
    """Scan state, including the keys the original /api/analyze/status returned."""
    state = scan_service.snapshot()
    return {
        # Original contract (unchanged keys and values).
        "status": state["status"],
        "repository": state["repository"],
        "branch": state["branch"],
        "message": state["message"],
        "error": state["error"],
        # Real scan telemetry.
        "scan_id": state["scan_id"],
        "error_code": state["error_code"],
        "target": state["target"],
        "scanner": state["scanner"],
        "stages": state["stages"],
        "pipeline_stages": state["pipeline_stages"],
        "current_stage": state["current_stage"],
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
        "duration_seconds": state["duration_seconds"],
        "validation": state["validation"],
        "result": state["result"],
    }


def start_scan_request(request: AnalyzeRequest):
    try:
        state = scan_service.start(request.repository, request.branch)
    except TargetError as error:
        raise HTTPException(
            status_code=400,
            detail={"reason_code": error.code, "reason": error.message},
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return {
        "status": "started",
        "scan_id": state["scan_id"],
        "repository": state["repository"],
        "branch": state["branch"],
        "message": state["message"],
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # No request in this app carries cookies/auth headers, and
    # "allow_origins=*" combined with allow_credentials=True is an
    # invalid CORS combination per spec (browsers reject it) --
    # credentials support was never actually used.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATA LOADER
# ============================================================

def load_json(filename: str):
    path = DATA_DIR / filename

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found: {filename}",
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in {filename}: {exc}",
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "name": "ECDAT API",
        "version": "1.0.0",
        "status": "running",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ECDAT backend",
    }


# ============================================================
# BUILD STATUS FROM FINAL MIGRATION REPORT
# ============================================================

def build_status(report):
    assets = report.get("assets", [])

    migration_action_count = 0
    pqc_candidate_count = 0
    high_or_critical_priority_count = 0

    migration_types = {}
    recommendations = {}
    risk_severities = {}
    source_impacts = {}

    for asset in assets:

        # ----------------------------------------------------
        # Migration actions
        # ----------------------------------------------------

        actions = asset.get(
            "migration_actions",
            [],
        )

        migration_action_count += len(actions)

        # ----------------------------------------------------
        # PQC migration
        # ----------------------------------------------------

        pqc = asset.get(
            "pqc_migration",
            {},
        )

        # A finding counts as a PQC candidate only when its migration
        # strategy selected a PQC replacement path (DIRECT_PQC / HYBRID).
        # A ranking-model candidate alone -- e.g. for a NEEDS_REVIEW
        # finding -- is not a PQC candidate.
        if has_selected_pqc_path(asset.get("migration_strategy")):
            pqc_candidate_count += 1

        migration_type = pqc.get(
            "migration_type"
        )

        if migration_type:
            migration_types[migration_type] = (
                migration_types.get(
                    migration_type,
                    0,
                ) + 1
            )

        # ----------------------------------------------------
        # Recommendation
        # ----------------------------------------------------

        recommendation = asset.get(
            "recommendation",
            {},
        )

        decision = recommendation.get(
            "decision"
        )

        if decision:
            recommendations[decision] = (
                recommendations.get(
                    decision,
                    0,
                ) + 1
            )

        # ----------------------------------------------------
        # Risk severity
        # ----------------------------------------------------

        current_risk = asset.get(
            "current_risk",
            {},
        )

        risk_severity = current_risk.get(
            "severity"
        )

        if risk_severity:
            risk_severities[risk_severity] = (
                risk_severities.get(
                    risk_severity,
                    0,
                ) + 1
            )

        # ----------------------------------------------------
        # Migration priority
        # ----------------------------------------------------

        migration_impact = asset.get(
            "migration_impact",
            {},
        )

        priority = migration_impact.get(
            "priority",
            {},
        )

        priority_level = priority.get(
            "level"
        )

        if priority_level in {
            "HIGH",
            "CRITICAL",
        }:
            high_or_critical_priority_count += 1

        # ----------------------------------------------------
        # Source impact
        # ----------------------------------------------------

        source_impact = asset.get(
            "source_impact",
            {},
        )

        impact_level = source_impact.get(
            "impact_level"
        )

        if impact_level:
            source_impacts[impact_level] = (
                source_impacts.get(
                    impact_level,
                    0,
                ) + 1
            )

    return {
        "status": "ready",

        "total_assets": len(assets),

        "total_migration_actions": (
            migration_action_count
        ),

        "assets_with_pqc_candidates": (
            pqc_candidate_count
        ),

        "high_or_critical_priority_assets": (
            high_or_critical_priority_count
        ),

        "migration_type_distribution": (
            migration_types
        ),

        "recommendation_distribution": (
            recommendations
        ),

        "risk_severity_distribution": (
            risk_severities
        ),

        "source_impact_distribution": (
            source_impacts
        ),
    }


# ============================================================
# STATUS
# ============================================================

@app.get("/api/status")
def get_status():

    report = load_json(
        "ecdat-migration-report.json"
    )

    return build_status(report)


# ============================================================
# SUMMARY
# ============================================================

@app.get("/api/summary")
def get_summary():

    report = load_json(
        "ecdat-migration-report.json"
    )

    status = build_status(report)

    return {
        "total_assets": status[
            "total_assets"
        ],

        "total_migration_actions": status[
            "total_migration_actions"
        ],

        "assets_with_pqc_candidates": status[
            "assets_with_pqc_candidates"
        ],

        "high_or_critical_priority_assets": status[
            "high_or_critical_priority_assets"
        ],

        "migration_type_distribution": status[
            "migration_type_distribution"
        ],

        "recommendation_distribution": status[
            "recommendation_distribution"
        ],

        "risk_severity_distribution": status[
            "risk_severity_distribution"
        ],

        "source_impact_distribution": status[
            "source_impact_distribution"
        ],
    }
# ============================================================
# CRYPTO ASSET INVENTORY
# ============================================================

@app.get("/api/assets")
def get_assets():
    """
    Return the complete cryptographic asset inventory
    discovered by ECDAT.
    """

    data = load_json(
        "ecdat-assets.json"
    )

    # Support both direct-list and dictionary datasets.
    if isinstance(data, list):
        assets = data

    elif isinstance(data, dict):
        assets = data.get(
            "assets",
            [],
        )

    else:
        assets = []

    return {
        "total_assets": len(assets),
        "assets": assets,
    }


# ============================================================
# SINGLE CRYPTO ASSET
# ============================================================

@app.get("/api/assets/{asset_name}")
def get_crypto_asset(asset_name: str):
    """
    Return the original cryptographic inventory
    record for a single asset.
    """

    data = load_json(
        "ecdat-assets.json"
    )

    if isinstance(data, list):
        assets = data

    elif isinstance(data, dict):
        assets = data.get(
            "assets",
            [],
        )

    else:
        assets = []

    for asset in assets:

        if asset.get("bom_ref") and str(asset["bom_ref"]) == asset_name:
            return asset

    raise HTTPException(
        status_code=404,
        detail=f"Crypto asset not found: {asset_name}",
    )
# ============================================================
# RISK & PRIORITY API
# ============================================================

def get_asset_list(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("assets", [])

    return []


def find_asset(records, asset_name):
    for record in records:
        identity = record.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        finding_id = record.get("bom_ref") or record.get("asset_ref") or identity.get("bom_ref")
        if finding_id and str(finding_id) == asset_name:
            return record

    return None


@app.get("/api/risk")
def get_risk_data():
    """
    Return risk assessment for all cryptographic assets.
    """

    data = load_json(
        "ecdat-risk-assessed-assets.json"
    )

    assets = get_asset_list(data)

    return {
        "total_assets": len(assets),
        "assets": assets,
    }


@app.get("/api/risk/{asset_name}")
def get_asset_risk(asset_name: str):
    """
    Return risk assessment for one asset.
    """

    data = load_json(
        "ecdat-risk-assessed-assets.json"
    )

    assets = get_asset_list(data)

    asset = find_asset(
        assets,
        asset_name,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Risk data not found for asset: {asset_name}",
        )

    return asset


@app.get("/api/priority")
def get_priority_data():
    """
    Return migration priority data for all assets.
    """

    data = load_json(
        "ecdat-migration-priority.json"
    )

    assets = get_asset_list(data)

    return {
        "asset_count": len(assets),
        "priority_distribution": data.get(
            "priority_distribution",
            {},
        ) if isinstance(data, dict) else {},
        "weights": data.get(
            "weights",
            {},
        ) if isinstance(data, dict) else {},
        "assets": assets,
    }


@app.get("/api/priority/{asset_name}")
def get_asset_priority(asset_name: str):
    """
    Return migration priority for one asset.
    """

    data = load_json(
        "ecdat-migration-priority.json"
    )

    assets = get_asset_list(data)

    asset = find_asset(
        assets,
        asset_name,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Priority data not found for asset: {asset_name}",
        )

    return asset


@app.get("/api/complexity")
def get_complexity_data():
    """
    Return migration complexity for all assets.
    """

    data = load_json(
        "ecdat-migration-complexity.json"
    )

    assets = get_asset_list(data)

    return {
        "asset_count": len(assets),
        "assets": assets,
    }


@app.get("/api/complexity/{asset_name}")
def get_asset_complexity(asset_name: str):
    """
    Return migration complexity for one asset.
    """

    data = load_json(
        "ecdat-migration-complexity.json"
    )

    assets = get_asset_list(data)

    asset = find_asset(
        assets,
        asset_name,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Complexity data not found for asset: {asset_name}",
        )

    return asset


@app.get("/api/blast-radius")
def get_blast_radius_data():
    """
    Return migration blast-radius data for all assets.
    """

    data = load_json(
        "ecdat-blast-radius.json"
    )

    assets = get_asset_list(data)

    return {
        "asset_count": len(assets),
        "dependency_count": data.get(
            "dependency_count",
            0,
        ) if isinstance(data, dict) else 0,
        "assets": assets,
    }


@app.get("/api/blast-radius/{bom_ref}/graph")
def get_blast_radius_graph(bom_ref: str):
    """
    Read-only relationship view for one finding: the recorded blast
    radius plus the named findings and CycloneDX dependsOn edges behind
    it (services/blast_radius_view.py). Nothing is recomputed.
    """

    try:
        records = load_blast_radius_records(DATA_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found: {Path(exc.filename or '').name}",
        )

    view = build_blast_radius_view(bom_ref, records)

    if view is None:
        raise HTTPException(
            status_code=404,
            detail={
                "reason_code": "unknown-finding",
                "reason": "No finding with this bom_ref exists in the ECDAT dataset.",
                "bom_ref": bom_ref,
            },
        )

    return view


@app.get("/api/blast-radius/{asset_name}")
def get_asset_blast_radius(asset_name: str):
    """
    Return blast-radius data for one asset.
    """

    data = load_json(
        "ecdat-blast-radius.json"
    )

    assets = get_asset_list(data)

    asset = find_asset(
        assets,
        asset_name,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail=f"Blast-radius data not found for asset: {asset_name}",
        )

    return asset
# ============================================================
# PQC MIGRATION API
# ============================================================

@app.get("/api/pqc")
def get_pqc_migration():
    """
    Return complete PQC migration analysis
    for all cryptographic assets.
    """

    data = load_json(
        "ecdat-pqc-migration.json"
    )

    if isinstance(data, dict):
        assets = data.get("assets", [])

        return {
            "project": data.get("project"),
            "stage": data.get("stage"),
            "description": data.get("description"),
            "summary": data.get("summary", {}),
            "assets": assets,
        }

    return {
        "total_assets": len(data),
        "assets": data,
    }


@app.get("/api/pqc/{asset_name}")
def get_asset_pqc_migration(asset_name: str):
    """
    Return PQC migration analysis for one asset.
    """

    data = load_json(
        "ecdat-pqc-migration.json"
    )

    assets = (
        data.get("assets", [])
        if isinstance(data, dict)
        else data
    )

    asset = find_asset(assets, asset_name)
    if asset:
        return asset

    raise HTTPException(
        status_code=404,
        detail=f"PQC migration data not found for asset: {asset_name}",
    )


@app.get("/api/pqc-ranking")
def get_pqc_ranking():
    """
    Return ranked PQC migration candidates.
    """

    data = load_json(
        "ecdat-pqc-ranked.json"
    )

    if not isinstance(data, dict):
        return {
            "top_candidates": [],
            "assets": [],
        }

    return {
        "project": data.get("project"),
        "report": data.get("report", {}),
        "summary": data.get("summary", {}),
        "mapping_validation": data.get(
            "mapping_validation",
            {},
        ),
        "top_candidates": data.get(
            "top_candidates",
            [],
        ),
        "assets": data.get(
            "assets",
            [],
        ),
    }


@app.get("/api/pqc-ranking/{asset_name}")
def get_asset_pqc_ranking(asset_name: str):
    """
    Return ranked PQC candidates for one asset.
    """

    data = load_json(
        "ecdat-pqc-ranked.json"
    )

    assets = (
        data.get("assets", [])
        if isinstance(data, dict)
        else []
    )

    asset = find_asset(assets, asset_name)
    if asset:
        return asset

    raise HTTPException(
        status_code=404,
        detail=f"PQC ranking not found for asset: {asset_name}",
    )
# ============================================================
# SOURCE IMPACT API
# ============================================================

@app.get("/api/source-impact")
def get_source_impact():
    """
    Return source-code impact analysis for all assets.
    """

    report = load_json(
        "ecdat-migration-report.json"
    )

    assets = report.get(
        "assets",
        [],
    )

    results = []

    for asset in assets:

        source_impact = asset.get(
            "source_impact",
            {},
        )

        results.append({
            "asset": asset.get("asset"),

            "affected_files": source_impact.get(
                "affected_files",
                [],
            ),

            "affected_file_count": source_impact.get(
                "affected_file_count",
                0,
            ),

            "affected_classes": source_impact.get(
                "affected_classes",
                [],
            ),

            "affected_class_count": source_impact.get(
                "affected_class_count",
                0,
            ),

            "affected_functions": source_impact.get(
                "affected_functions",
                [],
            ),

            "affected_function_count": source_impact.get(
                "affected_function_count",
                0,
            ),

            "impact_level": source_impact.get(
                "impact_level"
            ),
        })

    return {
        "total_assets": len(results),
        "assets": results,
    }


@app.get("/api/source-impact/{asset_name}")
def get_asset_source_impact(
    asset_name: str,
):
    """
    Return source-code impact information
    for one cryptographic asset.
    """

    report = load_json(
        "ecdat-migration-report.json"
    )

    assets = report.get(
        "assets",
        [],
    )

    for asset in assets:
        if asset.get("bom_ref") and str(asset["bom_ref"]) == asset_name:

            source_impact = asset.get(
                "source_impact",
                {},
            )

            return {
                "asset": asset.get("asset"),
                "bom_ref": asset.get("bom_ref"),

                "affected_files": source_impact.get(
                    "affected_files",
                    [],
                ),

                "affected_file_count": source_impact.get(
                    "affected_file_count",
                    0,
                ),

                "affected_classes": source_impact.get(
                    "affected_classes",
                    [],
                ),

                "affected_class_count": source_impact.get(
                    "affected_class_count",
                    0,
                ),

                "affected_functions": source_impact.get(
                    "affected_functions",
                    [],
                ),

                "affected_function_count": source_impact.get(
                    "affected_function_count",
                    0,
                ),

                "impact_level": source_impact.get(
                    "impact_level"
                ),
            }

    raise HTTPException(
        status_code=404,
        detail=(
            f"Source impact data not found "
            f"for asset: {asset_name}"
        ),
    )
# ============================================================
# MIGRATION ACTIONS API
# ============================================================

@app.get("/api/actions")
def get_migration_actions():
    """
    Return migration actions for all cryptographic assets.
    """

    data = load_json(
        "ecdat-migration-actions.json"
    )

    if isinstance(data, dict):
        assets = data.get("assets", [])

        return {
            "metadata": data.get("metadata", {}),
            "summary": data.get("summary", {}),
            "assets": assets,
        }

    return {
        "metadata": {},
        "summary": {
            "total_assets": len(data),
            "total_migration_actions": sum(
                item.get("action_count", 0)
                for item in data
                if isinstance(item, dict)
            ),
        },
        "assets": data,
    }


@app.get("/api/actions/{asset_name}")
def get_asset_migration_actions(
    asset_name: str,
):
    """
    Return migration actions for one cryptographic asset.
    """

    data = load_json(
        "ecdat-migration-actions.json"
    )

    assets = (
        data.get("assets", [])
        if isinstance(data, dict)
        else data
    )

    asset = find_asset(assets, asset_name)
    if asset:
        return asset

    raise HTTPException(
        status_code=404,
        detail=(
            f"Migration actions not found "
            f"for asset: {asset_name}"
        ),
    )




# ============================================================
# UNIFIED MIGRATION REPORT
# ============================================================

# ============================================================
# MIGRATION REPORT ASSET LIST
# ============================================================

@app.get("/api/migration-report/assets")
def get_report_assets():
    """
    Return the list of all cryptographic assets
    contained in the final ECDAT migration report.
    """

    report = load_json(
        "ecdat-migration-report.json"
    )

    assets = report.get(
        "assets",
        [],
    )

    return {
        "total_assets": len(assets),
        "assets": [
            {
                "asset": asset.get("asset"),
                "bom_ref": asset.get("bom_ref"),
                "asset_type": asset.get(
                    "identity",
                    {}
                ).get("asset_type"),
                "primitive": asset.get(
                    "identity",
                    {}
                ).get("primitive"),
                "risk_score": asset.get(
                    "current_risk",
                    {}
                ).get("score"),
                "risk_severity": asset.get(
                    "current_risk",
                    {}
                ).get("severity"),
                "migration_type": asset.get(
                    "pqc_migration",
                    {}
                ).get("migration_type"),
                "pqc_applicable": asset.get(
                    "pqc_migration",
                    {}
                ).get("pqc_applicable"),
                "recommendation": reconcile_recommendation(
                    asset.get("recommendation"),
                    asset.get("migration_strategy"),
                ).get("decision"),
                "candidate": reconcile_recommendation(
                    asset.get("recommendation"),
                    asset.get("migration_strategy"),
                ).get("candidate"),
                "source_impact": asset.get(
                    "source_impact",
                    {}
                ).get("impact_level"),
                "purpose_confidence": asset.get(
                    "classification",
                    {}
                ).get("purpose_confidence"),
                "purpose_needs_review": asset.get(
                    "classification",
                    {}
                ).get("purpose_needs_review", False),
                "migration_strategy": (
                    asset.get("migration_strategy") or {}
                ).get("strategy"),
                "strategy_pqc_component": (
                    asset.get("migration_strategy") or {}
                ).get("pqc_component"),
                "action_count": asset.get(
                    "action_count",
                    len(
                        asset.get(
                            "migration_actions",
                            [],
                        )
                    ),
                ),
            }
            for asset in assets
        ],
    }


# ============================================================
# SINGLE MIGRATION REPORT ASSET
# ============================================================

@app.get("/api/migration-report/assets/{asset_name}")
def get_report_asset(asset_name: str):
    """
    Return the complete migration report
    for a single cryptographic asset.
    """

    report = load_json(
        "ecdat-migration-report.json"
    )

    assets = report.get(
        "assets",
        [],
    )

    for asset in assets:

        if asset.get("bom_ref") and str(asset["bom_ref"]) == asset_name:
            return {
                **asset,
                "recommendation": reconcile_recommendation(
                    asset.get("recommendation"),
                    asset.get("migration_strategy"),
                ),
            }

    raise HTTPException(
        status_code=404,
        detail=f"Asset not found: {asset_name}",
    )


# ============================================================
# MIGRATION ACTIONS
# ============================================================

@app.get("/api/migration-actions")
def get_migration_actions():

    return load_json(
        "ecdat-migration-actions.json"
    )


# ============================================================
# PQC MIGRATION PLAN
# ============================================================

@app.get("/api/pqc-migration-plan")
def get_pqc_migration_plan():

    return load_json(
        "ecdat-pqc-migration-plan.json"
    )


# NOTE: a second, bare `@app.get("/api/pqc-ranking")` used to be defined
# here as well. Starlette matches routes in registration order, so that
# later definition was always dead code (the richer handler above,
# defined first, is the one that ever actually ran) — removed as part
# of the 2026-09-14 backend consolidation. See docs/CHANGELOG.md.


# ============================================================
# SINGLE ASSET
# ============================================================

# ============================================================
# UNIFIED ASSET REPORT
# ============================================================

@app.get("/api/asset/{asset_name}")
def get_asset(asset_name: str):
    """
    Return the complete ECDAT decision record for one asset.

    Combines:
        - Asset inventory
        - Risk assessment
        - Migration priority
        - Migration complexity
        - Blast radius
        - PQC migration
        - PQC ranking
        - Source impact
        - Migration actions
        - Final migration report
    """

    # --------------------------------------------------------
    # Load all required ECDAT datasets
    # --------------------------------------------------------

    inventory_data = load_json(
        "ecdat-assets.json"
    )

    risk_data = load_json(
        "ecdat-risk-assessed-assets.json"
    )

    priority_data = load_json(
        "ecdat-migration-priority.json"
    )

    complexity_data = load_json(
        "ecdat-migration-complexity.json"
    )

    blast_data = load_json(
        "ecdat-blast-radius.json"
    )

    pqc_data = load_json(
        "ecdat-pqc-migration.json"
    )

    ranking_data = load_json(
        "ecdat-pqc-ranked.json"
    )

    actions_data = load_json(
        "ecdat-migration-actions.json"
    )

    report_data = load_json(
        "ecdat-migration-report.json"
    )

    # The contextual risk breakdown (business criticality / data
    # lifetime / exposure / migration time / evidence quality /
    # Mosca urgency, and which of those were actually known vs
    # UNKNOWN for this finding) -- computed by explain_cbom.py but,
    # until now, never read back out by this endpoint. current_risk
    # below intentionally stays the flattened legacy score+severity
    # shape everything else already depends on; this is an additive
    # field for "why was this risk score assigned?" explainability.
    explainable_risk_data = load_json(
        "ecdat-explainable-risk.json"
    )

    # --------------------------------------------------------
    # Normalize asset lists
    # --------------------------------------------------------

    inventory_assets = (
        inventory_data
        if isinstance(inventory_data, list)
        else inventory_data.get("assets", [])
    )

    risk_assets = get_asset_list(
        risk_data
    )

    priority_assets = get_asset_list(
        priority_data
    )

    complexity_assets = get_asset_list(
        complexity_data
    )

    blast_assets = get_asset_list(
        blast_data
    )

    pqc_assets = (
        pqc_data.get("assets", [])
        if isinstance(pqc_data, dict)
        else pqc_data
    )

    ranking_assets = (
        ranking_data.get("assets", [])
        if isinstance(ranking_data, dict)
        else []
    )

    action_assets = (
        actions_data.get("assets", [])
        if isinstance(actions_data, dict)
        else actions_data
    )

    report_assets = (
        report_data.get("assets", [])
        if isinstance(report_data, dict)
        else report_data
    )

    explainable_risk_assets = (
        explainable_risk_data.get("assets", [])
        if isinstance(explainable_risk_data, dict)
        else (explainable_risk_data or [])
    )

    # --------------------------------------------------------
    # Find records
    # --------------------------------------------------------

    def find_by_id(records):
        for record in records:
            identity = record.get("identity", {})
            if not isinstance(identity, dict):
                identity = {}
            finding_id = record.get("bom_ref") or record.get("asset_ref") or identity.get("bom_ref")
            if finding_id and str(finding_id) == asset_name:
                return record

        return None

    inventory = find_by_id(
        inventory_assets
    )

    risk = find_by_id(
        risk_assets
    )

    priority = find_by_id(
        priority_assets
    )

    complexity = find_by_id(
        complexity_assets
    )

    blast_radius = find_by_id(
        blast_assets
    )

    pqc = find_by_id(
        pqc_assets
    )

    ranking = find_by_id(
        ranking_assets
    )

    actions = find_by_id(
        action_assets
    )

    explainable_risk = find_by_id(
        explainable_risk_assets
    )

    report = find_by_id(
        report_assets
    )

    # --------------------------------------------------------
    # Asset must exist
    # --------------------------------------------------------

    if (
        inventory is None
        and report is None
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Asset not found: {asset_name}",
        )

    # --------------------------------------------------------
    # Return unified ECDAT record
    # --------------------------------------------------------

    return {
        "asset": (report or inventory or {}).get("asset") or (report or inventory or {}).get("name") or "Unknown",
        "bom_ref": asset_name,

        "inventory": inventory,

        "classification": (
            report.get("classification")
            if report
            else None
        ),

        "current_risk": (
            report.get("current_risk")
            if report
            else (
                risk.get("risk_assessment")
                if risk
                else None
            )
        ),

        "risk_assessment": risk,

        # "Why was this risk score assigned?" -- the contextual
        # weighting behind current_risk's flattened score/severity:
        # which factors were known vs UNKNOWN (data lifetime in
        # particular -- see services/business_context.py -- is never
        # fabricated), their raw/weighted contributions, and Mosca
        # urgency when a data lifetime is actually configured.
        "risk_explanation": (
            {
                "context": explainable_risk.get("risk_assessment", {}).get("context"),
                "score_breakdown": explainable_risk.get("risk_assessment", {}).get("score_breakdown"),
                "mosca_analysis": explainable_risk.get("risk_assessment", {}).get("mosca_analysis"),
                # Prose + per-factor contributions, reconciled with the
                # score (services/explanation_engine.py).
                "explanation": explainable_risk.get("explanation"),
            }
            if explainable_risk
            else None
        ),

        # Purpose-aware migration strategy: KEEP / DIRECT_PQC / HYBRID /
        # NEEDS_REVIEW, with components, confidence, decision factors
        # and explanation (services/migration_strategy.py).
        "migration_strategy": (
            report.get("migration_strategy")
            if report
            else None
        ),

        "migration_impact": (
            report.get("migration_impact")
            if report
            else None
        ),

        "priority": priority,

        "complexity": complexity,

        "blast_radius": blast_radius,

        "pqc_migration": (
            report.get("pqc_migration")
            if report
            else pqc
        ),

        # Reconciled with the migration strategy (idempotent), so even a
        # report generated before reconciliation can never present a
        # NEEDS_REVIEW finding's ranking candidate as a recommendation.
        "recommendation": (
            reconcile_recommendation(
                report.get("recommendation"),
                report.get("migration_strategy"),
            )
            if report
            else None
        ),

        "ranked_candidates": (
            report.get("ranked_candidates")
            if report
            else (
                ranking.get(
                    "ranked_candidates",
                    []
                )
                if ranking
                else []
            )
        ),

        "source_impact": (
            report.get("source_impact")
            if report
            else None
        ),

        "migration_actions": (
            report.get("migration_actions")
            if report
            else (
                actions.get(
                    "actions",
                    []
                )
                if actions
                else []
            )
        ),

        "action_count": (
            report.get("action_count")
            if report
            else (
                actions.get(
                    "action_count",
                    0
                )
                if actions
                else 0
            )
        ),

        "explanation": (
            report.get("explanation")
            if report
            else None
        ),
    }
@app.post("/api/analyze")
def start_analysis(request: AnalyzeRequest):
    return start_scan_request(request)


@app.get("/api/analyze/status")
def get_analysis_status():
    return analysis_status_payload()


# ------------------------------------------------------------
# Repository scanning (same service, scan-oriented names)
# ------------------------------------------------------------


@app.post("/api/scan")
def start_scan(request: AnalyzeRequest):
    return start_scan_request(request)


@app.get("/api/scan/status")
def get_scan_status():
    return analysis_status_payload()


@app.get("/api/scan/capabilities")
def get_scan_capabilities():
    """What ECDAT can scan today, and what is explicitly not implemented."""
    return scan_service.capabilities()


@app.get("/api/scan/history")
def get_scan_history():
    return {"scans": scan_service.history()}
@app.post("/api/ai/advisor")
def ai_advisor(request: AIAdvisorRequest):

    try:
        result = generate_advice(
            request.asset_name
        )

        return result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI advisor failed: {exc}"
        )


# ============================================================
# AI MIGRATION ADVISOR (frontend contract)
# ============================================================
#
# This is the endpoint frontend/src/api.js:getAIAdvice() actually
# calls (POST /api/ai/advice, body {"asset": "<name>"}). It was
# previously only defined in the now-deprecated backend/api/main.py.
# Consolidated here as part of the 2026-09-14 backend architecture
# fix — see docs/ARCHITECTURE.md and docs/CHANGELOG.md.

class AIAdviceRequest(BaseModel):
    asset: str


@app.post("/api/ai/advice")
def ai_advice(request: AIAdviceRequest):
    try:
        return generate_advice(request.asset)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"AI advisor failed: {str(exc)}"
        )


# ============================================================
# EVIDENCE EXPLORER
# ============================================================
#
# "Why did ECDAT classify, score and recommend this migration path?"
# Read-only: services/evidence_explorer.py re-arranges the existing
# pipeline outputs for one bom_ref and computes nothing itself.

@app.get("/api/evidence/{bom_ref}")
def get_finding_evidence(bom_ref: str):
    try:
        records = load_evidence_records(DATA_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found: {Path(exc.filename or '').name}",
        )

    evidence = build_finding_evidence(bom_ref, records)

    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail={
                "reason_code": "unknown-finding",
                "reason": "No finding with this bom_ref exists in the ECDAT dataset.",
                "bom_ref": bom_ref,
            },
        )

    return evidence


# ============================================================
# WHAT-IF MIGRATION SIMULATOR
# ============================================================
#
# Thin HTTP layer over services/migration_scenario.py: every check
# (registry membership, role/family fit, NEEDS_REVIEW / KEEP) and every
# calculation (the real contextual-risk and migration-priority engines)
# happens there. Findings are addressed by bom_ref only. Snapshots are
# deep copies built in memory per request; nothing is written back to
# data/*.json.

WHAT_IF_NOTICE = (
    "Simulation only: computed in memory from a copy of the finding. "
    "The real finding and the ECDAT dataset are unchanged."
)


class WhatIfSimulationRequest(BaseModel):
    # extra="forbid": an algorithm name (e.g. {"asset": "RSA"}) is not an
    # accepted way to address a finding.
    model_config = ConfigDict(extra="forbid")

    bom_ref: str = Field(min_length=1)
    pqc_option: str = Field(min_length=1)


class WhatIfPortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replacements: Dict[str, str] = Field(min_length=1, max_length=1000)


def load_what_if_snapshots():
    try:
        return load_finding_snapshots(DATA_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found: {Path(exc.filename or '').name}",
        )


def what_if_snapshot(snapshots, bom_ref):
    snapshot = snapshots.get(bom_ref)

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={
                "reason_code": "unknown-finding",
                "reason": "No finding with this bom_ref exists in the ECDAT dataset.",
                "bom_ref": bom_ref,
            },
        )

    return snapshot


@app.get("/api/what-if/findings/{bom_ref}")
def get_what_if_finding(bom_ref: str):
    """Current state, simulatability and valid PQC options for one finding."""

    snapshot = what_if_snapshot(load_what_if_snapshots(), bom_ref)
    options = simulation_options(snapshot, load_ranked_candidates(DATA_DIR))
    eligibility = options["eligibility"]
    strategy = snapshot.strategy

    return {
        "simulation_mode": "what-if",
        "bom_ref": snapshot.bom_ref,
        "name": snapshot.name,
        "quantum_status": (snapshot.asset.get("classification") or {}).get("quantum_status"),
        "current": {
            "risk": {
                "score": snapshot.recorded_risk_score,
                "severity": snapshot.recorded_risk_severity,
            },
            "priority": {
                "score": snapshot.recorded_priority_score,
                "level": snapshot.recorded_priority_level,
            },
        },
        "strategy": {
            key: strategy.get(key)
            for key in (
                "strategy",
                "label",
                "confidence",
                "purpose_class_label",
                "pqc_family",
                "pqc_component",
                "classical_component",
                "inherited_from",
                "rationale",
            )
        },
        "simulatable": eligibility["simulatable"],
        "reason_code": eligibility.get("reason_code"),
        "reason": eligibility.get("reason"),
        "review_options": eligibility.get("review_options", []),
        "target_family": eligibility.get("target_family"),
        "options": options["options"],
        "ranking_source_bom_ref": options["ranking_source_bom_ref"],
    }


@app.post("/api/what-if/simulate")
def simulate_what_if(request: WhatIfSimulationRequest):
    """
    Simulate migrating one finding to one PQC option, plus the effect of
    that single change on portfolio readiness. Options the scenario
    engine rejects are returned as 422 with its reason_code.
    """

    snapshots = load_what_if_snapshots()
    snapshot = what_if_snapshot(snapshots, request.bom_ref)

    outcome = simulate_pqc_option(snapshot, request.pqc_option)

    if not outcome["applied"]:
        raise HTTPException(status_code=422, detail=outcome)

    portfolio = simulate_portfolio(
        snapshots.values(),
        {request.bom_ref: request.pqc_option},
    )
    readiness = portfolio["readiness_percent"]

    return {
        "simulation_mode": "what-if",
        "persisted": False,
        "notice": WHAT_IF_NOTICE,
        "finding": outcome,
        "portfolio": {
            "finding_count": portfolio["finding_count"],
            "remaining_quantum_vulnerable": portfolio["remaining_quantum_vulnerable"],
            "readiness_percent": {
                **readiness,
                "delta": readiness["after"] - readiness["before"],
            },
        },
    }


@app.post("/api/what-if/portfolio")
def simulate_what_if_portfolio(request: WhatIfPortfolioRequest):
    """
    Simulate several {bom_ref: pqc_option} replacements at once.
    Replacements the engine rejects (including unknown bom_refs) are
    listed under `rejected` and leave that finding's recorded state in
    place, exactly as services/migration_scenario.simulate_portfolio
    defines.
    """

    portfolio = simulate_portfolio(
        load_what_if_snapshots().values(),
        request.replacements,
    )
    readiness = portfolio["readiness_percent"]
    readiness["delta"] = readiness["after"] - readiness["before"]

    return {
        "simulation_mode": "what-if",
        "persisted": False,
        "notice": WHAT_IF_NOTICE,
        **portfolio,
    }

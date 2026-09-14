from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import sys
import threading
from pathlib import Path
from pydantic import BaseModel
from services.ai_advisor import generate_advice



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


analysis_state = {
    "status": "idle",
    "repository": None,
    "branch": None,
    "message": "No analysis running.",
    "error": None
}
class AIAdvisorRequest(BaseModel):
    asset_name: str


def run_repository_analysis(repository: str, branch: str):
    global analysis_state

    analysis_state.update({
        "status": "running",
        "repository": repository,
        "branch": branch,
        "message": "CBOMKit scan and ECDAT analysis are running.",
        "error": None
    })

    try:
        backend_dir = Path(__file__).resolve().parent
        script = backend_dir / "analyze_repository.py"

        result = subprocess.run(
    [
        sys.executable,
        str(script),
        repository,
        branch
    ],
    cwd=str(backend_dir)
)

        if result.returncode != 0:
            analysis_state.update({
                 "status": "failed",
        "message": "Analysis failed. Check the backend terminal for details.",
        "error": f"analyze_repository.py exited with code {result.returncode}"
            })
            return

        analysis_state.update({
            "status": "completed",
            "message": "CBOMKit scan and ECDAT analysis completed successfully.",
            "error": None
        })

    except Exception as exc:
        analysis_state.update({
            "status": "failed",
            "message": "Analysis failed unexpectedly.",
            "error": str(exc)
        })

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

        if pqc.get("pqc_applicable") is True:
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

        name = (
            asset.get("asset")
            or asset.get("name")
            or asset.get("algorithm")
        )

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
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
        name = (
            record.get("asset")
            or record.get("name")
        )

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
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

    for asset in assets:

        name = (
            asset.get("name")
            or asset.get("asset")
        )

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
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

    for asset in assets:

        name = asset.get("asset")

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
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

        name = asset.get(
            "asset"
        )

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):

            source_impact = asset.get(
                "source_impact",
                {},
            )

            return {
                "asset": name,

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

    for asset in assets:

        name = asset.get("asset")

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
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
                "recommendation": asset.get(
                    "recommendation",
                    {}
                ).get("decision"),
                "candidate": asset.get(
                    "recommendation",
                    {}
                ).get("candidate"),
                "source_impact": asset.get(
                    "source_impact",
                    {}
                ).get("impact_level"),
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

        name = asset.get(
            "asset"
        )

        if (
            name
            and str(name).lower()
            == asset_name.lower()
        ):
            return asset

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

    # --------------------------------------------------------
    # Find records
    # --------------------------------------------------------

    def find_by_name(records):
        for record in records:

            name = (
                record.get("asset")
                or record.get("name")
                or record.get("algorithm")
            )

            if (
                name
                and str(name).lower()
                == asset_name.lower()
            ):
                return record

        return None

    inventory = find_by_name(
        inventory_assets
    )

    risk = find_by_name(
        risk_assets
    )

    priority = find_by_name(
        priority_assets
    )

    complexity = find_by_name(
        complexity_assets
    )

    blast_radius = find_by_name(
        blast_assets
    )

    pqc = find_by_name(
        pqc_assets
    )

    ranking = find_by_name(
        ranking_assets
    )

    actions = find_by_name(
        action_assets
    )

    report = find_by_name(
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
        "asset": asset_name,

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

        "recommendation": (
            report.get("recommendation")
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
    if analysis_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="An analysis is already running."
        )

    thread = threading.Thread(
        target=run_repository_analysis,
        args=(request.repository, request.branch),
        daemon=True
    )

    thread.start()

    return {
        "status": "started",
        "repository": request.repository,
        "branch": request.branch,
        "message": "Analysis started successfully."
    }


@app.get("/api/analyze/status")
def get_analysis_status():
    return analysis_state
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
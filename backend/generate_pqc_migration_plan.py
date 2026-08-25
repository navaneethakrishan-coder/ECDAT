import json
from pathlib import Path
from collections import Counter


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

RISK_FILE = DATA_DIR / "ecdat-explainable-risk.json"
BLAST_FILE = DATA_DIR / "ecdat-blast-radius.json"
COMPLEXITY_FILE = DATA_DIR / "ecdat-migration-complexity.json"
PRIORITY_FILE = DATA_DIR / "ecdat-migration-priority.json"

# IMPORTANT:
# Stage 8.8 now consumes the ranked PQC output.
PQC_RANKED_FILE = DATA_DIR / "ecdat-pqc-ranked.json"

OUTPUT_FILE = DATA_DIR / "ecdat-pqc-migration-plan.json"


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def asset_key(record):
    return (
        record.get("name")
        or record.get("asset")
        or record.get("id")
    )


def build_map(records):
    result = {}

    for record in records:
        key = asset_key(record)

        if key:
            result[key] = record

    return result


# ============================================================
# RISK
# ============================================================

def get_risk_score(record):
    risk = record.get("risk_assessment", {})

    try:
        return float(
            risk.get("final_score", 0)
        )
    except (TypeError, ValueError):
        return 0.0


def get_risk_severity(record):
    return (
        record
        .get("risk_assessment", {})
        .get("severity", "UNKNOWN")
    )


# ============================================================
# BLAST RADIUS
# ============================================================

def get_blast_score(record):
    try:
        return float(
            record.get("blast_radius_score", 0)
        )
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# MIGRATION COMPLEXITY
# ============================================================

def get_complexity_score(record):
    """
    Supports the actual ECDAT migration-complexity structure.
    """

    for key in (
        "complexity_score",
        "score",
        "migration_complexity_score",
    ):
        value = record.get(key)

        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass

    nested = record.get(
        "migration_complexity",
        {}
    )

    if isinstance(nested, dict):
        for key in (
            "score",
            "complexity_score",
        ):
            value = nested.get(key)

            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return 0.0


def get_complexity_level(record):
    nested = record.get(
        "migration_complexity",
        {}
    )

    if isinstance(nested, dict):
        return nested.get(
            "level",
            record.get("level", "UNKNOWN"),
        )

    return record.get(
        "level",
        "UNKNOWN",
    )


# ============================================================
# MIGRATION PRIORITY
# ============================================================

def get_priority_score(record):
    priority = record.get(
        "migration_priority",
        {}
    )

    if isinstance(priority, dict):
        try:
            return float(
                priority.get(
                    "priority_score",
                    0,
                )
            )
        except (TypeError, ValueError):
            return 0.0

    try:
        return float(priority)
    except (TypeError, ValueError):
        return 0.0


def get_priority_level(record):
    priority = record.get(
        "migration_priority",
        {}
    )

    if isinstance(priority, dict):
        return priority.get(
            "priority",
            "UNKNOWN",
        )

    return "UNKNOWN"


# ============================================================
# PQC ANALYSIS
# ============================================================

def get_pqc_analysis(record):
    """
    Read PQC migration information from the ranked
    PQC analysis output.

    Primary location:
        record["migration"]

    Backward-compatible locations:
        record["pqc_analysis"]
        record["pqc_migration"]
    """

    migration = record.get("migration", {})

    if isinstance(migration, dict):
        return migration

    pqc_analysis = record.get("pqc_analysis", {})

    if isinstance(pqc_analysis, dict):
        return pqc_analysis

    pqc_migration = record.get("pqc_migration", {})

    if isinstance(pqc_migration, dict):
        return pqc_migration

    return {}


# ============================================================
# RANKED CANDIDATES
# ============================================================

def get_ranked_candidates(record):
    """
    Read ranked candidates generated by generate_pqc_ranking.py.

    Expected structure:

    ranked_candidates: [
        {
            "candidate": "ML-KEM-768",
            "family": "KEM",
            "score": 84.36,
            "rank": 1,
            ...
        }
    ]
    """

    candidates = record.get(
        "ranked_candidates",
        []
    )

    if not isinstance(candidates, list):
        return []

    return candidates


def build_candidate_entries(record):
    """
    Preserve the complete ranked candidate information.
    """

    candidates = get_ranked_candidates(record)

    result = []

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        rank = candidate.get(
            "rank",
            index,
        )

        try:
            rank = int(rank)
        except (TypeError, ValueError):
            rank = index

        score = candidate.get("score")

        if score is not None:
            try:
                score = round(float(score), 2)
            except (TypeError, ValueError):
                score = None

        result.append(
            {
                "rank": rank,

                "candidate": candidate.get(
                    "candidate"
                ),

                "family": candidate.get(
                    "family"
                ),

                "score": score,

                "compatibility": candidate.get(
                    "compatibility"
                ),

                "score_breakdown": candidate.get(
                    "score_breakdown",
                    {}
                ),

                "reason": candidate.get(
                    "reason"
                ),

                "tradeoffs": candidate.get(
                    "tradeoffs",
                    []
                ),

                "explanation": candidate.get(
                    "explanation",
                    {}
                ),
            }
        )

    result.sort(
        key=lambda item: (
            item["rank"]
            if item["rank"] is not None
            else 999999
        )
    )

    return result


# ============================================================
# RECOMMENDATION
# ============================================================

def make_recommendation(
    pqc_analysis,
    ranked_candidates,
):
    migration_type = pqc_analysis.get(
        "migration_type",
        "unknown",
    )

    confidence = pqc_analysis.get(
        "confidence",
        "LOW",
    )

    # --------------------------------------------------------
    # NO DIRECT PQC REPLACEMENT
    # --------------------------------------------------------

    if migration_type == "no-direct-pqc-replacement":
        return {
            "decision": "NO_DIRECT_REPLACEMENT",
            "candidate": None,
            "candidate_rank": None,
            "candidate_score": None,
            "confidence": confidence,
            "reason": (
                "No direct PQC replacement is available "
                "for the current cryptographic role."
            ),
        }

    # --------------------------------------------------------
    # ARCHITECTURAL MIGRATION
    # --------------------------------------------------------

    if migration_type == "architectural-migration":

        selected = (
            ranked_candidates[0]
            if ranked_candidates
            else None
        )

        return {
            "decision": "ARCHITECTURAL_MIGRATION",

            "candidate": (
                selected.get("candidate")
                if selected
                else None
            ),

            "candidate_rank": (
                selected.get("rank")
                if selected
                else None
            ),

            "candidate_score": (
                selected.get("score")
                if selected
                else None
            ),

            "confidence": "MEDIUM",

            "reason": (
                "The asset requires usage-specific or "
                "architectural migration planning. "
                "The highest-ranked PQC candidate is "
                "provided as a migration direction rather "
                "than a direct replacement."
            ),
        }

    # --------------------------------------------------------
    # NO CANDIDATES
    # --------------------------------------------------------

    if not ranked_candidates:
        return {
            "decision": "NO_DIRECT_REPLACEMENT",
            "candidate": None,
            "candidate_rank": None,
            "candidate_score": None,
            "confidence": "LOW",
            "reason": (
                "No PQC candidate was available."
            ),
        }

    # --------------------------------------------------------
    # PQC CANDIDATE
    # --------------------------------------------------------

    selected = ranked_candidates[0]

    score = selected.get(
        "score"
    )

    if score is not None:
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = None

    if score is not None and score >= 80:
        decision = "RECOMMENDED"
    else:
        decision = "CONDITIONALLY_RECOMMENDED"

    return {
        "decision": decision,

        "candidate": selected.get(
            "candidate"
        ),

        "candidate_rank": selected.get(
            "rank"
        ),

        "candidate_score": (
            round(score, 2)
            if score is not None
            else None
        ),

        "confidence": confidence,

        "reason": (
            "The selected candidate is the highest-ranked "
            "compatible PQC candidate currently available "
            "according to the ECDAT candidate-ranking model."
        ),
    }


# ============================================================
# BUILD ASSET PLAN
# ============================================================

def build_asset_plan(
    pqc_record,
    risk_record,
    blast_record,
    complexity_record,
    priority_record,
):

    name = pqc_record.get(
        "name",
        pqc_record.get(
            "asset",
            "Unknown",
        ),
    )

    pqc = get_pqc_analysis(
        pqc_record
    )

    candidates = build_candidate_entries(
        pqc_record
    )

    recommendation = make_recommendation(
        pqc,
        candidates,
    )

    classification = pqc_record.get(
        "classification",
        {}
    )

    if not isinstance(
        classification,
        dict,
    ):
        classification = {}

    risk_assessment = risk_record.get(
        "risk_assessment",
        {}
    )

    context = risk_assessment.get(
        "context",
        {}
    )

    evidence = risk_record.get(
        "evidence",
        {}
    )

    return {

        "asset": name,

        # ----------------------------------------------------
        # IDENTITY
        # ----------------------------------------------------

        "identity": {
            "id": pqc_record.get(
                "id"
            ),

            "asset_type": pqc_record.get(
                "asset_type"
            ),

            "primitive": pqc_record.get(
                "primitive"
            ),
        },

        # ----------------------------------------------------
        # CLASSIFICATION
        # ----------------------------------------------------

        "classification": {
            "category": classification.get(
                "category"
            ),

            "purpose": classification.get(
                "purpose",
                [],
            ),

            "quantum_status": classification.get(
                "quantum_status"
            ),

            "risk_reason": classification.get(
                "risk_reason"
            ),
        },

        # ----------------------------------------------------
        # CURRENT RISK
        # ----------------------------------------------------

        "current_risk": {
            "score": get_risk_score(
                risk_record
            ),

            "severity": get_risk_severity(
                risk_record
            ),
        },

        # ----------------------------------------------------
        # MIGRATION IMPACT
        # ----------------------------------------------------

        "migration_impact": {
            "blast_radius_score": get_blast_score(
                blast_record
            ),

            "migration_complexity_score":
                get_complexity_score(
                    complexity_record
                ),

            "migration_complexity_level":
                get_complexity_level(
                    complexity_record
                ),

            "migration_priority_score":
                get_priority_score(
                    priority_record
                ),

            "migration_priority":
                get_priority_level(
                    priority_record
                ),
        },

        # ----------------------------------------------------
        # CONTEXT
        # ----------------------------------------------------

        "context": {
            "business_criticality":
                context.get(
                    "business_criticality"
                ),

            "data_lifetime_years":
                context.get(
                    "data_lifetime_years"
                ),

            "migration_time_years":
                context.get(
                    "migration_time_years"
                ),

            "exposure":
                context.get(
                    "exposure"
                ),

            "quantum_threat_horizon_years":
                context.get(
                    "quantum_threat_horizon_years"
                ),
        },

        # ----------------------------------------------------
        # PQC ANALYSIS
        # ----------------------------------------------------

        "pqc_analysis": {

            "migration_type":
                pqc.get(
                    "migration_type"
                ),

            "pqc_applicable":
                pqc.get(
                    "pqc_applicable"
                ),

            "confidence":
                pqc.get(
                    "confidence"
                ),

            "reason":
                pqc.get(
                    "reason"
                ),
        },

        # ----------------------------------------------------
        # RANKED PQC CANDIDATES
        # ----------------------------------------------------

        "ranked_candidates":
            candidates,

        # ----------------------------------------------------
        # FINAL RECOMMENDATION
        # ----------------------------------------------------

        "recommendation":
            recommendation,

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        "evidence": {

            "evidence_count":
                evidence.get(
                    "evidence_count",
                    0,
                ),

            "locations":
                evidence.get(
                    "locations",
                    [],
                ),
        },

        # ----------------------------------------------------
        # MIGRATION ACTIONS
        # ----------------------------------------------------

        "migration_actions": [
            "Validate the cryptographic usage.",
            "Validate PQC implementation support.",
            "Evaluate protocol compatibility.",
            "Evaluate interoperability.",
            "Perform performance testing.",
            "Perform security testing.",
            "Validate migration in a controlled environment.",
        ],
    }


# ============================================================
# GENERATE PLAN
# ============================================================

def generate_plan():

    print(
        "Loading ECDAT migration data..."
    )

    risk_data = load_json(
        RISK_FILE
    )

    blast_data = load_json(
        BLAST_FILE
    )

    complexity_data = load_json(
        COMPLEXITY_FILE
    )

    priority_data = load_json(
        PRIORITY_FILE
    )

    # IMPORTANT:
    # Read the ranked PQC output.
    pqc_data = load_json(
        PQC_RANKED_FILE
    )

    risk_map = build_map(
        risk_data.get(
            "assets",
            [],
        )
    )

    blast_map = build_map(
        blast_data.get(
            "assets",
            [],
        )
    )

    complexity_map = build_map(
        complexity_data.get(
            "assets",
            [],
        )
    )

    priority_map = build_map(
        priority_data.get(
            "assets",
            [],
        )
    )

    pqc_assets = pqc_data.get(
        "assets",
        [],
    )

    print(
        f"Risk records: {len(risk_map)}"
    )

    print(
        f"Blast-radius records: {len(blast_map)}"
    )

    print(
        f"Complexity records: {len(complexity_map)}"
    )

    print(
        f"Priority records: {len(priority_map)}"
    )

    print(
        f"PQC ranked records: {len(pqc_assets)}"
    )

    assets = []

    missing_risk = 0
    missing_blast = 0
    missing_complexity = 0
    missing_priority = 0

    for pqc_record in pqc_assets:

        name = pqc_record.get(
            "name",
            pqc_record.get(
                "asset"
            ),
        )

        risk_record = risk_map.get(
            name
        )

        blast_record = blast_map.get(
            name
        )

        complexity_record = complexity_map.get(
            name
        )

        priority_record = priority_map.get(
            name
        )

        if risk_record is None:
            missing_risk += 1

        if blast_record is None:
            missing_blast += 1

        if complexity_record is None:
            missing_complexity += 1

        if priority_record is None:
            missing_priority += 1

        assets.append(
            build_asset_plan(
                pqc_record,
                risk_record or {},
                blast_record or {},
                complexity_record or {},
                priority_record or {},
            )
        )

    # ========================================================
    # SUMMARY COUNTS
    # ========================================================

    decision_counts = Counter(
        asset["recommendation"][
            "decision"
        ]
        for asset in assets
    )

    migration_counts = Counter(
        asset["pqc_analysis"][
            "migration_type"
        ]
        for asset in assets
    )

    pqc_applicable = sum(
        1
        for asset in assets
        if asset["pqc_analysis"][
            "pqc_applicable"
        ] is True
    )

    assets_with_candidates = sum(
        1
        for asset in assets
        if len(
            asset["ranked_candidates"]
        ) > 0
    )

    # ========================================================
    # HIGH PRIORITY
    # ========================================================

    high_priority = [
        asset
        for asset in assets
        if asset["migration_impact"][
            "migration_priority_score"
        ] >= 60
    ]

    high_priority.sort(
        key=lambda asset:
            asset["migration_impact"][
                "migration_priority_score"
            ],
        reverse=True,
    )

    # ========================================================
    # TOP RANKED CANDIDATES
    # ========================================================

    top_candidate_assets = []

    for asset in assets:

        candidates = asset[
            "ranked_candidates"
        ]

        if not candidates:
            continue

        top = candidates[0]

        top_candidate_assets.append(
            {
                "asset":
                    asset["asset"],

                "candidate":
                    top.get("candidate"),

                "family":
                    top.get("family"),

                "candidate_score":
                    top.get("score"),

                "candidate_rank":
                    top.get("rank"),

                "priority_score":
                    asset["migration_impact"][
                        "migration_priority_score"
                    ],

                "decision":
                    asset["recommendation"][
                        "decision"
                    ],
            }
        )

    top_candidate_assets.sort(
        key=lambda item:
            item["priority_score"],
        reverse=True,
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = {

        "project": "ECDAT",

        "report": {
            "name":
                "PQC Migration Plan",

            "stage":
                "8.8",

            "description": (
                "Consolidated post-quantum migration "
                "decision-support report generated "
                "from ECDAT risk, dependency, "
                "migration complexity, migration "
                "priority and ranked PQC candidate analysis."
            ),

            "ranking_source":
                "ecdat-pqc-ranked.json",
        },

        "summary": {

            "total_assets":
                len(assets),

            "pqc_applicable_assets":
                pqc_applicable,

            "assets_with_candidates":
                assets_with_candidates,

            "migration_types":
                dict(migration_counts),

            "recommendation_distribution":
                dict(decision_counts),

            "high_priority_assets":
                len(high_priority),

            "ranked_candidate_assets":
                len(top_candidate_assets),
        },

        # ====================================================
        # MAPPING VALIDATION
        # ====================================================

        "mapping_validation": {

            "risk_mapped":
                len(assets) - missing_risk,

            "blast_radius_mapped":
                len(assets) - missing_blast,

            "complexity_mapped":
                len(assets) - missing_complexity,

            "priority_mapped":
                len(assets) - missing_priority,

            "missing_risk":
                missing_risk,

            "missing_blast_radius":
                missing_blast,

            "missing_complexity":
                missing_complexity,

            "missing_priority":
                missing_priority,
        },

        # ====================================================
        # TOP PRIORITY ASSETS
        # ====================================================

        "top_priority_assets": [

            {
                "asset":
                    asset["asset"],

                "priority_score":
                    asset["migration_impact"][
                        "migration_priority_score"
                    ],

                "priority":
                    asset["migration_impact"][
                        "migration_priority"
                    ],

                "risk_score":
                    asset["current_risk"][
                        "score"
                    ],

                "blast_radius":
                    asset["migration_impact"][
                        "blast_radius_score"
                    ],

                "complexity":
                    asset["migration_impact"][
                        "migration_complexity_score"
                    ],

                "decision":
                    asset["recommendation"][
                        "decision"
                    ],

                "candidate":
                    asset["recommendation"][
                        "candidate"
                    ],

                "candidate_score":
                    asset["recommendation"].get(
                        "candidate_score"
                    ),

                "candidate_rank":
                    asset["recommendation"].get(
                        "candidate_rank"
                    ),
            }

            for asset in high_priority[:10]
        ],

        # ====================================================
        # TOP PQC CANDIDATES
        # ====================================================

        "top_pqc_candidates":
            top_candidate_assets[:10],

        # ====================================================
        # ALL ASSETS
        # ====================================================

        "assets":
            assets,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
        )

    return output


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(data):

    summary = data["summary"]

    validation = data[
        "mapping_validation"
    ]

    print()

    print(
        "============================================="
    )

    print(
        "ECDAT PQC MIGRATION PLAN"
    )

    print(
        "============================================="
    )

    print(
        f"Total assets: "
        f"{summary['total_assets']}"
    )

    print(
        f"PQC-applicable assets: "
        f"{summary['pqc_applicable_assets']}"
    )

    print(
        f"Assets with candidates: "
        f"{summary['assets_with_candidates']}"
    )

    print()

    print(
        "Migration types:"
    )

    for key, value in summary[
        "migration_types"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print()

    print(
        "Recommendations:"
    )

    for key, value in summary[
        "recommendation_distribution"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print()

    print(
        "Mapping validation:"
    )

    print(
        f"  Risk mapped: "
        f"{validation['risk_mapped']}/"
        f"{summary['total_assets']}"
    )

    print(
        f"  Blast-radius mapped: "
        f"{validation['blast_radius_mapped']}/"
        f"{summary['total_assets']}"
    )

    print(
        f"  Complexity mapped: "
        f"{validation['complexity_mapped']}/"
        f"{summary['total_assets']}"
    )

    print(
        f"  Priority mapped: "
        f"{validation['priority_mapped']}/"
        f"{summary['total_assets']}"
    )

    print()

    print(
        "Top migration priorities:"
    )

    for index, asset in enumerate(
        data["top_priority_assets"],
        start=1,
    ):

        print()

        print(
            f"{index}. "
            f"{asset['asset']} — "
            f"{asset['priority_score']}"
        )

        print(
            f"   Risk: "
            f"{asset['risk_score']}"
        )

        print(
            f"   Blast radius: "
            f"{asset['blast_radius']}"
        )

        print(
            f"   Complexity: "
            f"{asset['complexity']}"
        )

        print(
            f"   Decision: "
            f"{asset['decision']}"
        )

        print(
            f"   Candidate: "
            f"{asset['candidate']}"
        )

        print(
            f"   Candidate score: "
            f"{asset['candidate_score']}"
        )

        print(
            f"   Candidate rank: "
            f"{asset['candidate_rank']}"
        )

    print()

    print(
        "Top ranked PQC candidates:"
    )

    for index, item in enumerate(
        data["top_pqc_candidates"],
        start=1,
    ):

        print()

        print(
            f"{index}. "
            f"{item['asset']}"
        )

        print(
            f"   Candidate: "
            f"{item['candidate']}"
        )

        print(
            f"   Family: "
            f"{item['family']}"
        )

        print(
            f"   Score: "
            f"{item['candidate_score']}"
        )

        print(
            f"   Rank: "
            f"{item['candidate_rank']}"
        )

        print(
            f"   Decision: "
            f"{item['decision']}"
        )

    print()

    print(
        f"Output: {OUTPUT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    data = generate_plan()

    print_summary(data)
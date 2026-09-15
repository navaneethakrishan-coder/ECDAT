import json
from pathlib import Path
from collections import Counter

from services.pqc_ranker import rank_candidates


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

PQC_FILE = DATA_DIR / "ecdat-pqc-migration.json"
RISK_FILE = DATA_DIR / "ecdat-explainable-risk.json"
BLAST_FILE = DATA_DIR / "ecdat-blast-radius.json"
COMPLEXITY_FILE = DATA_DIR / "ecdat-migration-complexity.json"
PRIORITY_FILE = DATA_DIR / "ecdat-migration-priority.json"

OUTPUT_FILE = DATA_DIR / "ecdat-pqc-ranked.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_asset_name(record):
    return (
        record.get("name")
        or record.get("asset")
        or record.get("id")
    )


def get_finding_id(record):
    identity = record.get("identity", {})
    if not isinstance(identity, dict):
        identity = {}
    return record.get("bom_ref") or record.get("asset_ref") or identity.get("bom_ref")


def build_map(records):
    result = {}

    for record in records:
        name = get_finding_id(record)

        if name:
            result[name] = record

    return result


# ============================================================
# EXTRACT RISK
# ============================================================

def get_quantum_risk(record):
    risk = record.get(
        "risk_assessment",
        {},
    )

    try:
        return float(
            risk.get(
                "final_score",
                0,
            )
        )
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# EXTRACT BLAST RADIUS
# ============================================================

def get_blast_radius(record):
    try:
        return float(
            record.get(
                "blast_radius_score",
                0,
            )
        )
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# EXTRACT COMPLEXITY
# ============================================================

def get_complexity(record):
    # Direct form
    for key in (
        "complexity_score",
        "migration_complexity_score",
        "score",
    ):
        value = record.get(key)

        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass

    # Nested form
    nested = record.get(
        "migration_complexity",
        {},
    )

    if isinstance(nested, dict):
        for key in (
            "complexity_score",
            "score",
        ):
            value = nested.get(key)

            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return 0.0


# ============================================================
# EXTRACT PRIORITY
# ============================================================

def get_priority(record):
    priority = record.get(
        "migration_priority",
        {},
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


# ============================================================
# EXTRACT PQC DATA
# ============================================================

def get_pqc_analysis(record):
    pqc = record.get(
        "pqc_migration",
        {},
    )

    if not isinstance(pqc, dict):
        return {}

    return pqc


def get_candidates(record):
    pqc = get_pqc_analysis(record)

    candidates = pqc.get(
        "candidates",
        [],
    )

    if not isinstance(candidates, list):
        return []

    return candidates


# ============================================================
# BUILD RANKING INPUT
# ============================================================

def build_ranker_asset(
    pqc_record,
    risk_record,
    blast_record,
    complexity_record,
    priority_record,
):
    classification = pqc_record.get(
        "classification",
        {},
    )

    if not isinstance(classification, dict):
        classification = {}

    purposes = classification.get(
        "purpose",
        [],
    )

    if isinstance(purposes, str):
        purposes = [purposes]

    return {
        "name": pqc_record.get(
            "name",
            pqc_record.get(
                "asset"
            ),
        ),

        "purpose": purposes,

        "category": classification.get(
            "category",
        ),

        "quantum_status": classification.get(
            "quantum_status",
        ),

        "quantum_risk": get_quantum_risk(
            risk_record
        ),

        "blast_radius": get_blast_radius(
            blast_record
        ),

        "migration_complexity": get_complexity(
            complexity_record
        ),

        "migration_priority": get_priority(
            priority_record
        ),
    }


# ============================================================
# PROCESS ASSET
# ============================================================

def process_asset(
    pqc_record,
    risk_map,
    blast_map,
    complexity_map,
    priority_map,
):
    name = get_asset_name(
        pqc_record
    )
    bom_ref = get_finding_id(pqc_record)

    risk_record = risk_map.get(
        bom_ref,
        {},
    )

    blast_record = blast_map.get(
        bom_ref,
        {},
    )

    complexity_record = complexity_map.get(
        bom_ref,
        {},
    )

    priority_record = priority_map.get(
        bom_ref,
        {},
    )

    pqc_analysis = get_pqc_analysis(
        pqc_record
    )

    candidates = get_candidates(
        pqc_record
    )

    ranker_asset = build_ranker_asset(
        pqc_record,
        risk_record,
        blast_record,
        complexity_record,
        priority_record,
    )

    ranked = []

    if candidates:
        ranked = rank_candidates(
            ranker_asset,
            candidates,
        )

    return {
        "asset": name,
        "bom_ref": bom_ref,

        "identity": {
            "id": pqc_record.get(
                "id"
            ),
            "bom_ref": bom_ref,
            "asset_type": pqc_record.get(
                "asset_type"
            ),
            "primitive": pqc_record.get(
                "primitive"
            ),
        },

        "classification": {
            "category": pqc_analysis.get(
                "category",
                ranker_asset.get(
                    "category"
                ),
            ),
            "purpose": ranker_asset.get(
                "purpose",
                [],
            ),
            "quantum_status":
                pqc_analysis.get(
                    "quantum_status",
                    ranker_asset.get(
                        "quantum_status"
                    ),
                ),
        },

        "migration": {
            "migration_type":
                pqc_analysis.get(
                    "migration_type"
                ),

            "pqc_applicable":
                pqc_analysis.get(
                    "pqc_applicable"
                ),

            "confidence":
                pqc_analysis.get(
                    "confidence"
                ),

            "reason":
                pqc_analysis.get(
                    "reason"
                ),
        },

        "current_context": {
            "quantum_risk":
                ranker_asset[
                    "quantum_risk"
                ],

            "blast_radius":
                ranker_asset[
                    "blast_radius"
                ],

            "migration_complexity":
                ranker_asset[
                    "migration_complexity"
                ],

            "migration_priority":
                ranker_asset[
                    "migration_priority"
                ],
        },

        "candidate_count":
            len(candidates),

        "ranked_candidates":
            ranked,

        "original_candidates":
            candidates,
    }


# ============================================================
# GENERATE
# ============================================================

def generate():

    print(
        "Loading ECDAT PQC ranking data..."
    )

    pqc_data = load_json(
        PQC_FILE
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

    pqc_assets = pqc_data.get(
        "assets",
        [],
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

    print(
        f"PQC records: {len(pqc_assets)}"
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

    # --------------------------------------------------------
    # Mapping validation
    # --------------------------------------------------------

    risk_mapped = 0
    blast_mapped = 0
    complexity_mapped = 0
    priority_mapped = 0

    for record in pqc_assets:

        finding_id = get_finding_id(record)

        if finding_id in risk_map:
            risk_mapped += 1

        if finding_id in blast_map:
            blast_mapped += 1

        if finding_id in complexity_map:
            complexity_mapped += 1

        if finding_id in priority_map:
            priority_mapped += 1

    print()
    print(
        "Mapping validation:"
    )

    print(
        f"  Risk mapped: "
        f"{risk_mapped}/{len(pqc_assets)}"
    )

    print(
        f"  Blast-radius mapped: "
        f"{blast_mapped}/{len(pqc_assets)}"
    )

    print(
        f"  Complexity mapped: "
        f"{complexity_mapped}/{len(pqc_assets)}"
    )

    print(
        f"  Priority mapped: "
        f"{priority_mapped}/{len(pqc_assets)}"
    )

    # --------------------------------------------------------
    # Process all assets
    # --------------------------------------------------------

    ranked_assets = []

    for record in pqc_assets:

        ranked_assets.append(
            process_asset(
                record,
                risk_map,
                blast_map,
                complexity_map,
                priority_map,
            )
        )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    pqc_applicable = sum(
        1
        for asset in ranked_assets
        if asset["migration"][
            "pqc_applicable"
        ] is True
    )

    assets_with_candidates = sum(
        1
        for asset in ranked_assets
        if asset["candidate_count"] > 0
    )

    migration_types = Counter(
        str(
            asset["migration"][
                "migration_type"
            ]
        )
        for asset in ranked_assets
    )

    # --------------------------------------------------------
    # Top candidates
    # --------------------------------------------------------

    top_candidates = []

    for asset in ranked_assets:

        ranked = asset[
            "ranked_candidates"
        ]

        if not ranked:
            continue

        top = ranked[0]

        top_candidates.append(
            {
                "asset":
                    asset["asset"],

                "candidate":
                    top.get(
                        "candidate"
                    ),

                "family":
                    top.get(
                        "family"
                    ),

                "score":
                    top.get(
                        "score"
                    ),

                "rank":
                    top.get(
                        "rank"
                    ),
            }
        )

    top_candidates.sort(
        key=lambda item:
            item["score"],
        reverse=True,
    )

    output = {
        "project": "ECDAT",

        "report": {
            "name":
                "PQC Candidate Ranking",

            "stage":
                "8.7",

            "description": (
                "Batch ranking of PQC migration "
                "candidates using the deterministic "
                "ECDAT PQC ranking engine."
            ),
        },

        "summary": {
            "total_assets":
                len(ranked_assets),

            "pqc_applicable_assets":
                pqc_applicable,

            "assets_with_candidates":
                assets_with_candidates,

            "migration_types":
                dict(migration_types),
        },

        "mapping_validation": {
            "risk_mapped":
                risk_mapped,

            "blast_radius_mapped":
                blast_mapped,

            "complexity_mapped":
                complexity_mapped,

            "priority_mapped":
                priority_mapped,
        },

        "top_candidates":
            top_candidates[:20],

        "assets":
            ranked_assets,
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

    summary = data[
        "summary"
    ]

    print()
    print(
        "============================================="
    )
    print(
        "ECDAT PQC CANDIDATE RANKING"
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

    validation = data[
        "mapping_validation"
    ]

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
        "Top ranked PQC candidates:"
    )

    for index, item in enumerate(
        data["top_candidates"][:10],
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
            f"{item['score']}"
        )

        print(
            f"   Rank: "
            f"{item['rank']}"
        )

    print()

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":

    data = generate()

    print_summary(data)

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

RISK_FILE = DATA_DIR / "ecdat-explainable-risk.json"
BLAST_FILE = DATA_DIR / "ecdat-blast-radius.json"
COMPLEXITY_FILE = DATA_DIR / "ecdat-migration-complexity.json"
PRIORITY_FILE = DATA_DIR / "ecdat-migration-priority.json"
PQC_FILE = DATA_DIR / "ecdat-pqc-migration-plan.json"
ACTIONS_FILE = DATA_DIR / "ecdat-migration-actions.json"

OUTPUT_FILE = DATA_DIR / "ecdat-migration-report.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def assets_from(data):
    if not isinstance(data, dict):
        return []

    assets = data.get("assets", [])

    if not isinstance(assets, list):
        return []

    return assets


def index_by_asset(data):
    """
    Normalize the different asset naming conventions used
    by previous ECDAT stages.

    Some datasets use:
        "asset"

    while the explainable-risk dataset uses:
        "name"
    """

    result = {}

    for item in assets_from(data):

        if not isinstance(item, dict):
            continue

        asset_name = (
            item.get("asset")
            or item.get("name")
        )

        if asset_name is None:
            continue

        result[str(asset_name)] = item

    return result


def get_nested(data, *keys, default=None):
    current = data

    for key in keys:

        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def build_report(
    risk_data,
    blast_data,
    complexity_data,
    priority_data,
    pqc_data,
    actions_data,
):

    risk_map = index_by_asset(risk_data)
    blast_map = index_by_asset(blast_data)
    complexity_map = index_by_asset(complexity_data)
    priority_map = index_by_asset(priority_data)
    pqc_map = index_by_asset(pqc_data)
    actions_map = index_by_asset(actions_data)

    asset_names = sorted(
        name
        for name in (
            set(risk_map)
            | set(blast_map)
            | set(complexity_map)
            | set(priority_map)
            | set(pqc_map)
            | set(actions_map)
        )
        if name is not None
    )

    reports = []

    for asset_name in asset_names:

        risk = risk_map.get(
            asset_name,
            {},
        )

        blast = blast_map.get(
            asset_name,
            {},
        )

        complexity = complexity_map.get(
            asset_name,
            {},
        )

        priority = priority_map.get(
            asset_name,
            {},
        )

        pqc = pqc_map.get(
            asset_name,
            {},
        )

        actions = actions_map.get(
            asset_name,
            {},
        )

        # -------------------------------------------------
        # CLASSIFICATION
        # -------------------------------------------------

        classification = risk.get(
            "classification",
            {},
        )

        if not classification:
            classification = pqc.get(
                "classification",
                {},
            )

        if not isinstance(
            classification,
            dict,
        ):
            classification = {}

        # -------------------------------------------------
        # RISK
        # -------------------------------------------------

        risk_assessment = risk.get(
            "risk_assessment",
            {},
        )

        if not isinstance(
            risk_assessment,
            dict,
        ):
            risk_assessment = {}

        current_risk_score = risk_assessment.get(
            "final_score"
        )

        if current_risk_score is None:

            current_risk_score = get_nested(
                risk,
                "current_risk",
                "score",
            )

        current_risk_severity = risk_assessment.get(
            "severity"
        )

        if current_risk_severity is None:

            current_risk_severity = get_nested(
                risk,
                "current_risk",
                "severity",
            )

        current_risk = {
            "score": current_risk_score,
            "severity": current_risk_severity,
        }

        # -------------------------------------------------
        # BLAST RADIUS
        # -------------------------------------------------

        blast_section = (
            blast.get("blast_radius")
            or blast.get("migration_impact")
            or {}
        )

        if not isinstance(
            blast_section,
            dict,
        ):
            blast_section = {}

        blast_score = blast_section.get(
            "score"
        )

        blast_severity = blast_section.get(
            "severity"
        )

        # Some datasets may expose the score directly.
        if blast_score is None:
            blast_score = blast.get(
                "score"
            )

        if blast_severity is None:
            blast_severity = blast.get(
                "severity"
            )

        # -------------------------------------------------
        # MIGRATION COMPLEXITY
        # -------------------------------------------------

        complexity_section = (
            complexity.get(
                "migration_complexity"
            )
            or complexity.get(
                "complexity"
            )
            or {}
        )

        if not isinstance(
            complexity_section,
            dict,
        ):
            complexity_section = {}

        complexity_score = complexity_section.get(
            "score"
        )

        complexity_level = complexity_section.get(
            "level"
        )

        if complexity_score is None:
            complexity_score = complexity.get(
                "score"
            )

        if complexity_level is None:
            complexity_level = complexity.get(
                "level"
            )

        # -------------------------------------------------
        # MIGRATION PRIORITY
        # -------------------------------------------------

        priority_section = (
            priority.get(
                "migration_priority"
            )
            or priority.get(
                "priority"
            )
            or {}
        )

        if not isinstance(
            priority_section,
            dict,
        ):
            priority_section = {}

        priority_score = priority_section.get(
            "priority_score"
        )

        if priority_score is None:
            priority_score = priority_section.get(
                "score"
            )

        if priority_score is None:
            priority_score = priority.get(
                "priority_score"
            )

        if priority_score is None:
            priority_score = priority.get(
                "score"
            )

        priority_level = priority_section.get(
            "priority"
        )

        if priority_level is None:
            priority_level = priority_section.get(
                "level"
            )

        if priority_level is None:
            priority_level = priority.get(
                "priority_level"
            )

        # -------------------------------------------------
        # PQC ANALYSIS
        # -------------------------------------------------

        pqc_analysis = pqc.get(
            "pqc_analysis",
            {},
        )

        if not isinstance(
            pqc_analysis,
            dict,
        ):
            pqc_analysis = {}

        if not pqc_analysis:

            pqc_analysis = pqc.get(
                "migration",
                {},
            )

            if not isinstance(
                pqc_analysis,
                dict,
            ):
                pqc_analysis = {}

        recommendation = pqc.get(
            "recommendation",
            {},
        )

        if not isinstance(
            recommendation,
            dict,
        ):
            recommendation = {}

        ranked_candidates = pqc.get(
            "ranked_candidates",
            [],
        )

        if not isinstance(
            ranked_candidates,
            list,
        ):
            ranked_candidates = []

        # -------------------------------------------------
        # RECOMMENDATION
        # -------------------------------------------------

        selected_candidate = recommendation.get(
            "candidate"
        )

        candidate_score = recommendation.get(
            "candidate_score"
        )

        candidate_rank = recommendation.get(
            "candidate_rank"
        )

        # If recommendation does not contain the selected
        # candidate, use the first ranked candidate.
        if (
            selected_candidate is None
            and ranked_candidates
        ):

            first_candidate = ranked_candidates[0]

            if isinstance(
                first_candidate,
                dict,
            ):

                selected_candidate = (
                    first_candidate.get(
                        "candidate"
                    )
                )

                candidate_score = (
                    first_candidate.get(
                        "score"
                    )
                )

                candidate_rank = (
                    first_candidate.get(
                        "rank"
                    )
                )

        # -------------------------------------------------
        # SOURCE IMPACT
        # -------------------------------------------------

        affected_files = actions.get(
            "affected_files",
            [],
        )

        affected_classes = actions.get(
            "affected_classes",
            [],
        )

        affected_functions = actions.get(
            "affected_functions",
            [],
        )

        migration_actions = actions.get(
            "actions",
            [],
        )

        if not isinstance(
            affected_files,
            list,
        ):
            affected_files = []

        if not isinstance(
            affected_classes,
            list,
        ):
            affected_classes = []

        if not isinstance(
            affected_functions,
            list,
        ):
            affected_functions = []

        if not isinstance(
            migration_actions,
            list,
        ):
            migration_actions = []

        action_count = actions.get(
            "action_count",
            len(migration_actions),
        )

        # -------------------------------------------------
        # FINAL REPORT RECORD
        # -------------------------------------------------

        report = {

            "asset": asset_name,

            "identity": {
                "id": (
                    risk.get("id")
                    or pqc.get("id")
                ),
                "asset_type": (
                    risk.get("asset_type")
                    or pqc.get("asset_type")
                ),
                "primitive": (
                    risk.get("primitive")
                    or pqc.get("primitive")
                ),
            },

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

            "current_risk": current_risk,

            "migration_impact": {

                "blast_radius": {
                    "score": blast_score,
                    "severity": blast_severity,
                },

                "complexity": {
                    "score": complexity_score,
                    "level": complexity_level,
                },

                "priority": {
                    "score": priority_score,
                    "level": priority_level,
                },
            },

            "pqc_migration": {

                "migration_type": pqc_analysis.get(
                    "migration_type"
                ),

                "pqc_applicable": pqc_analysis.get(
                    "pqc_applicable"
                ),

                "confidence": pqc_analysis.get(
                    "confidence"
                ),

                "reason": pqc_analysis.get(
                    "reason"
                ),
            },

            "recommendation": {

                "decision": recommendation.get(
                    "decision"
                ),

                "candidate": selected_candidate,

                "candidate_score": candidate_score,

                "candidate_rank": candidate_rank,

                "confidence": recommendation.get(
                    "confidence"
                ),

                "reason": recommendation.get(
                    "reason"
                ),
            },

            "ranked_candidates": ranked_candidates,

            "source_impact": {

                "affected_files": affected_files,

                "affected_file_count": len(
                    affected_files
                ),

                "affected_classes": affected_classes,

                "affected_class_count": len(
                    affected_classes
                ),

                "affected_functions": affected_functions,

                "affected_function_count": len(
                    affected_functions
                ),

                "impact_level": actions.get(
                    "impact_level"
                ),
            },

            "migration_actions": migration_actions,

            "action_count": action_count,

            "explanation": actions.get(
                "explanation",
                {},
            ),
        }

        reports.append(report)

    return reports


def build_summary(reports):

    migration_types = {}

    decisions = {}

    severity_distribution = {}

    impact_distribution = {}

    total_actions = 0

    candidates = 0

    high_or_critical_priority = 0

    for report in reports:

        migration_type = (
            report[
                "pqc_migration"
            ][
                "migration_type"
            ]
            or "none"
        )

        migration_types[
            migration_type
        ] = (
            migration_types.get(
                migration_type,
                0,
            )
            + 1
        )

        decision = (
            report[
                "recommendation"
            ][
                "decision"
            ]
            or "NONE"
        )

        decisions[
            decision
        ] = (
            decisions.get(
                decision,
                0,
            )
            + 1
        )

        severity = (
            report[
                "current_risk"
            ][
                "severity"
            ]
            or "UNKNOWN"
        )

        severity_distribution[
            severity
        ] = (
            severity_distribution.get(
                severity,
                0,
            )
            + 1
        )

        impact = (
            report[
                "source_impact"
            ][
                "impact_level"
            ]
            or "UNKNOWN"
        )

        impact_distribution[
            impact
        ] = (
            impact_distribution.get(
                impact,
                0,
            )
            + 1
        )

        total_actions += report[
            "action_count"
        ]

        if report[
            "recommendation"
        ][
            "candidate"
        ]:

            candidates += 1

        priority = report[
            "migration_impact"
        ][
            "priority"
        ]

        priority_level = priority.get(
            "level"
        )

        if priority_level in {
            "HIGH",
            "CRITICAL",
        }:

            high_or_critical_priority += 1

    return {

        "total_assets": len(
            reports
        ),

        "total_migration_actions": total_actions,

        "assets_with_pqc_candidates": candidates,

        "high_or_critical_priority_assets": (
            high_or_critical_priority
        ),

        "migration_type_distribution": (
            migration_types
        ),

        "recommendation_distribution": (
            decisions
        ),

        "risk_severity_distribution": (
            severity_distribution
        ),

        "source_impact_distribution": (
            impact_distribution
        ),
    }


def main():

    print(
        "Loading ECDAT migration-report data..."
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

    pqc_data = load_json(
        PQC_FILE
    )

    actions_data = load_json(
        ACTIONS_FILE
    )

    print(
        f"Risk records: "
        f"{len(assets_from(risk_data))}"
    )

    print(
        f"Blast-radius records: "
        f"{len(assets_from(blast_data))}"
    )

    print(
        f"Complexity records: "
        f"{len(assets_from(complexity_data))}"
    )

    print(
        f"Priority records: "
        f"{len(assets_from(priority_data))}"
    )

    print(
        f"PQC records: "
        f"{len(assets_from(pqc_data))}"
    )

    print(
        f"Action records: "
        f"{len(assets_from(actions_data))}"
    )

    print()
    print(
        "============================================="
    )
    print(
        "ECDAT MIGRATION REPORT GENERATION"
    )
    print(
        "============================================="
    )

    reports = build_report(
        risk_data,
        blast_data,
        complexity_data,
        priority_data,
        pqc_data,
        actions_data,
    )

    summary = build_summary(
        reports
    )

    output = {

        "metadata": {

            "project": "ECDAT",

            "stage": "9.6",

            "component":
                "migration-plan-reporting",

            "description":
                "Unified source-aware PQC migration report.",
        },

        "summary": summary,

        "assets": reports,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
        )

    print()
    print(
        "============================================="
    )
    print(
        "MIGRATION REPORT GENERATION COMPLETE"
    )
    print(
        "============================================="
    )

    print(
        f"Total assets: "
        f"{summary['total_assets']}"
    )

    print(
        f"Total migration actions: "
        f"{summary['total_migration_actions']}"
    )

    print(
        f"Assets with PQC candidates: "
        f"{summary['assets_with_pqc_candidates']}"
    )

    print(
        f"High/Critical priority assets: "
        f"{summary['high_or_critical_priority_assets']}"
    )

    print()
    print(
        "Migration types:"
    )

    for key, value in (
        summary[
            "migration_type_distribution"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print(
        "Recommendations:"
    )

    for key, value in (
        summary[
            "recommendation_distribution"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print(
        "Risk severity:"
    )

    for key, value in (
        summary[
            "risk_severity_distribution"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print(
        "Source impact:"
    )

    for key, value in (
        summary[
            "source_impact_distribution"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
"""
Blast-radius view: which findings (and source locations) are affected
if one cryptographic finding needs migration.

Read-only. It re-arranges what generate_blast_radius.py already
recorded, joined by bom_ref only:

    data/ecdat-blast-radius.json        score, severity, breakdown, reasons,
                                        and the direct-dependency, direct-
                                        dependent and transitive-dependent
                                        bom_ref sets
    data/ecdat-assets.json              names, asset types, source
                                        occurrences, and the CycloneDX
                                        `dependencies` (ref dependsOn X)
                                        the blast-radius stage was built from
    data/ecdat-explainable-risk.json    classification category
    data/ecdat-migration-complexity.json recorded complexity
    data/ecdat-pqc-migration-plan.json  migration strategy (only so a
                                        NEEDS_REVIEW finding is labelled)

Nodes are exactly the bom_refs the blast-radius stage recorded. Edges
are exactly the CycloneDX dependsOn relationships between those nodes
that the stage traversed; nothing is inferred from shared files,
names or categories, and no score is recomputed.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

FILES = {
    "assets": "ecdat-assets.json",
    "blast": "ecdat-blast-radius.json",
    "risk": "ecdat-explainable-risk.json",
    "complexity": "ecdat-migration-complexity.json",
    "plan": "ecdat-pqc-migration-plan.json",
}

RELATIONSHIP_SOURCE = (
    "CycloneDX dependencies (ref dependsOn X) recorded in the CBOM, "
    "as used by generate_blast_radius.py"
)


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _load(path: Path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _by_ref(data):
    records = data.get("assets", []) if isinstance(data, dict) else data
    return {
        str(record.get("bom_ref") or record.get("asset_ref")): record
        for record in records or []
        if isinstance(record, dict) and (record.get("bom_ref") or record.get("asset_ref"))
    }


def load_blast_radius_records(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    data_dir = Path(data_dir)
    assets_file = _load(data_dir / FILES["assets"])

    records = {key: _by_ref(_load(data_dir / filename)) for key, filename in FILES.items() if key != "assets"}
    records["assets"] = _by_ref(assets_file)

    # The same edge list generate_blast_radius.py builds its graph from,
    # de-duplicated (the CBOM repeats identical entries).
    edges = set()
    for entry in _as_list(assets_file.get("dependencies")):
        ref = _as_dict(entry).get("ref")
        for target in _as_list(_as_dict(entry).get("dependsOn")):
            if ref and target:
                edges.add((str(ref), str(target)))
    records["edges"] = sorted(edges)

    return records


def _source_locations(asset):
    occurrences = [
        {
            "location": occurrence.get("location"),
            "line": occurrence.get("line"),
        }
        for occurrence in _as_list(asset.get("occurrences"))
        if isinstance(occurrence, dict)
    ]
    files = sorted({occurrence["location"] for occurrence in occurrences if occurrence["location"]})
    return occurrences, files


def _node(bom_ref, records, relation):
    asset = records["assets"].get(bom_ref)
    classification = _as_dict(_as_dict(records["risk"].get(bom_ref)).get("classification"))

    if asset is None:
        # Recorded by the blast-radius stage but absent from the inventory:
        # reported as unknown, never filled in.
        return {
            "bom_ref": bom_ref,
            "relation": relation,
            "known_finding": False,
            "name": None,
            "asset_type": None,
            "category": None,
            "occurrence_count": None,
            "source_files": [],
        }

    occurrences, files = _source_locations(asset)

    return {
        "bom_ref": bom_ref,
        "relation": relation,
        "known_finding": True,
        "name": asset.get("name"),
        "asset_type": asset.get("asset_type"),
        "category": classification.get("category"),
        "occurrence_count": len(occurrences),
        "source_files": files,
    }


def build_blast_radius_view(bom_ref: str, records: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    asset = records["assets"].get(bom_ref)

    if asset is None:
        return None

    blast = records["blast"].get(bom_ref)
    complexity = records["complexity"].get(bom_ref)
    strategy = _as_dict(_as_dict(records["plan"].get(bom_ref)).get("migration_strategy"))

    dependencies = [str(ref) for ref in _as_list(_as_dict(_as_dict(blast).get("direct_dependencies")).get("refs"))]
    direct = [str(ref) for ref in _as_list(_as_dict(_as_dict(blast).get("direct_dependents")).get("refs"))]
    transitive = [str(ref) for ref in _as_list(_as_dict(_as_dict(blast).get("transitive_dependents")).get("refs"))]
    indirect = [ref for ref in transitive if ref not in direct]

    affected = set(transitive)
    dependency_set = set(dependencies)

    # Only recorded dependsOn edges the blast-radius traversal covers:
    #   dependent -> (this finding or another affected finding)
    #   this finding -> each of its direct dependencies
    edges = [
        {"from": source, "to": target, "relation": "depends-on"}
        for source, target in records["edges"]
        if (source in affected and (target == bom_ref or target in affected))
        or (source == bom_ref and target in dependency_set)
    ]

    indirect_nodes = []
    for ref in indirect:
        node = _node(ref, records, "indirect-dependent")
        node["via"] = [edge["to"] for edge in edges if edge["from"] == ref and edge["to"] in affected]
        indirect_nodes.append(node)

    occurrences, files = _source_locations(asset)
    classification = _as_dict(_as_dict(records["risk"].get(bom_ref)).get("classification"))
    explanation = _as_dict(_as_dict(blast).get("explanation"))

    return {
        "bom_ref": bom_ref,
        "relationship_source": RELATIONSHIP_SOURCE,
        "finding": {
            "bom_ref": bom_ref,
            "name": asset.get("name"),
            "asset_type": asset.get("asset_type"),
            "category": classification.get("category"),
            "occurrence_count": len(occurrences),
            "source_files": files,
            "occurrences": occurrences,
        },
        "blast_radius": {
            "score": blast.get("blast_radius_score"),
            "severity": blast.get("severity"),
            "score_breakdown": blast.get("score_breakdown"),
            "summary": explanation.get("summary"),
            "reasons": _as_list(explanation.get("reasons")),
        } if blast else None,
        "migration_complexity": {
            "score": complexity.get("score"),
            "level": complexity.get("level"),
        } if complexity else None,
        "migration_strategy": {
            "strategy": strategy.get("strategy"),
            "label": strategy.get("label"),
            "resolved": strategy.get("strategy") != "NEEDS_REVIEW",
        } if strategy else None,
        "has_relationships": bool(dependencies or transitive),
        "counts": {
            "dependencies": len(dependencies),
            "direct_dependents": len(direct),
            "indirect_dependents": len(indirect),
            "affected_findings": len(transitive),
            "source_occurrences": len(occurrences),
            "source_files": len(files),
        } if blast else None,
        "dependencies": [_node(ref, records, "dependency") for ref in dependencies],
        "direct_dependents": [_node(ref, records, "direct-dependent") for ref in direct],
        "indirect_dependents": indirect_nodes,
        "edges": edges,
    }

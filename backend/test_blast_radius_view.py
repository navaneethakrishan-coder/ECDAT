"""
Blast-radius visualization API (services/blast_radius_view.py,
GET /api/blast-radius/{bom_ref}/graph).

Relationships are checked independently against the raw CycloneDX CBOM, not
against the pipeline's own output, so a fabricated or misattributed edge
cannot pass by agreeing with itself.

Runs against the fixture dataset (fixture_dataset.py) rather than `data/`:
the duplicate-RSA-2048 case below needs two findings that share a name and
differ only by bom_ref, and `data/` only happens to contain that shape
depending on which repository was scanned last.
"""

import hashlib
import json
from collections import Counter, defaultdict

from fastapi import HTTPException

import fixture_dataset
import main
from services import blast_radius_view


DATA_DIR = fixture_dataset.use_fixture_data(main, blast_radius_view)


def _load(filename):
    return fixture_dataset.load(filename)


def _by_ref(filename):
    return {record["bom_ref"]: record for record in _load(filename)["assets"]}


def _raw_edges():
    cbom = _load("keycloak-cbom.json")
    return {
        (entry["ref"], target)
        for entry in cbom.get("dependencies", [])
        for target in entry.get("dependsOn", [])
    }


def _view(bom_ref):
    return main.get_blast_radius_graph(bom_ref)


def _fingerprint():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(DATA_DIR.glob("*.json"))}


def test_blast_radius_response_copies_the_recorded_blast_radius():
    blast = _by_ref("ecdat-blast-radius.json")
    complexity = _by_ref("ecdat-migration-complexity.json")
    assets = _by_ref("ecdat-assets.json")

    for bom_ref, source in assets.items():
        view = _view(bom_ref)
        record = blast[bom_ref]

        assert view["bom_ref"] == view["finding"]["bom_ref"] == bom_ref
        assert view["finding"]["name"] == source["name"]
        assert view["blast_radius"]["score"] == record["blast_radius_score"]
        assert view["blast_radius"]["severity"] == record["severity"]
        assert view["blast_radius"]["score_breakdown"] == record["score_breakdown"]
        assert view["migration_complexity"] == {
            "score": complexity[bom_ref]["score"],
            "level": complexity[bom_ref]["level"],
        }

        counts = view["counts"]
        assert counts["dependencies"] == record["direct_dependencies"]["count"] == len(view["dependencies"])
        assert counts["direct_dependents"] == record["direct_dependents"]["count"] == len(view["direct_dependents"])
        assert counts["affected_findings"] == record["transitive_dependents"]["count"]
        assert counts["direct_dependents"] + counts["indirect_dependents"] == counts["affected_findings"]
        assert counts["source_occurrences"] == len(source["occurrences"])
        assert counts["source_files"] == len({o["location"] for o in source["occurrences"]})
        json.dumps(view)


def test_findings_are_addressed_by_bom_ref_only():
    names = Counter(asset["name"] for asset in _load("ecdat-assets.json")["assets"])
    duplicate_name = next(name for name, count in names.items() if count > 1)

    try:
        _view(duplicate_name)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail["reason_code"] == "unknown-finding"
    else:
        raise AssertionError("An algorithm name must not resolve to a finding.")

    for bom_ref in _by_ref("ecdat-assets.json"):
        view = _view(bom_ref)
        for node in view["dependencies"] + view["direct_dependents"] + view["indirect_dependents"]:
            assert node["bom_ref"] != bom_ref
            assert node["known_finding"] is True
        for edge in view["edges"]:
            assert edge["from"] and edge["to"]


def test_duplicate_rsa_2048_findings_show_only_their_own_relationships():
    raw = _raw_edges()
    refs = [asset["bom_ref"] for asset in _load("ecdat-assets.json")["assets"] if asset["name"] == "RSA-2048"]
    assert len(refs) == 2

    views = {ref: _view(ref) for ref in refs}

    for ref, view in views.items():
        other = next(r for r in refs if r != ref)
        expected_dependents = sorted(source for source, target in raw if target == ref)

        assert sorted(node["bom_ref"] for node in view["direct_dependents"]) == expected_dependents
        assert all(edge["to"] == ref for edge in view["edges"])
        assert other not in json.dumps(view)

        other_dependents = {source for source, target in raw if target == other}
        assert not other_dependents & {node["bom_ref"] for node in view["direct_dependents"]}

        own_files = {o["location"] for o in _by_ref("ecdat-assets.json")[ref]["occurrences"]}
        assert set(view["finding"]["source_files"]) == own_files

    first, second = views.values()
    assert first["direct_dependents"] != second["direct_dependents"]
    assert first["finding"]["source_files"] != second["finding"]["source_files"]


def test_dependency_relationships_match_the_raw_cbom():
    raw = _raw_edges()
    dependents_of = defaultdict(set)
    for source, target in raw:
        dependents_of[target].add(source)

    for bom_ref in _by_ref("ecdat-assets.json"):
        view = _view(bom_ref)

        assert {n["bom_ref"] for n in view["dependencies"]} == {t for s, t in raw if s == bom_ref}
        assert {n["bom_ref"] for n in view["direct_dependents"]} == dependents_of[bom_ref]

        # Independent reverse traversal of the raw CBOM edges.
        reachable, frontier = set(), [bom_ref]
        while frontier:
            for dependent in dependents_of[frontier.pop()]:
                if dependent not in reachable and dependent != bom_ref:
                    reachable.add(dependent)
                    frontier.append(dependent)

        affected = {n["bom_ref"] for n in view["direct_dependents"] + view["indirect_dependents"]}
        assert affected == reachable

        for node in view["indirect_dependents"]:
            assert node["via"], "An indirect dependent must be reached through a recorded edge."
            for parent in node["via"]:
                assert (node["bom_ref"], parent) in raw
                assert parent in affected

    # A recorded transitive chain: a finding whose dependents have dependents.
    chained = [
        ref for ref in _by_ref("ecdat-assets.json") if _view(ref)["indirect_dependents"]
    ]
    assert chained, "The fixture must contain a transitive dependency chain."


def test_finding_with_no_relationships():
    raw = _raw_edges()
    related = {s for s, _ in raw} | {t for _, t in raw}
    unrelated = [ref for ref in _by_ref("ecdat-assets.json") if ref not in related]

    assert unrelated, "The fixture must contain findings with no CBOM relationships."

    for bom_ref in unrelated:
        view = _view(bom_ref)

        assert view["has_relationships"] is False
        assert view["dependencies"] == []
        assert view["direct_dependents"] == []
        assert view["indirect_dependents"] == []
        assert view["edges"] == []
        assert view["counts"]["affected_findings"] == 0
        # Its blast radius is still reported, from its own recorded breakdown.
        assert view["blast_radius"]["score"] is not None
        assert view["blast_radius"]["score_breakdown"]["direct_dependent_score"] == 0


def test_no_fabricated_relationships():
    raw = _raw_edges()
    assets = _by_ref("ecdat-assets.json")

    for bom_ref in assets:
        for edge in _view(bom_ref)["edges"]:
            assert (edge["from"], edge["to"]) in raw

    # Findings that merely share a source file are not related unless the
    # CBOM records a dependsOn edge between them.
    by_file = defaultdict(set)
    for ref, asset in assets.items():
        for occurrence in asset["occurrences"]:
            by_file[occurrence["location"]].add(ref)

    unrelated_pairs = [
        (a, b)
        for refs in by_file.values()
        for a in refs
        for b in refs
        if a != b and (a, b) not in raw and (b, a) not in raw
    ]
    assert unrelated_pairs, "The fixture must contain co-located findings without a dependency."

    for a, b in unrelated_pairs:
        view = _view(a)
        related = {
            node["bom_ref"]
            for node in view["dependencies"] + view["direct_dependents"] + view["indirect_dependents"]
        }
        transitive = set(_by_ref("ecdat-blast-radius.json")[a]["transitive_dependents"]["refs"])
        if b not in transitive:
            assert b not in related


def test_needs_review_finding_is_labelled_but_blast_radius_is_reported_normally():
    plan = _by_ref("ecdat-pqc-migration-plan.json")
    ref = next(r for r, record in plan.items() if record["migration_strategy"]["strategy"] == "NEEDS_REVIEW")
    view = _view(ref)

    assert view["migration_strategy"]["resolved"] is False
    assert view["blast_radius"]["score"] == _by_ref("ecdat-blast-radius.json")[ref]["blast_radius_score"]


def test_blast_radius_view_is_read_only():
    fingerprint = _fingerprint()

    for bom_ref in _by_ref("ecdat-assets.json"):
        _view(bom_ref)

    assert _fingerprint() == fingerprint


if __name__ == "__main__":
    test_blast_radius_response_copies_the_recorded_blast_radius()
    test_findings_are_addressed_by_bom_ref_only()
    test_duplicate_rsa_2048_findings_show_only_their_own_relationships()
    test_dependency_relationships_match_the_raw_cbom()
    test_finding_with_no_relationships()
    test_no_fabricated_relationships()
    test_needs_review_finding_is_labelled_but_blast_radius_is_reported_normally()
    test_blast_radius_view_is_read_only()

    print("All blast-radius view tests passed.")

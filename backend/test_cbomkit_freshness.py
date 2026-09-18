"""The CBOMKit adapter must never pass off a pre-scan CBOM as a new scan.

CBOMKit keeps every CBOM it has ever produced and serves them from
/api/v1/cbom/last/{n}, so a repository scanned before this request already
has a record waiting the moment the scan starts. These tests pin the rule:
a CBOM is only accepted as the result of this scan when CBOMKit's own record
is demonstrably later, and a record CBOMKit keeps for an unchanged commit is
labelled as cached rather than reported as fresh.

Runs against a fake HTTP client, so no CBOMKit and no network are involved.
"""

import requests

from services.scanning.cbomkit import CBOMKitRepositoryScanner
from services.scanning.base import ScannerError
from services.scanning.targets import parse_repository_target


TARGET = parse_repository_target("https://github.com/pyca/cryptography", "main")


def record(commit, created_at, git_url="https://github.com/pyca/cryptography", branch="main"):
    return {
        "projectIdentifier": f"pkg:github/pyca/cryptography@{commit}",
        "gitUrl": git_url,
        "branch": branch,
        "commit": commit,
        "createdAt": created_at,
        "bom": {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "components": [{"bom-ref": f"ref-{commit}", "cryptoProperties": {"assetType": "algorithm"}}],
            "dependencies": [],
        },
    }


class FakeClient:
    """A CBOMKit whose stored records change on a schedule we control."""

    base_url = "http://cbomkit.test"

    def __init__(self, timeline):
        # timeline: list of record-lists, one per lookup. The availability
        # probe (count=1) does not advance it, so each entry is one step of
        # the scan itself: [what exists at baseline, then each poll].
        self.timeline = list(timeline)
        self.calls = 0
        self.scans = []

    def recent_cboms(self, count=5):
        if count == 1:  # availability probe
            return self.timeline[0]
        self.calls += 1
        index = min(self.calls - 1, len(self.timeline) - 1)
        return self.timeline[index]

    def start_scan(self, git_url, branch):
        self.scans.append((git_url, branch))
        return None


def build(client, **kwargs):
    options = {"poll_interval": 0, "timeout_seconds": 5, "accept_cached_after": 1000}
    options.update(kwargs)
    return CBOMKitRepositoryScanner(client=client, **options)


def test_a_first_ever_scan_accepts_the_record_it_produces():
    old = record("aaaaaaa", 1_000)
    client = FakeClient([[], [old]])  # nothing at baseline, then the new CBOM lands
    artifact = build(client).scan(TARGET)

    assert artifact.source["commit"] == "aaaaaaa"
    assert artifact.source["freshness"] == "fresh-scan"
    assert client.scans == [("https://github.com/pyca/cryptography", "main")]


def test_a_pre_existing_record_is_not_accepted_as_this_scan():
    """The critical case: the repository was scanned before, so a record is
    already waiting when polling starts. It must be ignored until CBOMKit
    produces a later one."""
    stale = record("a825ca0", 1_788_098_335_178)
    fresh = record("19ff778", 1_789_728_373_897)
    # Baseline sees the stale record; the next polls still only have the
    # stale record; then the real scan finishes.
    client = FakeClient([[stale], [stale], [stale], [fresh]])

    artifact = build(client).scan(TARGET)

    assert artifact.source["commit"] == "19ff778", "the stale CBOM was accepted as this scan's result"
    assert artifact.source["freshness"] == "fresh-scan"
    assert artifact.cbom["components"][0]["bom-ref"] == "ref-19ff778"


def test_a_re_scan_of_the_same_commit_is_reported_as_cached_not_fresh():
    """CBOMKit may keep the record it has when nothing changed. That is a
    valid answer, but it is not a new scan, so it is labelled."""
    existing = record("a825ca0", 1_788_098_335_178)
    client = FakeClient([[existing]])  # nothing ever changes

    artifact = build(client, accept_cached_after=0).scan(TARGET)

    assert artifact.source["freshness"] == "cbomkit-cached"
    assert artifact.source["commit"] == "a825ca0"
    assert artifact.source["cbom_created_at"].startswith("2026-")
    assert "kept the record it already held" in artifact.source["freshness_detail"]


def test_waiting_for_a_new_cbom_times_out_rather_than_using_the_old_one():
    """With no cached fallback in reach, a stale-only CBOMKit is a timeout --
    never a silent success on last month's data."""
    existing = record("a825ca0", 1_788_098_335_178)
    client = FakeClient([[existing]])

    try:
        build(client, timeout_seconds=0.3, accept_cached_after=1000).scan(TARGET)
    except ScannerError as error:
        assert error.code == "cbomkit-timeout", error.code
    else:
        raise AssertionError("a stale-only CBOMKit should not produce a result")


def test_a_new_record_for_a_different_commit_counts_even_without_timestamps():
    old = record("aaaaaaa", None)
    new = record("bbbbbbb", None)
    client = FakeClient([[old], [old], [new]])

    artifact = build(client).scan(TARGET)
    assert artifact.source["commit"] == "bbbbbbb"
    assert artifact.source["freshness"] == "fresh-scan"


def test_another_repository_is_never_mistaken_for_this_target():
    other = record("ccccccc", 9_999_999, git_url="https://github.com/other/repo")
    mine = record("ddddddd", 1_000)
    client = FakeClient([[other], [other, mine]])

    artifact = build(client).scan(TARGET)
    assert artifact.source["commit"] == "ddddddd"
    assert artifact.source["git_url"] == "https://github.com/pyca/cryptography"


def test_a_different_branch_is_never_mistaken_for_this_target():
    other_branch = record("eeeeeee", 9_999_999, branch="develop")
    mine = record("fffffff", 1_000)
    client = FakeClient([[other_branch], [other_branch, mine]])

    artifact = build(client).scan(TARGET)
    assert artifact.source["commit"] == "fffffff"
    assert artifact.source["branch"] == "main"


def test_a_cbomkit_that_cannot_be_reached_before_the_scan_fails_clearly():
    class DeadClient(FakeClient):
        def recent_cboms(self, count=5):
            self.calls += 1
            if self.calls == 1:
                return []  # availability probe succeeds
            raise requests.ConnectionError("connection refused")

    try:
        build(DeadClient([[]])).scan(TARGET)
    except ScannerError as error:
        assert error.code == "cbomkit-unavailable", error.code
    else:
        raise AssertionError("an unreachable CBOMKit must fail the scan")


def test_a_rejected_scan_request_is_reported_with_its_own_code():
    class RejectingClient(FakeClient):
        def start_scan(self, git_url, branch):
            raise requests.HTTPError("400 Bad Request")

    try:
        build(RejectingClient([[]])).scan(TARGET)
    except ScannerError as error:
        assert error.code == "cbomkit-scan-rejected", error.code
    else:
        raise AssertionError("a rejected scan request must fail the scan")


if __name__ == "__main__":
    test_a_first_ever_scan_accepts_the_record_it_produces()
    test_a_pre_existing_record_is_not_accepted_as_this_scan()
    test_a_re_scan_of_the_same_commit_is_reported_as_cached_not_fresh()
    test_waiting_for_a_new_cbom_times_out_rather_than_using_the_old_one()
    test_a_new_record_for_a_different_commit_counts_even_without_timestamps()
    test_another_repository_is_never_mistaken_for_this_target()
    test_a_different_branch_is_never_mistaken_for_this_target()
    test_a_cbomkit_that_cannot_be_reached_before_the_scan_fails_clearly()
    test_a_rejected_scan_request_is_reported_with_its_own_code()
    print("All CBOMKit freshness tests passed.")

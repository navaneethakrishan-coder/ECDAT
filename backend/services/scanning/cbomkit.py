"""CBOMKit adapter: scans a GitHub repository and returns its CBOM.

This is the one scanner ECDAT has today. It wraps IBM CBOMKit's HTTP API
(the same endpoints the previous cbomkit_client.py script used) behind the
Scanner interface. It reports what CBOMKit actually did -- it never invents
a CBOM, a component or progress it cannot observe.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from .base import Availability, ScanArtifact, Scanner, ScannerError, ProgressCallback

DEFAULT_CBOMKIT_URL = os.environ.get("ECDAT_CBOMKIT_URL", "http://localhost:8081")

# How many of CBOMKit's most recent CBOMs to search for this target. CBOMKit
# is shared, so the window has to be wide enough that other projects' scans
# cannot push ours out of sight while we poll.
RECENT_WINDOW = 20


def _normalise(url: str) -> str:
    return (url or "").strip().rstrip("/").removesuffix(".git").lower()


def _created_at(entry) -> Optional[int]:
    """CBOMKit's record timestamp (epoch ms), when it reports one."""
    value = (entry or {}).get("createdAt")
    return value if isinstance(value, (int, float)) else None


def _commit(entry) -> Optional[str]:
    entry = entry or {}
    return entry.get("commit") or entry.get("gitCommit")


def _identity(entry) -> tuple:
    """What makes one CBOMKit record distinguishable from another."""
    entry = entry or {}
    return (_created_at(entry), _commit(entry), entry.get("projectIdentifier"))


def _isoformat(created_at) -> Optional[str]:
    if not created_at:
        return None
    return datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def _is_newer(entry, baseline) -> bool:
    """Whether `entry` is a genuinely later CBOMKit record than `baseline`.

    A record with a newer timestamp, a different commit or a different
    project identifier is the product of a later scan. Anything else is the
    record CBOMKit already held before this scan was requested.
    """
    if baseline is None:
        return True

    entry_created, baseline_created = _created_at(entry), _created_at(baseline)
    if entry_created is not None and baseline_created is not None:
        if entry_created > baseline_created:
            return True
        if entry_created < baseline_created:
            return False
        # Same instant: only a different record counts as new.
        return _identity(entry)[1:] != _identity(baseline)[1:]

    return _identity(entry) != _identity(baseline)


class CBOMKitClient:
    """Thin HTTP client for CBOMKit (injectable for tests)."""

    def __init__(self, base_url: str = DEFAULT_CBOMKIT_URL, session=None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def recent_cboms(self, count: int = 5):
        response = self.session.get(f"{self.base_url}/api/v1/cbom/last/{count}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def start_scan(self, git_url: str, branch: str):
        response = self.session.post(
            f"{self.base_url}/api/v1/scan",
            json={"scanUrl": git_url, "branch": branch},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response


class CBOMKitRepositoryScanner(Scanner):
    """Scans a public git repository with CBOMKit and returns its CBOM."""

    key = "cbomkit-repository"
    title = "CBOMKit source scan"
    target_kind = "git-repository"
    requires = f"CBOMKit reachable at {DEFAULT_CBOMKIT_URL}"

    def __init__(
        self,
        client: Optional[CBOMKitClient] = None,
        poll_interval: float = 10.0,
        timeout_seconds: int = 1800,
        accept_cached_after: float = 900.0,
    ):
        self.client = client or CBOMKitClient()
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        # CBOMKit may answer a re-scan of an unchanged commit by keeping the
        # record it already has. After this long with no newer record we stop
        # waiting and use that one -- clearly labelled as CBOMKit's cached
        # result, never presented as a fresh scan.
        #
        # This is a last resort, not a shortcut: measured CBOMKit re-scans of
        # a repository this size take 3-5 minutes (10+ for a large C project),
        # so a short window would label a result cached while a fresh CBOM was
        # still on its way. 15 minutes leaves CBOMKit room to answer properly
        # and still returns well inside the 30-minute scan timeout.
        self.accept_cached_after = accept_cached_after
        self.requires = f"CBOMKit reachable at {self.client.base_url}"

    def check_availability(self) -> Availability:
        try:
            self.client.recent_cboms(1)
            return Availability(True, f"CBOMKit responded at {self.client.base_url}.")
        except requests.RequestException as error:
            return Availability(
                False,
                f"CBOMKit is not reachable at {self.client.base_url} ({error.__class__.__name__}).",
            )

    def _find_cbom(self, target):
        """Returns the newest CBOM entry CBOMKit holds for this target, or None."""
        entries = self.client.recent_cboms(RECENT_WINDOW)
        wanted_urls = {_normalise(target.url), _normalise(target.original_url)}
        matches = []
        for entry in entries or []:
            if _normalise(entry.get("gitUrl", "")) not in wanted_urls:
                continue
            if (entry.get("branch") or "").strip() != target.branch:
                continue
            if entry.get("bom"):
                matches.append(entry)

        if not matches:
            return None
        # CBOMKit returns newest first, but sort defensively: "newest" is the
        # decision this scanner's freshness check depends on.
        matches.sort(key=lambda entry: _created_at(entry) or 0, reverse=True)
        return matches[0]

    def _artifact(self, entry, target, freshness: str, detail: Optional[str] = None) -> ScanArtifact:
        source = {
            "scanner": self.key,
            "scanner_title": self.title,
            "git_url": entry.get("gitUrl") or target.url,
            "branch": entry.get("branch") or target.branch,
            # Only recorded when CBOMKit reports it.
            "commit": _commit(entry),
            "cbomkit_url": self.client.base_url,
            # Whether this CBOM came from the scan just requested, or is one
            # CBOMKit already held. Never inferred -- it follows CBOMKit's own
            # record timestamp and commit.
            "freshness": freshness,
            "cbom_created_at": _isoformat(_created_at(entry)),
        }
        if detail:
            source["freshness_detail"] = detail
        return ScanArtifact(cbom=entry["bom"], source=source)

    def scan(self, target, progress: Optional[ProgressCallback] = None) -> ScanArtifact:
        def report(message: str):
            if progress:
                progress(message)

        if not self.supports(target):
            raise ScannerError("unsupported-target", f"{self.title} cannot scan a '{target.kind}' target.")

        availability = self.check_availability()
        if not availability.available:
            raise ScannerError("cbomkit-unavailable", availability.detail)

        # What CBOMKit already holds for this target, before we ask for a
        # scan. Everything below is judged against this: a CBOM that is not
        # demonstrably later than this record is not the result of this scan.
        try:
            baseline = self._find_cbom(target)
        except requests.RequestException as error:
            raise ScannerError(
                "cbomkit-unavailable",
                f"CBOMKit did not answer before the scan started: {error}",
            ) from error

        baseline_stamp = _isoformat(_created_at(baseline))
        if baseline:
            report(
                f"CBOMKit already holds a CBOM for {target.slug}"
                + (f" (commit {_commit(baseline)}" if _commit(baseline) else " (")
                + (f", scanned {baseline_stamp})." if baseline_stamp else ").")
                + " Waiting for the result of this scan."
            )

        report(f"Requesting CBOMKit scan of {target.slug} ({target.branch})…")
        try:
            self.client.start_scan(target.url, target.branch)
        except requests.RequestException as error:
            raise ScannerError("cbomkit-scan-rejected", f"CBOMKit rejected the scan request: {error}") from error

        started = time.monotonic()
        deadline = started + self.timeout_seconds
        attempts = 0
        last_error = None

        while time.monotonic() < deadline:
            attempts += 1
            waited = time.monotonic() - started
            try:
                entry = self._find_cbom(target)
            except requests.RequestException as error:
                entry, last_error = None, error

            if entry and _is_newer(entry, baseline):
                report(f"CBOMKit returned a new CBOM after {attempts} check(s).")
                return self._artifact(entry, target, "fresh-scan")

            # CBOMKit kept the record it already had. That is a legitimate
            # answer for an unchanged commit, but it is not a new scan, so it
            # is only used once waiting has clearly stopped being productive,
            # and it is labelled as cached wherever it is shown.
            if entry and baseline is not None and waited >= self.accept_cached_after:
                detail = (
                    f"CBOMKit returned no new CBOM within {int(waited)}s and kept the record it already held"
                    + (f" (commit {_commit(entry)}" if _commit(entry) else " (")
                    + (f", scanned {_isoformat(_created_at(entry))})." if _created_at(entry) else ").")
                )
                report(detail)
                return self._artifact(entry, target, "cbomkit-cached", detail)

            report(
                f"CBOMKit is scanning {target.slug}… {int(waited)}s elapsed"
                + (f" (last API error: {last_error})" if last_error else "")
            )
            time.sleep(self.poll_interval)

        raise ScannerError(
            "cbomkit-timeout",
            f"CBOMKit did not produce a CBOM for {target.slug} ({target.branch}) within {self.timeout_seconds}s.",
        )

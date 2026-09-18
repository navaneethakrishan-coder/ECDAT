"""CBOMKit adapter: scans a GitHub repository and returns its CBOM.

This is the one scanner ECDAT has today. It wraps IBM CBOMKit's HTTP API
(the same endpoints the previous cbomkit_client.py script used) behind the
Scanner interface. It reports what CBOMKit actually did -- it never invents
a CBOM, a component or progress it cannot observe.
"""

import os
import time
from typing import Optional

import requests

from .base import Availability, ScanArtifact, Scanner, ScannerError, ProgressCallback

DEFAULT_CBOMKIT_URL = os.environ.get("ECDAT_CBOMKIT_URL", "http://localhost:8081")


def _normalise(url: str) -> str:
    return (url or "").strip().rstrip("/").removesuffix(".git").lower()


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

    def __init__(self, client: Optional[CBOMKitClient] = None, poll_interval: float = 10.0, timeout_seconds: int = 1800):
        self.client = client or CBOMKitClient()
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
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
        """Returns the CBOM entry CBOMKit holds for this target, or None."""
        entries = self.client.recent_cboms(5)
        wanted_urls = {_normalise(target.url), _normalise(target.original_url)}
        for entry in entries or []:
            if _normalise(entry.get("gitUrl", "")) not in wanted_urls:
                continue
            if (entry.get("branch") or "").strip() != target.branch:
                continue
            if entry.get("bom"):
                return entry
        return None

    def scan(self, target, progress: Optional[ProgressCallback] = None) -> ScanArtifact:
        def report(message: str):
            if progress:
                progress(message)

        if not self.supports(target):
            raise ScannerError("unsupported-target", f"{self.title} cannot scan a '{target.kind}' target.")

        availability = self.check_availability()
        if not availability.available:
            raise ScannerError("cbomkit-unavailable", availability.detail)

        report(f"Requesting CBOMKit scan of {target.slug} ({target.branch})…")
        try:
            self.client.start_scan(target.url, target.branch)
        except requests.RequestException as error:
            raise ScannerError("cbomkit-scan-rejected", f"CBOMKit rejected the scan request: {error}") from error

        deadline = time.monotonic() + self.timeout_seconds
        attempts = 0
        last_error = None

        while time.monotonic() < deadline:
            attempts += 1
            try:
                entry = self._find_cbom(target)
                if entry:
                    bom = entry["bom"]
                    report(f"CBOMKit returned a CBOM after {attempts} check(s).")
                    return ScanArtifact(
                        cbom=bom,
                        source={
                            "scanner": self.key,
                            "scanner_title": self.title,
                            "git_url": entry.get("gitUrl") or target.url,
                            "branch": entry.get("branch") or target.branch,
                            # Only recorded when CBOMKit reports it.
                            "commit": entry.get("commit") or entry.get("gitCommit"),
                            "cbomkit_url": self.client.base_url,
                        },
                    )
            except requests.RequestException as error:
                last_error = error

            elapsed = int(self.timeout_seconds - max(deadline - time.monotonic(), 0))
            report(
                f"CBOMKit is scanning {target.slug}… {elapsed}s elapsed"
                + (f" (last API error: {last_error})" if last_error else "")
            )
            time.sleep(self.poll_interval)

        raise ScannerError(
            "cbomkit-timeout",
            f"CBOMKit did not produce a CBOM for {target.slug} ({target.branch}) within {self.timeout_seconds}s.",
        )

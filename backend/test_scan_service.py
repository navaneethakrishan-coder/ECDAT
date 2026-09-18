"""The scan lifecycle: stages, failures and the record it publishes.

Runs entirely on a fake scanner and a fake pipeline runner, so it never
touches CBOMKit, the network, or the real data/ directory.
"""

import json
import tempfile
from pathlib import Path

from services.scanning.base import Availability, ScanArtifact, Scanner, ScannerError
from services.scanning.registry import ScannerRegistry
from services.scanning.service import ScanService
from services.scanning.targets import GIT_REPOSITORY, TargetError


def crypto_cbom(ref="finding-1"):
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"bom-ref": ref, "name": "RSA-2048", "cryptoProperties": {"assetType": "algorithm"}}],
        "dependencies": [],
    }


class FakeScanner(Scanner):
    key = "fake"
    title = "Fake scanner"
    target_kind = GIT_REPOSITORY
    requires = "nothing"

    def __init__(self, cbom=None, available=True, error=None):
        self.cbom = cbom if cbom is not None else crypto_cbom()
        self.available = available
        self.error = error
        self.scanned = []
        self.progress_messages = []

    def check_availability(self):
        return Availability(self.available, "fake is available" if self.available else "fake is not running")

    def scan(self, target, progress=None):
        self.scanned.append((target.url, target.branch))
        if progress:
            progress("scanning…")
            self.progress_messages.append("scanning…")
        if self.error:
            raise self.error
        return ScanArtifact(cbom=self.cbom, source={"scanner": self.key, "git_url": target.url, "branch": target.branch})


class FakePipeline:
    """Stands in for the real 13-stage runner."""

    STAGES = (("CBOM Parser", "cbom_parser.py"), ("Classification", "classify_cbom.py"))

    class Result:
        def __init__(self, name, script, ok, returncode=0, output_tail=""):
            self.name, self.script, self.ok, self.returncode, self.output_tail = name, script, ok, returncode, output_tail

    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.ran = []

    def __call__(self, on_stage_start=None, on_stage_end=None):
        results = []
        for name, script in self.STAGES:
            if on_stage_start:
                on_stage_start(name, script)
            ok = script != self.fail_at
            result = self.Result(name, script, ok, 0 if ok else 2, "" if ok else "boom")
            results.append(result)
            self.ran.append(script)
            if on_stage_end:
                on_stage_end(result)
            if not ok:
                return False, results
        return True, results


def build(tmp, scanner=None, pipeline=None):
    return ScanService(
        registry=ScannerRegistry([scanner or FakeScanner()]),
        data_dir=Path(tmp),
        pipeline_runner=pipeline or FakePipeline(),
        stage_list=FakePipeline.STAGES,
    )


def stage(state, key):
    return next(item for item in state["stages"] if item["key"] == key)


def test_a_successful_scan_runs_every_stage_and_writes_the_cbom_and_record():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FakeScanner()
        pipeline = FakePipeline()
        service = build(tmp, scanner, pipeline)

        state = service.run_sync("https://github.com/keycloak/keycloak.git", "main")

        assert state["status"] == "completed", state
        assert state["repository"] == "https://github.com/keycloak/keycloak"
        assert scanner.scanned == [("https://github.com/keycloak/keycloak", "main")]
        assert pipeline.ran == ["cbom_parser.py", "classify_cbom.py"]

        for key in ("target", "scanner", "availability", "scan", "validation", "pipeline", "publish"):
            assert stage(state, key)["status"] == "done", key
        assert all(item["status"] == "done" for item in state["pipeline_stages"])

        assert state["result"]["crypto_components"] == 1
        assert state["result"]["findings"] == 1
        assert state["validation"]["ok"] is True
        assert state["duration_seconds"] is not None

        # The CBOM lands on the path the existing pipeline already reads.
        written = json.loads((Path(tmp) / "keycloak-cbom.json").read_text(encoding="utf-8"))
        assert written == scanner.cbom

        record = json.loads((Path(tmp) / "ecdat-scan.json").read_text(encoding="utf-8"))
        assert record["status"] == "completed"
        assert record["target"]["slug"] == "keycloak/keycloak"

        history = json.loads((Path(tmp) / "ecdat-scan-history.json").read_text(encoding="utf-8"))["scans"]
        assert len(history) == 1 and history[0]["scan_id"] == state["scan_id"]


def test_an_invalid_target_never_starts_a_scan():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FakeScanner()
        service = build(tmp, scanner)

        try:
            service.start("https://gitlab.com/owner/repo", "main")
        except TargetError as error:
            assert error.code == "unsupported-host"
        else:
            raise AssertionError("an unsupported host should be rejected")

        assert scanner.scanned == []
        assert service.snapshot()["status"] == "idle"


def test_an_unavailable_scanner_fails_before_scanning():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FakeScanner(available=False)
        service = build(tmp, scanner)

        state = service.run_sync("https://github.com/o/r", "main")

        assert state["status"] == "failed"
        assert state["error_code"] == "scanner-unavailable"
        assert stage(state, "availability")["status"] == "failed"
        assert stage(state, "scan")["status"] == "pending"
        assert scanner.scanned == []
        assert not (Path(tmp) / "keycloak-cbom.json").exists()


def test_a_scanner_error_is_reported_with_its_code():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FakeScanner(error=ScannerError("cbomkit-timeout", "CBOMKit did not finish"))
        service = build(tmp, scanner)

        state = service.run_sync("https://github.com/o/r", "main")

        assert state["status"] == "failed"
        assert state["error_code"] == "cbomkit-timeout"
        assert "CBOMKit did not finish" in state["error"]


def test_an_invalid_cbom_stops_before_the_pipeline_runs():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FakeScanner(cbom={"bomFormat": "CycloneDX", "specVersion": "1.6", "components": []})
        pipeline = FakePipeline()
        service = build(tmp, scanner, pipeline)

        state = service.run_sync("https://github.com/o/r", "main")

        assert state["status"] == "failed"
        assert state["error_code"] == "no-crypto-components"
        assert pipeline.ran == []
        assert not (Path(tmp) / "keycloak-cbom.json").exists()


def test_a_failing_pipeline_stage_is_named_in_the_status():
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = FakePipeline(fail_at="classify_cbom.py")
        service = build(tmp, pipeline=pipeline)

        state = service.run_sync("https://github.com/o/r", "main")

        assert state["status"] == "failed"
        assert state["error_code"] == "pipeline-stage-failed"
        assert "Classification" in state["error"]
        stages = {item["key"]: item["status"] for item in state["pipeline_stages"]}
        assert stages["cbom_parser.py"] == "done"
        assert stages["classify_cbom.py"] == "failed"


def test_history_keeps_the_most_recent_scans_first():
    with tempfile.TemporaryDirectory() as tmp:
        service = build(tmp)

        first = service.run_sync("https://github.com/o/one", "main")["scan_id"]
        second = service.run_sync("https://github.com/o/two", "main")["scan_id"]

        history = service.history()
        assert [entry["scan_id"] for entry in history[:2]] == [second, first]
        assert history[0]["target"]["slug"] == "o/two"


def test_capabilities_come_from_the_registry():
    with tempfile.TemporaryDirectory() as tmp:
        capabilities = build(tmp).capabilities()
        assert capabilities["supported_targets"][0]["kind"] == GIT_REPOSITORY
        assert [entry["kind"] for entry in capabilities["planned_targets"]] == ["binary", "library", "container"]


if __name__ == "__main__":
    test_a_successful_scan_runs_every_stage_and_writes_the_cbom_and_record()
    test_an_invalid_target_never_starts_a_scan()
    test_an_unavailable_scanner_fails_before_scanning()
    test_a_scanner_error_is_reported_with_its_code()
    test_an_invalid_cbom_stops_before_the_pipeline_runs()
    test_a_failing_pipeline_stage_is_named_in_the_status()
    test_history_keeps_the_most_recent_scans_first()
    test_capabilities_come_from_the_registry()
    print("All scan service tests passed.")

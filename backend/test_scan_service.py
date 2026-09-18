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


def test_a_second_scan_is_refused_while_one_is_running():
    """The single scan slot: two callers must never both own data/."""
    import threading

    with tempfile.TemporaryDirectory() as tmp:
        release = threading.Event()

        class BlockingScanner(FakeScanner):
            def scan(self, target, progress=None):
                release.wait(5)
                return super().scan(target, progress)

        service = build(tmp, BlockingScanner())
        worker = threading.Thread(target=lambda: service.run_sync("https://github.com/o/one", "main"))
        worker.start()
        try:
            while not service.is_running():
                pass

            refused = None
            try:
                service.start("https://github.com/o/two", "main")
            except RuntimeError as error:
                refused = str(error)
            assert refused and "already running" in refused, refused

            # The CLI path takes the same slot, so it is refused too.
            try:
                service.run_sync("https://github.com/o/three", "main")
            except RuntimeError as error:
                refused = str(error)
            assert "already running" in refused, refused
        finally:
            release.set()
            worker.join(10)

        assert service.snapshot()["status"] == "completed"
        # The slot is free again once the scan ends.
        assert service.run_sync("https://github.com/o/four", "main")["status"] == "completed"


def test_the_dataset_lock_is_released_even_when_a_scan_fails():
    from services.scanning.service import LOCK_FILENAME

    with tempfile.TemporaryDirectory() as tmp:
        service = build(tmp, FakeScanner(available=False))
        assert service.run_sync("https://github.com/o/one", "main")["status"] == "failed"
        assert not (Path(tmp) / LOCK_FILENAME).exists(), "a failed scan left the dataset locked"

        # And a later scan can still run.
        service = build(tmp)
        assert service.run_sync("https://github.com/o/one", "main")["status"] == "completed"


def test_a_lock_held_by_a_live_process_blocks_a_second_process():
    import json as _json
    import os as _os

    from services.scanning.service import LOCK_FILENAME

    with tempfile.TemporaryDirectory() as tmp:
        # A lock file naming this (running) process stands in for another
        # ECDAT process mid-scan.
        (Path(tmp) / LOCK_FILENAME).write_text(
            _json.dumps({"pid": _os.getpid(), "scan_id": "other", "started_at": "now"}), encoding="utf-8"
        )
        service = build(tmp)
        try:
            service.run_sync("https://github.com/o/one", "main")
        except RuntimeError as error:
            assert "another ECDAT process" in str(error), error
        else:
            raise AssertionError("a live lock holder must block a new scan")


def test_a_lock_left_by_a_dead_process_is_taken_over():
    import json as _json

    from services.scanning.service import LOCK_FILENAME

    with tempfile.TemporaryDirectory() as tmp:
        # PID 0 is never a live process ECDAT could be running as.
        (Path(tmp) / LOCK_FILENAME).write_text(
            _json.dumps({"pid": 0, "scan_id": "dead", "started_at": "then"}), encoding="utf-8"
        )
        service = build(tmp)
        assert service.run_sync("https://github.com/o/one", "main")["status"] == "completed"


def test_a_pipeline_stage_timeout_is_reported_as_its_own_failure():
    class TimingOutPipeline(FakePipeline):
        def __call__(self, on_stage_start=None, on_stage_end=None):
            name, script = self.STAGES[0]
            if on_stage_start:
                on_stage_start(name, script)
            result = self.Result(name, script, False, -1, "")
            result.timed_out = True
            if on_stage_end:
                on_stage_end(result)
            return False, [result]

    with tempfile.TemporaryDirectory() as tmp:
        state = build(tmp, pipeline=TimingOutPipeline()).run_sync("https://github.com/o/one", "main")

        assert state["status"] == "failed"
        assert state["error_code"] == "pipeline-stage-timeout", state["error_code"]
        assert "did not finish in time" in state["error"]
        assert stage(state, "pipeline")["status"] == "failed"


def test_a_scan_record_left_running_by_a_dead_process_is_closed_out():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "ecdat-scan.json").write_text(
            json.dumps({"scan_id": "abc", "status": "running", "started_at": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        (Path(tmp) / "ecdat-scan-history.json").write_text(
            json.dumps({"scans": [{"scan_id": "abc", "status": "running"}]}), encoding="utf-8"
        )

        service = build(tmp)  # construction reconciles the stale record

        record = json.loads((Path(tmp) / "ecdat-scan.json").read_text(encoding="utf-8"))
        assert record["status"] == "interrupted"
        assert record["error_code"] == "scan-interrupted"
        assert record["finished_at"]
        assert service.history()[0]["status"] == "interrupted"
        # A completed record is left exactly as it was.
        service2 = build(tmp)
        assert json.loads((Path(tmp) / "ecdat-scan.json").read_text(encoding="utf-8"))["status"] == "interrupted"
        assert service2.snapshot()["status"] == "idle"


def test_writes_are_atomic_and_leave_no_temp_files_behind():
    with tempfile.TemporaryDirectory() as tmp:
        service = build(tmp)
        service.run_sync("https://github.com/o/one", "main")

        leftovers = [path.name for path in Path(tmp).iterdir() if path.name.startswith(".") and path.suffix == ".tmp"]
        assert not leftovers, leftovers
        # The CBOM is complete, parseable JSON.
        cbom = json.loads((Path(tmp) / "keycloak-cbom.json").read_text(encoding="utf-8"))
        assert cbom["components"][0]["bom-ref"] == "finding-1"


def test_a_cached_cbom_is_described_as_cached_in_the_completion_message():
    class CachedScanner(FakeScanner):
        def scan(self, target, progress=None):
            artifact = super().scan(target, progress)
            artifact.source.update(
                {"freshness": "cbomkit-cached", "cbom_created_at": "2026-08-30T13:58:40+00:00"}
            )
            return artifact

    with tempfile.TemporaryDirectory() as tmp:
        state = build(tmp, CachedScanner()).run_sync("https://github.com/o/one", "main")

        assert state["status"] == "completed"
        assert "already held" in state["message"], state["message"]
        assert state["result"]["source"]["freshness"] == "cbomkit-cached"


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
    test_a_second_scan_is_refused_while_one_is_running()
    test_the_dataset_lock_is_released_even_when_a_scan_fails()
    test_a_lock_held_by_a_live_process_blocks_a_second_process()
    test_a_lock_left_by_a_dead_process_is_taken_over()
    test_a_pipeline_stage_timeout_is_reported_as_its_own_failure()
    test_a_scan_record_left_running_by_a_dead_process_is_closed_out()
    test_writes_are_atomic_and_leave_no_temp_files_behind()
    test_a_cached_cbom_is_described_as_cached_in_the_completion_message()
    test_capabilities_come_from_the_registry()
    print("All scan service tests passed.")

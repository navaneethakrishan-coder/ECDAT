"""The ECDAT scan lifecycle.

One scan, start to finish:

    target validation
      → scanner selection
        → scanner availability
          → repository scan (CBOMKit)
            → CBOM validation + normalization
              → the existing 13-stage ECDAT pipeline
                → scan record published

Every stage reported to the API is a stage that really ran: the status
carries the actual stage the scan is in, the real pipeline stage names, the
real validation result and the real counts from the produced CBOM.
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .base import ScannerError
from .pipeline import pipeline_stages, run_pipeline
from .registry import ScannerRegistry
from .targets import TargetError, parse_repository_target
from .validation import normalize_cbom, validate_cbom

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR.parent / "data"

# The filename the pipeline already reads (cbom_parser.py, evidence_explorer).
# Kept as-is so no analysis module has to change.
CBOM_FILENAME = "keycloak-cbom.json"
SCAN_RECORD_FILENAME = "ecdat-scan.json"
SCAN_HISTORY_FILENAME = "ecdat-scan-history.json"
HISTORY_LIMIT = 20

# Cross-process guard: the API server and the CLI are different processes
# writing the same data/ directory, so the in-process lock is not enough.
LOCK_FILENAME = ".ecdat-scan.lock"


def _process_alive(pid: int) -> bool:
    """Whether a process is still running, without signalling it.

    os.kill(pid, 0) terminates the target on Windows, so that is never used
    here; each platform gets the check that only observes.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False

    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

STAGE_DEFINITIONS = [
    ("target", "Validate repository target"),
    ("scanner", "Select scanner"),
    ("availability", "Check scanner availability"),
    ("scan", "Scan repository (CBOMKit)"),
    ("validation", "Validate & normalize CBOM"),
    ("pipeline", "ECDAT analysis pipeline"),
    ("publish", "Publish scan results"),
]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ScanService:
    """Owns scan state. One scan at a time; thread-safe snapshots."""

    def __init__(
        self,
        registry: ScannerRegistry = None,
        data_dir: Path = DATA_DIR,
        pipeline_runner=run_pipeline,
        stage_list=None,
    ):
        self.registry = registry or ScannerRegistry()
        self.data_dir = Path(data_dir)
        self.pipeline_runner = pipeline_runner
        # The pipeline's own stage list (name, script), so the reported
        # stages are exactly the stages that will run.
        self.stage_list = list(stage_list) if stage_list is not None else pipeline_stages()
        self._lock = threading.RLock()
        self._state = self._idle_state()
        self._thread = None
        self._reconcile_persisted_record()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _idle_state(self):
        return {
            "status": "idle",
            "scan_id": None,
            "repository": None,
            "branch": None,
            "message": "No scan has been started.",
            "error": None,
            "error_code": None,
            "target": None,
            "scanner": None,
            "stages": [
                {"key": key, "label": label, "status": "pending", "detail": None, "started_at": None, "finished_at": None}
                for key, label in STAGE_DEFINITIONS
            ],
            "pipeline_stages": [
                {"key": script, "label": name, "status": "pending"} for name, script in self.stage_list
            ],
            "current_stage": None,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "validation": None,
            "result": None,
        }

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self._state))

    def is_running(self):
        with self._lock:
            return self._state["status"] in {"starting", "running"}

    def _update(self, **fields):
        with self._lock:
            self._state.update(fields)

    def _stage(self, key, status, detail=None):
        with self._lock:
            for stage in self._state["stages"]:
                if stage["key"] != key:
                    continue
                stage["status"] = status
                if detail is not None:
                    stage["detail"] = detail
                if status == "running" and not stage["started_at"]:
                    stage["started_at"] = _now()
                if status in {"done", "failed", "skipped"}:
                    stage["finished_at"] = _now()
                if status == "running":
                    self._state["current_stage"] = stage["label"]
            return

    def _stage_detail(self, key, detail):
        with self._lock:
            for stage in self._state["stages"]:
                if stage["key"] == key:
                    stage["detail"] = detail

    def _pipeline_stage(self, script, status):
        with self._lock:
            for stage in self._state["pipeline_stages"]:
                if stage["key"] == script:
                    stage["status"] = status
                    if status == "running":
                        self._state["current_stage"] = f"Pipeline: {stage['label']}"

    def _fail(self, code, message, stage_key=None):
        if stage_key:
            self._stage(stage_key, "failed", message)
        with self._lock:
            started = self._state.get("started_at")
            self._state.update(
                {
                    "status": "failed",
                    "message": message,
                    "error": message,
                    "error_code": code,
                    "finished_at": _now(),
                    "duration_seconds": self._elapsed(started),
                }
            )
        self._write_record()

    def _elapsed(self, started_at):
        if not started_at:
            return None
        try:
            started = datetime.fromisoformat(started_at)
        except ValueError:
            return None
        return round((datetime.now(timezone.utc) - started).total_seconds(), 1)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _write_json(self, filename, payload):
        """Writes JSON atomically: a crash mid-write cannot truncate the file.

        The bytes are identical to a direct write -- only the way they reach
        the file changes (temp file in the same directory, then os.replace,
        which is atomic on Windows and POSIX alike).
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        return path

    def _reconcile_persisted_record(self):
        """Closes out a scan the previous process died in the middle of.

        The in-memory state starts idle, so a record still saying "running"
        would outlive its scan and be reported by the history endpoint
        forever. Nothing can resume that scan, so it is recorded as
        interrupted -- never as completed, and never silently dropped.
        """
        path = self.data_dir / SCAN_RECORD_FILENAME
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as file:
                record = json.load(file)
        except (json.JSONDecodeError, OSError):
            return

        if record.get("status") not in {"starting", "running"}:
            return

        record.update(
            {
                "status": "interrupted",
                "error": "The backend stopped while this scan was running; its result is unknown.",
                "error_code": "scan-interrupted",
                "finished_at": _now(),
            }
        )

        try:
            self._write_json(SCAN_RECORD_FILENAME, record)
            history = self.history()
            for entry in history:
                if entry.get("scan_id") == record.get("scan_id"):
                    entry.update(
                        {
                            "status": record["status"],
                            "error": record["error"],
                            "error_code": record["error_code"],
                            "finished_at": record["finished_at"],
                        }
                    )
            self._write_json(SCAN_HISTORY_FILENAME, {"scans": history[:HISTORY_LIMIT]})
        except OSError:
            # A read-only data directory must not stop the API from starting.
            pass

    def _write_record(self):
        state = self.snapshot()
        record = {
            "scan_id": state["scan_id"],
            "status": state["status"],
            "target": state["target"],
            "scanner": state["scanner"],
            "started_at": state["started_at"],
            "finished_at": state["finished_at"],
            "duration_seconds": state["duration_seconds"],
            "validation": state["validation"],
            "result": state["result"],
            "error": state["error"],
            "error_code": state["error_code"],
        }
        self._write_json(SCAN_RECORD_FILENAME, record)

        history = self.history()
        history = [entry for entry in history if entry.get("scan_id") != record["scan_id"]]
        history.insert(0, record)
        self._write_json(SCAN_HISTORY_FILENAME, {"scans": history[:HISTORY_LIMIT]})

    def history(self):
        path = self.data_dir / SCAN_HISTORY_FILENAME
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file).get("scans", [])
        except (json.JSONDecodeError, OSError):
            return []

    def capabilities(self):
        return self.registry.capabilities()

    # ------------------------------------------------------------------
    # Running a scan
    # ------------------------------------------------------------------

    def start(self, repository: str, branch: str = "main"):
        """Validates the target and starts a scan in the background.

        Raises TargetError for an unusable target and RuntimeError if a scan
        is already running, so the API can answer 400/409 truthfully.
        """
        target = parse_repository_target(repository, branch)
        self._claim(target)

        self._thread = threading.Thread(target=self._run, args=(target,), daemon=True)
        self._thread.start()
        return self.snapshot()

    def _acquire_dataset_lock(self, scan_id):
        """Claims data/ for this scan across processes, or raises RuntimeError."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / LOCK_FILENAME
        payload = json.dumps({"pid": os.getpid(), "scan_id": scan_id, "started_at": _now()})

        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = {}
            try:
                holder = json.loads(path.read_text(encoding="utf-8") or "{}")
            except (json.JSONDecodeError, OSError):
                holder = {}

            if _process_alive(holder.get("pid")):
                raise RuntimeError(
                    "A scan is already running in another ECDAT process "
                    f"(pid {holder.get('pid')}, started {holder.get('started_at')})."
                )
            # The process that held the lock is gone, so its scan cannot
            # still be writing; take the lock over rather than blocking
            # every future scan.
            path.unlink(missing_ok=True)
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(payload)

    def _release_dataset_lock(self):
        try:
            (self.data_dir / LOCK_FILENAME).unlink(missing_ok=True)
        except OSError:
            pass

    def _claim(self, target):
        """Takes the single scan slot, or refuses.

        The check and the state transition happen under one lock hold, so two
        callers -- two API requests, or an API request and the CLI -- can
        never both believe they own the scan and run two pipelines over the
        same dataset.
        """
        with self._lock:
            if self._state["status"] in {"starting", "running"}:
                raise RuntimeError("A scan is already running.")

            scan_id = uuid.uuid4().hex[:12]
            # Raises RuntimeError if another process owns data/; the state is
            # untouched in that case, so this scan never half-starts.
            self._acquire_dataset_lock(scan_id)

            self._state = self._idle_state()
            self._state.update(
                {
                    "status": "starting",
                    "scan_id": scan_id,
                    "repository": target.url,
                    "branch": target.branch,
                    "target": target.describe(),
                    "message": f"Starting scan of {target.slug} ({target.branch}).",
                    "started_at": _now(),
                }
            )
        self._stage("target", "done", f"{target.slug} on branch {target.branch}.")

    def run_sync(self, repository: str, branch: str = "main"):
        """Same scan, run in the caller's thread (used by the CLI).

        Takes the same single scan slot as start(), so a CLI scan cannot
        overlap an API scan writing the same dataset.
        """
        target = parse_repository_target(repository, branch)
        self._claim(target)
        self._run(target)
        return self.snapshot()

    def _run(self, target):
        try:
            self._run_stages(target)
        except Exception as error:  # the scan slot must never leak on a crash
            self._fail("scan-crashed", f"The scan failed unexpectedly: {error}")
        finally:
            self._release_dataset_lock()

    def _run_stages(self, target):
        self._update(status="running", message=f"Scanning {target.slug} ({target.branch}).")

        # ---- scanner selection
        self._stage("scanner", "running")
        scanner = self.registry.for_target(target)
        if scanner is None:
            self._fail("no-scanner", f"No scanner is implemented for '{target.kind}' targets.", "scanner")
            return
        self._update(scanner=scanner.describe())
        self._stage("scanner", "done", f"{scanner.title}.")

        # ---- availability
        self._stage("availability", "running")
        availability = scanner.check_availability()
        if not availability.available:
            self._fail("scanner-unavailable", availability.detail, "availability")
            return
        self._stage("availability", "done", availability.detail)

        # ---- scan
        self._stage("scan", "running", f"Waiting for {scanner.title}…")
        started = time.monotonic()
        try:
            artifact = scanner.scan(target, progress=lambda message: self._stage_detail("scan", message))
        except ScannerError as error:
            self._fail(error.code, error.message, "scan")
            return
        except Exception as error:  # a scanner crash must not look like a clean failure
            self._fail("scanner-crashed", f"{scanner.title} failed: {error}", "scan")
            return
        self._stage("scan", "done", f"CBOM received in {round(time.monotonic() - started, 1)}s.")

        # ---- validation + normalization
        self._stage("validation", "running")
        report = validate_cbom(artifact.cbom)
        with self._lock:
            self._state["validation"] = report
        if not report["ok"]:
            first = report["errors"][0]
            self._fail(first["code"], f"CBOM validation failed: {first['message']}", "validation")
            return

        normalized, notes = normalize_cbom(artifact.cbom)
        stats = report["stats"]
        detail = (
            f"{stats['findings']} cryptographic finding(s) from {stats['crypto_components']} "
            f"component entr(y/ies) of {stats['components']}, "
            f"{stats['dependency_edges']} recorded dependency edge(s)."
        )
        if notes:
            detail += " " + " ".join(notes)
        if report["warnings"]:
            detail += f" {len(report['warnings'])} warning(s)."
        self._stage("validation", "done", detail)

        try:
            cbom_path = self._write_json(CBOM_FILENAME, normalized)
        except OSError as error:
            self._fail("cbom-write-failed", f"Could not write the CBOM: {error}", "validation")
            return

        # ---- ECDAT pipeline (unchanged stages)
        self._stage("pipeline", "running", "Running the ECDAT analysis pipeline…")
        ok, results = self.pipeline_runner(
            on_stage_start=lambda name, script: self._pipeline_stage(script, "running"),
            on_stage_end=lambda result: self._pipeline_stage(result.script, "done" if result.ok else "failed"),
        )
        if not ok:
            failed = results[-1]
            if getattr(failed, "timed_out", False):
                self._fail(
                    "pipeline-stage-timeout",
                    (
                        f"Pipeline stage '{failed.name}' did not finish in time and was stopped. "
                        f"{failed.output_tail}"
                    ).strip(),
                    "pipeline",
                )
                return
            self._fail(
                "pipeline-stage-failed",
                f"Pipeline stage '{failed.name}' failed (exit {failed.returncode}). {failed.output_tail}".strip(),
                "pipeline",
            )
            return
        self._stage("pipeline", "done", f"{len(results)} stage(s) completed.")

        # ---- publish
        self._stage("publish", "running")
        result = {
            "cbom_path": str(cbom_path.name),
            "source": artifact.source,
            "components": stats["components"],
            "crypto_components": stats["crypto_components"],
            "findings": stats["findings"],
            "dependency_edges": stats["dependency_edges"],
            "asset_types": stats["asset_types"],
        }
        # A CBOM the scanner reports as cached is described as cached here
        # too, so a completed scan never implies a freshly scanned commit
        # that did not happen.
        cached = (artifact.source or {}).get("freshness") == "cbomkit-cached"
        message = (
            f"Scanned {target.slug} ({target.branch}): "
            f"{stats['findings']} cryptographic finding(s) analysed."
        )
        if cached:
            scanned_at = (artifact.source or {}).get("cbom_created_at")
            message = (
                f"Analysed {target.slug} ({target.branch}) from the CBOM CBOMKit already held"
                + (f", scanned {scanned_at}" if scanned_at else "")
                + f": {stats['findings']} cryptographic finding(s)."
            )

        with self._lock:
            started_at = self._state["started_at"]
            self._state.update(
                {
                    "status": "completed",
                    "result": result,
                    "message": message,
                    "error": None,
                    "error_code": None,
                    "current_stage": None,
                    "finished_at": _now(),
                    "duration_seconds": self._elapsed(started_at),
                }
            )
        self._stage("publish", "done", "Scan record written.")
        self._write_record()

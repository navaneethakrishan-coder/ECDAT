"""Runs the existing 13-stage ECDAT analysis pipeline, stage by stage.

The stage list is imported from run_pipeline.py so there is exactly one
definition of the pipeline. Nothing about what those stages compute changes
here -- this only runs them in order and reports which one is running.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from run_pipeline import PIPELINE

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class StageResult:
    name: str
    script: str
    ok: bool
    returncode: int
    output_tail: str = ""


def pipeline_stages():
    """The pipeline's stages, in order: [(name, script), ...]."""
    return list(PIPELINE)


def run_pipeline(
    on_stage_start: Optional[Callable[[str, str], None]] = None,
    on_stage_end: Optional[Callable[[StageResult], None]] = None,
    backend_dir: Path = BACKEND_DIR,
    python_executable: str = None,
):
    """Runs every pipeline stage; stops at the first failure.

    Returns (ok, results). A failing stage carries the tail of its output so
    the API can show the real error instead of a generic message.
    """
    results = []
    python_executable = python_executable or sys.executable

    for name, script in pipeline_stages():
        if on_stage_start:
            on_stage_start(name, script)

        script_path = Path(backend_dir) / script
        if not script_path.exists():
            result = StageResult(name, script, False, -1, f"Pipeline script not found: {script_path}")
        else:
            completed = subprocess.run(
                [python_executable, str(script_path)],
                cwd=str(backend_dir),
                capture_output=True,
                text=True,
            )
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-12:]
            result = StageResult(
                name,
                script,
                completed.returncode == 0,
                completed.returncode,
                "\n".join(tail),
            )

        results.append(result)
        if on_stage_end:
            on_stage_end(result)

        if not result.ok:
            return False, results

    return True, results

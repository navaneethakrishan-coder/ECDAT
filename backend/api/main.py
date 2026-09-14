"""
DEPRECATED ENTRY POINT.

This module used to contain a second, independently-maintained FastAPI
application that had drifted from backend/main.py: it was missing the
repository-analysis endpoints (`/api/analyze`, `/api/analyze/status`)
while backend/main.py was missing the `/api/ai/advice` contract the
frontend actually calls. Neither file, run alone, could serve the full
dashboard. See docs/ARCHITECTURE.md ("Known inconsistency: two
divergent FastAPI apps") and docs/CHANGELOG.md (2026-09-14 entry) for
the full history.

backend/main.py is now the single canonical FastAPI application and
contains every route (including /api/ai/advice). This module is kept
only so that `uvicorn api.main:app` does not hard-fail for anyone still
pointing at it -- it simply re-exports the canonical `app` object, so
both entry points serve identical, non-divergent behavior.

Prefer running the backend as:
    uvicorn main:app --reload
from inside the backend/ directory.
"""

import sys
from pathlib import Path

# backend/ (the parent of this api/ package) must be on sys.path for
# `from main import app` to resolve, regardless of the working
# directory this module happens to be imported/run from.
_BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from main import app  # noqa: E402  (import after sys.path fix-up, by design)

__all__ = ["app"]

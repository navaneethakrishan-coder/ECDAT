"""ECDAT scanning: targets, scanners, CBOM validation and the scan lifecycle.

    GitHub repository → ECDAT scan → CBOMKit → CBOM validation/normalization
      → the existing ECDAT pipeline → the 3D security space

Adding a binary / library / container scanner later means implementing
services.scanning.base.Scanner and registering it; nothing downstream
changes. Target kinds without a scanner are declared in registry.py as
not implemented and are never presented as coverage.
"""

from .base import Availability, ScanArtifact, Scanner, ScannerError
from .cbomkit import CBOMKitClient, CBOMKitRepositoryScanner
from .registry import PLANNED_TARGETS, ScannerRegistry
from .service import ScanService
from .targets import GIT_REPOSITORY, ScanTarget, TargetError, parse_repository_target
from .validation import normalize_cbom, validate_cbom

__all__ = [
    "Availability",
    "CBOMKitClient",
    "CBOMKitRepositoryScanner",
    "GIT_REPOSITORY",
    "PLANNED_TARGETS",
    "ScanArtifact",
    "ScanService",
    "ScanTarget",
    "Scanner",
    "ScannerError",
    "ScannerRegistry",
    "TargetError",
    "normalize_cbom",
    "parse_repository_target",
    "validate_cbom",
]

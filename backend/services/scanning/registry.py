"""Which scanners ECDAT actually has, and which target kinds it does not.

`PLANNED_TARGETS` exists so the product can state plainly what is *not*
implemented. Nothing in it is ever selectable or reported as coverage.
"""

from .base import Scanner
from .cbomkit import CBOMKitRepositoryScanner
from .targets import GIT_REPOSITORY


# Target kinds the architecture is ready for but no scanner implements yet.
PLANNED_TARGETS = [
    {
        "kind": "binary",
        "title": "Compiled binaries",
        "status": "not-implemented",
        "detail": "No binary scanner is implemented. ECDAT cannot report cryptography inside compiled artifacts.",
    },
    {
        "kind": "library",
        "title": "Dependency / library inventories",
        "status": "not-implemented",
        "detail": "No library scanner is implemented. Third-party dependency cryptography is not analysed.",
    },
    {
        "kind": "container",
        "title": "Container images",
        "status": "not-implemented",
        "detail": "No container scanner is implemented. Image layers are not scanned.",
    },
]


class ScannerRegistry:
    """Holds the scanners this deployment can run."""

    def __init__(self, scanners=None):
        self.scanners = list(scanners) if scanners is not None else [CBOMKitRepositoryScanner()]

    def add(self, scanner: Scanner):
        self.scanners.append(scanner)

    def for_target(self, target):
        for scanner in self.scanners:
            if scanner.supports(target):
                return scanner
        return None

    def capabilities(self) -> dict:
        supported = []
        for scanner in self.scanners:
            availability = scanner.check_availability()
            supported.append(
                {
                    **scanner.describe(),
                    "status": "available" if availability.available else "unavailable",
                    "available": availability.available,
                    "detail": availability.detail,
                }
            )

        return {
            "supported_targets": [
                {
                    "kind": GIT_REPOSITORY,
                    "title": "Public GitHub repository (source scan)",
                    "scanners": [entry for entry in supported if entry["target_kind"] == GIT_REPOSITORY],
                }
            ],
            "planned_targets": PLANNED_TARGETS,
        }

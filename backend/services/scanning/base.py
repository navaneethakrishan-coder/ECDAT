"""The scanner interface every ECDAT scanner implements.

A scanner turns a ScanTarget into a CycloneDX CBOM. Everything after that
(validation, the ECDAT analysis pipeline) is shared, so adding a binary,
library or container scanner later means implementing this one interface --
no change to the pipeline, the API or the UI contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional


# Progress callback: stage detail text from inside a scanner.
ProgressCallback = Callable[[str], None]


class ScannerError(Exception):
    """A scanner failure with a machine-readable reason code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Availability:
    available: bool
    detail: str


@dataclass
class ScanArtifact:
    """What a scanner returns: a CBOM plus how it was obtained."""

    cbom: dict
    source: dict = field(default_factory=dict)


class Scanner(ABC):
    """Base class for ECDAT scanners."""

    key: str = ""
    title: str = ""
    target_kind: str = ""
    # Human-readable prerequisite, e.g. "CBOMKit running on http://localhost:8081".
    requires: str = ""

    def supports(self, target) -> bool:
        return getattr(target, "kind", None) == self.target_kind

    @abstractmethod
    def check_availability(self) -> Availability:
        """Whether this scanner can run right now (service reachable, etc.)."""

    @abstractmethod
    def scan(self, target, progress: Optional[ProgressCallback] = None) -> ScanArtifact:
        """Runs the scan and returns the CBOM it produced.

        Must raise ScannerError on failure; must never synthesise findings.
        """

    def describe(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "target_kind": self.target_kind,
            "requires": self.requires,
        }

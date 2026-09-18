"""Scan target parsing, scanner selection and capability reporting."""

from services.scanning.base import Availability, ScanArtifact, Scanner, ScannerError
from services.scanning.registry import PLANNED_TARGETS, ScannerRegistry
from services.scanning.targets import GIT_REPOSITORY, TargetError, parse_repository_target


class FakeScanner(Scanner):
    key = "fake"
    title = "Fake scanner"
    target_kind = GIT_REPOSITORY
    requires = "nothing"

    def __init__(self, available=True):
        self.available = available

    def check_availability(self):
        return Availability(self.available, "fake availability")

    def scan(self, target, progress=None):
        return ScanArtifact(cbom={}, source={})


def test_accepts_the_github_url_forms_a_user_actually_pastes():
    for url in (
        "https://github.com/keycloak/keycloak",
        "https://github.com/keycloak/keycloak/",
        "https://github.com/keycloak/keycloak.git",
        "http://github.com/keycloak/keycloak",
        "https://www.github.com/keycloak/keycloak",
        "git@github.com:keycloak/keycloak.git",
    ):
        target = parse_repository_target(url, "main")
        assert target.kind == GIT_REPOSITORY, url
        assert target.url == "https://github.com/keycloak/keycloak", url
        assert target.slug == "keycloak/keycloak", url
        assert target.original_url == url, url


def test_rejects_unusable_targets_with_a_reason_code():
    cases = {
        "": "empty-url",
        "   ": "empty-url",
        "https://gitlab.com/owner/repo": "unsupported-host",
        "https://github.com/onlyowner": "malformed-url",
        # No github.com anywhere: an unsupported target, not a typo.
        "not a url": "unsupported-host",
        "https://github.com/owner/repo extra": "malformed-url",
        "ftp://example.com/owner/repo": "unsupported-host",
        "https://github.com/": "malformed-url",
    }
    for url, code in cases.items():
        try:
            parse_repository_target(url, "main")
        except TargetError as error:
            assert error.code == code, f"{url}: {error.code} != {code}"
        else:
            raise AssertionError(f"{url!r} should have been rejected")


def test_branch_defaults_and_validation():
    assert parse_repository_target("https://github.com/o/r", "").branch == "main"
    assert parse_repository_target("https://github.com/o/r", "release/24.0").branch == "release/24.0"

    for branch in ("bad branch", "..", "/leading", "a" * 256):
        try:
            parse_repository_target("https://github.com/o/r", branch)
        except TargetError as error:
            assert error.code == "invalid-branch", branch
        else:
            raise AssertionError(f"branch {branch!r} should have been rejected")


def test_registry_selects_a_scanner_for_the_target_kind():
    scanner = FakeScanner()
    registry = ScannerRegistry([scanner])
    target = parse_repository_target("https://github.com/o/r", "main")

    assert registry.for_target(target) is scanner

    class OtherTarget:
        kind = "container"

    assert registry.for_target(OtherTarget()) is None


def test_capabilities_report_unavailable_scanners_and_never_claim_planned_coverage():
    registry = ScannerRegistry([FakeScanner(available=False)])
    capabilities = registry.capabilities()

    repository = capabilities["supported_targets"][0]
    assert repository["kind"] == GIT_REPOSITORY
    assert repository["scanners"][0]["available"] is False
    assert repository["scanners"][0]["status"] == "unavailable"

    planned_kinds = {entry["kind"] for entry in capabilities["planned_targets"]}
    assert planned_kinds == {"binary", "library", "container"}
    for entry in capabilities["planned_targets"]:
        assert entry["status"] == "not-implemented", entry
    assert PLANNED_TARGETS is capabilities["planned_targets"]


def test_scanner_errors_carry_codes():
    error = ScannerError("cbomkit-timeout", "timed out")
    assert error.code == "cbomkit-timeout"
    assert str(error) == "timed out"


if __name__ == "__main__":
    test_accepts_the_github_url_forms_a_user_actually_pastes()
    test_rejects_unusable_targets_with_a_reason_code()
    test_branch_defaults_and_validation()
    test_registry_selects_a_scanner_for_the_target_kind()
    test_capabilities_report_unavailable_scanners_and_never_claim_planned_coverage()
    test_scanner_errors_carry_codes()
    print("All scan target tests passed.")

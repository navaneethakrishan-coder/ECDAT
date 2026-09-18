"""Scan targets: what ECDAT can be pointed at, and how a target is parsed.

Only what a scanner genuinely supports is described here. Today that is a
public GitHub repository; other target kinds are declared as planned in
registry.py so the product never implies coverage it does not have.
"""

from dataclasses import dataclass
import re


GIT_REPOSITORY = "git-repository"

# Branch names: git's own rules, narrowed to what a URL/CLI round-trip can
# carry safely. No spaces, no "..", no leading/trailing slash or dot.
BRANCH_PATTERN = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9._\-/]{1,255}$")

HTTPS_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*?)(?:\.git)?/?$",
    re.IGNORECASE,
)
SSH_PATTERN = re.compile(
    r"^git@github\.com:(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*?)(?:\.git)?/?$",
    re.IGNORECASE,
)


class TargetError(ValueError):
    """A scan target that ECDAT cannot accept, with a machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ScanTarget:
    kind: str
    url: str          # canonical https URL, no .git suffix
    branch: str
    owner: str
    repository: str
    original_url: str  # exactly what the user typed

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repository}"

    def describe(self) -> dict:
        return {
            "kind": self.kind,
            "url": self.url,
            "branch": self.branch,
            "owner": self.owner,
            "repository": self.repository,
            "slug": self.slug,
            "original_url": self.original_url,
        }


def parse_repository_target(url: str, branch: str = "main") -> ScanTarget:
    """Parses a GitHub repository URL + branch into a ScanTarget.

    Raises TargetError (with a reason code the API surfaces verbatim) rather
    than guessing at a malformed or unsupported target.
    """
    raw_url = (url or "").strip()
    raw_branch = (branch or "").strip() or "main"

    if not raw_url:
        raise TargetError("empty-url", "Enter a GitHub repository URL.")

    match = HTTPS_PATTERN.match(raw_url) or SSH_PATTERN.match(raw_url)

    if not match:
        # Host first: a string that names no GitHub host is an unsupported
        # target, which is more useful to the user than "malformed".
        if "github.com" not in raw_url.lower():
            raise TargetError(
                "unsupported-host",
                "Only github.com repositories are supported today.",
            )
        if " " in raw_url:
            raise TargetError("malformed-url", "A repository URL cannot contain spaces.")
        raise TargetError(
            "malformed-url",
            "Use a repository URL of the form https://github.com/owner/repository.",
        )

    if not BRANCH_PATTERN.match(raw_branch):
        raise TargetError("invalid-branch", f"'{raw_branch}' is not a valid git branch name.")

    owner = match.group("owner")
    repository = match.group("repo")

    return ScanTarget(
        kind=GIT_REPOSITORY,
        url=f"https://github.com/{owner}/{repository}",
        branch=raw_branch,
        owner=owner,
        repository=repository,
        original_url=raw_url,
    )

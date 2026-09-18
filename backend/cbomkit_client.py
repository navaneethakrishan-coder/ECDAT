"""Fetch a CBOM from CBOMKit for one repository (no ECDAT pipeline).

A thin CLI over services/scanning/cbomkit.py, which is the single CBOMKit
adapter used by the API, the scan CLI and this script. Writes the CBOM to
the path the ECDAT pipeline reads.

Usage:
    python cbomkit_client.py <github_url> [branch]
"""

import json
import sys

from services.scanning.base import ScannerError
from services.scanning.cbomkit import CBOMKitRepositoryScanner
from services.scanning.service import CBOM_FILENAME, DATA_DIR
from services.scanning.targets import TargetError, parse_repository_target
from services.scanning.validation import normalize_cbom, validate_cbom


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python cbomkit_client.py <github_url> [branch]\n\n"
            "Example:\n"
            "  python cbomkit_client.py https://github.com/keycloak/keycloak main"
        )
        sys.exit(1)

    try:
        target = parse_repository_target(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
    except TargetError as error:
        print(f"ERROR [{error.code}]: {error.message}")
        sys.exit(1)

    scanner = CBOMKitRepositoryScanner()

    print("=" * 60)
    print("CBOMKIT SCAN")
    print("=" * 60)
    print(f"Repository: {target.url}")
    print(f"Branch    : {target.branch}")

    try:
        artifact = scanner.scan(target, progress=lambda message: print(message))
    except ScannerError as error:
        print(f"\nERROR [{error.code}]: {error.message}")
        sys.exit(1)

    report = validate_cbom(artifact.cbom)
    for warning in report["warnings"]:
        print(f"WARNING [{warning['code']}]: {warning['message']}")

    if not report["ok"]:
        for failure in report["errors"]:
            print(f"ERROR [{failure['code']}]: {failure['message']}")
        sys.exit(1)

    normalized, notes = normalize_cbom(artifact.cbom)
    for note in notes:
        print(f"NOTE: {note}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / CBOM_FILENAME
    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)

    stats = report["stats"]
    print(f"\nCBOM saved to: {path}")
    print(f"{stats['crypto_components']} cryptographic component(s) of {stats['components']}.")


if __name__ == "__main__":
    main()

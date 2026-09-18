"""Scan a GitHub repository from the command line.

Runs exactly the same scan the API runs (services/scanning): target
validation → CBOMKit → CBOM validation/normalization → the ECDAT pipeline.
There is no second implementation of the workflow.

Usage:
    python analyze_repository.py "<github_url>" [branch]
"""

import sys

from services.scanning import ScanService, TargetError


def describe_stage(stage):
    detail = f" — {stage['detail']}" if stage.get("detail") else ""
    return f"[{stage['status'].upper():>7}] {stage['label']}{detail}"


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            '  python analyze_repository.py "<github_url>" [branch]\n\n'
            "Example:\n"
            '  python analyze_repository.py "https://github.com/keycloak/keycloak" main'
        )
        sys.exit(1)

    github_url = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"

    print("=" * 70)
    print("ECDAT REPOSITORY SCAN")
    print("=" * 70)
    print("Repository:", github_url)
    print("Branch    :", branch)

    service = ScanService()

    try:
        state = service.run_sync(github_url, branch)
    except TargetError as error:
        print(f"\nERROR [{error.code}]: {error.message}")
        sys.exit(1)

    print("\nStages:")
    for stage in state["stages"]:
        print("  " + describe_stage(stage))

    if state["status"] != "completed":
        print(f"\nSCAN FAILED [{state['error_code']}]: {state['error']}")
        sys.exit(1)

    result = state["result"]
    print("\n" + "=" * 70)
    print("ECDAT SCAN COMPLETE")
    print("=" * 70)
    print(f"Cryptographic findings : {result['crypto_components']}")
    print(f"CBOM components        : {result['components']}")
    print(f"Recorded dependencies  : {result['dependency_edges']}")
    print(f"Duration               : {state['duration_seconds']}s")
    print("\nOpen the ECDAT dashboard to explore the results.")


if __name__ == "__main__":
    main()

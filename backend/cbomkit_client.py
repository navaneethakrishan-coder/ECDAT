import json
import sys
import time
from pathlib import Path

import requests


CBOMKIT_URL = "http://localhost:8081"
ECDAT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ECDAT_DIR / "data"

CBOM_FILE = DATA_DIR / "keycloak-cbom.json"


def start_scan(github_url, branch="main"):
    print("=" * 60)
    print("STARTING CBOMKIT SCAN")
    print("=" * 60)
    print(f"Repository: {github_url}")
    print(f"Branch:     {branch}")

    payload = {
        "scanUrl": github_url,
        "branch": branch
    }

    response = requests.post(
        f"{CBOMKIT_URL}/api/v1/scan",
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    print("CBOMKit accepted the scan request.")
    return response


def get_latest_cboms():
    response = requests.get(
        f"{CBOMKIT_URL}/api/v1/cbom/last/5",
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def wait_for_cbom(github_url, branch, timeout_seconds=1800):
    print("\nWaiting for CBOMKit to finish...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            cboms = get_latest_cboms()

            for entry in cboms:
                if (
                    entry.get("gitUrl") == github_url
                    and entry.get("branch") == branch
                ):
                    bom = entry.get("bom")

                    if bom:
                        print("\nCBOM generated successfully.")
                        return bom

        except requests.RequestException as error:
            print(f"Waiting for CBOMKit API: {error}")

        print(".", end="", flush=True)
        time.sleep(10)

    raise TimeoutError(
        "Timed out waiting for CBOMKit to generate the CBOM."
    )


def save_cbom(bom):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(CBOM_FILE, "w", encoding="utf-8") as file:
        json.dump(bom, file, indent=2)

    print(f"\nCBOM saved to:")
    print(CBOM_FILE)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python cbomkit_client.py <github_url> [branch]\n\n"
            "Example:\n"
            "  python cbomkit_client.py "
            "https://github.com/keycloak/keycloak main"
        )
        sys.exit(1)

    github_url = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"

    try:
        start_scan(github_url, branch)

        bom = wait_for_cbom(github_url, branch)

        save_cbom(bom)

        print("\n" + "=" * 60)
        print("CBOMKIT → ECDAT IMPORT COMPLETE")
        print("=" * 60)

    except Exception as error:
        print("\nERROR:")
        print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
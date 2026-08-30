import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def run_command(command):
    print("\n" + "=" * 70)
    print("RUNNING:", " ".join(command))
    print("=" * 70)

    result = subprocess.run(
        command,
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        print("\nERROR: Command failed.")
        sys.exit(result.returncode)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            '  python analyze_repository.py "<github_url>" [branch]\n\n'
            "Example:\n"
            '  python analyze_repository.py '
            '"https://github.com/keycloak/keycloak" main'
        )
        sys.exit(1)

    github_url = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"

    python = sys.executable

    print("=" * 70)
    print("ECDAT AUTOMATED REPOSITORY ANALYSIS")
    print("=" * 70)
    print("Repository:", github_url)
    print("Branch:", branch)

    # ---------------------------------------------------------
    # STEP 1: CBOMKit scan + CBOM retrieval
    # ---------------------------------------------------------
    run_command([
        python,
        str(BASE_DIR / "cbomkit_client.py"),
        github_url,
        branch
    ])

    # ---------------------------------------------------------
    # STEP 2: Complete ECDAT analysis pipeline
    # ---------------------------------------------------------
    run_command([
        python,
        str(BASE_DIR / "run_pipeline.py")
    ])

    print("\n" + "=" * 70)
    print("ECDAT ANALYSIS COMPLETE")
    print("=" * 70)

    print("\nRepository:")
    print(github_url)

    print("\nThe CBOM was scanned and the complete ECDAT")
    print("migration analysis pipeline has finished successfully.")

    print("\nOpen the ECDAT dashboard to view the results.")


if __name__ == "__main__":
    main()
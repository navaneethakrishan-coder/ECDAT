"""A deterministic ECDAT dataset for tests, independent of data/.

Most analysis tests used to read `data/` directly, so they silently depended
on whichever repository ECDAT had scanned last: they asserted "30 assets" and
named bom_refs from one CBOMKit scan of pyca/cryptography. Scanning any other
repository -- which is exactly what ECDAT is for -- broke them.

This module builds a fixture dataset instead:

  * `FIXTURE_CBOM` is a small, hand-written CycloneDX CBOM with stable
    bom-refs, shaped to contain the situations the tests are about: a key
    agreement, two *different* findings sharing the name "RSA-2048", a
    signature with key material that inherits its strategy, and a hash.
  * That CBOM is run through the **real** 13-stage pipeline, in an isolated
    copy of backend/ inside a temp directory, so every generated file is
    produced by the production code under test -- nothing is mocked and no
    expected value is hand-written.
  * `data/` is never read or written.

Tests refer to findings by role (`ref("x25519")`), never by a UUID from some
past scan, and derive counts from the fixture itself, so they stay true
whatever ECDAT has scanned.
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REAL_DATA_DIR = BACKEND_DIR.parent / "data"


# ---------------------------------------------------------------------------
# The fixture CBOM
# ---------------------------------------------------------------------------

# Roles the tests need, and the bom-ref each one keeps. Stable by design:
# these are the fixture's identity, not values copied from a scan.
REFS = {
    "x25519": "fixture-x25519-key-agreement",
    "x25519_private_key": "fixture-x25519-private-key",
    "rsa2048_java": "fixture-rsa2048-java-keyfactory",
    "rsa2048_python": "fixture-rsa2048-python-generate",
    # Key material governed by each RSA finding separately. Two findings can
    # share a displayed algorithm name and still own entirely different
    # relationships, and that is precisely what blast radius must not mix up.
    "rsa2048_java_key": "fixture-rsa2048-java-private-key",
    "rsa2048_python_key": "fixture-rsa2048-python-private-key",
    "dsa": "fixture-dsa-signature",
    "dsa_public_key": "fixture-dsa-public-key",
    "sha256": "fixture-sha256-digest",
    "hmac": "fixture-hmac-sha256",
    # A finding with no recorded CBOM relationship at all. Real scans are
    # full of these, and blast radius has to report "none" rather than
    # inventing an edge, so the fixture keeps one deliberately isolated.
    "aes256": "fixture-aes256-gcm",
}

# A ref that is well-formed but belongs to no finding, for 404 / lookup-miss
# assertions. Deliberately not a UUID from any dataset.
MISSING_REF = "fixture-no-such-finding"


def _occurrence(location, line, context, offset=8):
    return {"location": location, "line": line, "offset": offset, "additionalContext": context}


def _component(bom_ref, name, asset_type, occurrences, primitive=None, oid=None):
    crypto = {"assetType": asset_type}
    if primitive:
        crypto["algorithmProperties"] = {"primitive": primitive}
    if oid:
        crypto["oid"] = oid
    return {
        "name": name,
        "type": "cryptographic-asset",
        "bom-ref": bom_ref,
        "cryptoProperties": crypto,
        "evidence": {"occurrences": occurrences},
    }


FIXTURE_CBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "version": 1,
    "metadata": {
        "timestamp": "2026-01-01T00:00:00Z",
        "properties": [
            {"name": "gitUrl", "value": "https://github.com/ecdat-tests/fixture"},
            {"name": "revision", "value": "main"},
            {"name": "commit", "value": "f1x7ure"},
        ],
    },
    "components": [
        # Key agreement, two occurrences in one file: a clean DIRECT_PQC case
        # and the source-impact fixture (2 occurrences, 1 file).
        _component(
            REFS["x25519"],
            "X25519",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/KeyExchange.java",
                    42,
                    "javax.crypto.KeyAgreement#getInstance(Ljava/lang/String;)Ljavax/crypto/KeyAgreement;",
                ),
                _occurrence(
                    "src/main/java/com/example/KeyExchange.java",
                    58,
                    "javax.crypto.KeyAgreement#generateSecret()[B",
                ),
            ],
            primitive="key-agree",
            oid="1.3.101.110",
        ),
        # Key material governed by the key agreement above.
        _component(
            REFS["x25519_private_key"],
            "private-key@fixture-x25519",
            "related-crypto-material",
            [_occurrence("src/main/java/com/example/KeyExchange.java", 40, "java.security.KeyPair#getPrivate()")],
        ),
        # Two DIFFERENT findings that share the displayed algorithm name.
        # This is the duplicate-name isolation fixture: same name, different
        # bom-refs, different files, different evidence.
        _component(
            REFS["rsa2048_java"],
            "RSA-2048",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/KeyLoader.java",
                    77,
                    "java.security.KeyFactory#getInstance(Ljava/lang/String;)Ljava/security/KeyFactory;",
                )
            ],
            primitive="pke",
            oid="1.2.840.113549.1.1.1",
        ),
        _component(
            REFS["rsa2048_python"],
            "RSA-2048",
            "algorithm",
            [
                _occurrence(
                    "tools/generate_vectors.py",
                    12,
                    "cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key",
                )
            ],
            primitive="pke",
            oid="1.2.840.113549.1.1.1",
        ),
        # One piece of key material per RSA finding, in that finding's own
        # file. Same-named findings therefore have *different* dependents,
        # which is what lets a test prove the blast-radius view keeps their
        # relationships apart instead of merging them by name.
        _component(
            REFS["rsa2048_java_key"],
            "private-key@fixture-rsa2048-java",
            "related-crypto-material",
            [_occurrence("src/main/java/com/example/KeyLoader.java", 81, "java.security.PrivateKey")],
        ),
        _component(
            REFS["rsa2048_python_key"],
            "private-key@fixture-rsa2048-python",
            "related-crypto-material",
            [_occurrence("tools/generate_vectors.py", 19, "rsa.RSAPrivateKey")],
        ),
        # Symmetric encryption, standalone: no key material and no dependency
        # entry, so it stays outside the dependency graph entirely. It sits in
        # the key-exchange file on purpose, giving the suite two findings that
        # share a source file with no edge between them -- co-location is not
        # a relationship, and blast radius must not treat it as one.
        _component(
            REFS["aes256"],
            "AES-256-GCM",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/KeyExchange.java",
                    96,
                    "javax.crypto.Cipher#getInstance(Ljava/lang/String;)Ljavax/crypto/Cipher;",
                )
            ],
            primitive="block-cipher",
        ),
        # A signature used on a TLS path: externally exposed, so the strategy
        # engine has the evidence it needs for a hybrid transition.
        _component(
            REFS["dsa"],
            "DSA",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/tls/TlsHandshakeSigner.java",
                    120,
                    "java.security.Signature#getInstance(Ljava/lang/String;)Ljava/security/Signature;",
                ),
                _occurrence(
                    "src/main/java/com/example/tls/TlsHandshakeSigner.java",
                    141,
                    "javax.net.ssl.SSLContext#getInstance(Ljava/lang/String;)Ljavax/net/ssl/SSLContext;",
                ),
                _occurrence(
                    "src/main/java/com/example/tls/CertificateVerifier.java",
                    64,
                    "java.security.cert.X509Certificate#verify(Ljava/security/PublicKey;)V",
                ),
            ],
            primitive="signature",
            oid="1.2.840.10040.4.3",
        ),
        _component(
            REFS["dsa_public_key"],
            "public-key@fixture-dsa",
            "related-crypto-material",
            [
                _occurrence(
                    "src/main/java/com/example/tls/CertificateVerifier.java",
                    61,
                    "java.security.cert.X509Certificate#getPublicKey()Ljava/security/PublicKey;",
                )
            ],
        ),
        # Hashing and MAC: roles with no PQC replacement (KEEP).
        _component(
            REFS["sha256"],
            "SHA-256",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/Digest.java",
                    18,
                    "java.security.MessageDigest#getInstance(Ljava/lang/String;)Ljava/security/MessageDigest;",
                )
            ],
            primitive="hash",
            oid="2.16.840.1.101.3.4.2.1",
        ),
        _component(
            REFS["hmac"],
            "HMAC-SHA256",
            "algorithm",
            [
                _occurrence(
                    "src/main/java/com/example/Digest.java",
                    31,
                    "javax.crypto.Mac#getInstance(Ljava/lang/String;)Ljavax/crypto/Mac;",
                )
            ],
            primitive="mac",
        ),
    ],
    "dependencies": [
        {"ref": REFS["x25519_private_key"], "dependsOn": [REFS["x25519"]]},
        {"ref": REFS["rsa2048_java_key"], "dependsOn": [REFS["rsa2048_java"]]},
        {"ref": REFS["rsa2048_python_key"], "dependsOn": [REFS["rsa2048_python"]]},
        {"ref": REFS["dsa_public_key"], "dependsOn": [REFS["dsa"]]},
        {"ref": REFS["dsa"], "dependsOn": [REFS["sha256"]]},
        {"ref": REFS["hmac"], "dependsOn": [REFS["sha256"]]},
    ],
}


def ref(role: str) -> str:
    """The bom_ref of a fixture finding, by the role the test cares about."""
    try:
        return REFS[role]
    except KeyError:
        raise KeyError(f"Unknown fixture role '{role}'. Known roles: {sorted(REFS)}") from None


def expected_assets() -> int:
    """How many findings the fixture has -- derived, never hard-coded."""
    return len({component["bom-ref"] for component in FIXTURE_CBOM["components"]})


# ---------------------------------------------------------------------------
# Building the dataset with the real pipeline
# ---------------------------------------------------------------------------

_IGNORED = shutil.ignore_patterns("venv", "__pycache__", "*.pyc", ".pytest_cache")


def _signature() -> str:
    """Identifies this fixture: its CBOM plus the production code that
    processes it, so a change to either rebuilds rather than reusing a stale
    dataset."""
    digest = hashlib.sha256()
    digest.update(json.dumps(FIXTURE_CBOM, sort_keys=True).encode("utf-8"))
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        parts = path.parts
        if "venv" in parts or "__pycache__" in parts or path.name.startswith("test_"):
            continue
        if path.name == "fixture_dataset.py":
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    registry = REAL_DATA_DIR / "pqc-algorithms.json"
    if registry.exists():
        digest.update(registry.read_bytes())
    return digest.hexdigest()[:16]


def _root() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / f"ecdat-fixture-{_signature()}"


def build(force: bool = False) -> Path:
    """Materialises the fixture dataset and returns its data directory.

    The dataset is produced by running the real pipeline over an isolated
    copy of backend/, so `data/` is untouched. The result is cached between
    test files and test runs; it is rebuilt whenever the fixture or the
    production code changes.
    """
    root = _root()
    data_dir = root / "data"
    marker = root / ".ready"

    if marker.exists() and not force:
        return data_dir

    if root.exists():
        shutil.rmtree(root, ignore_errors=True)

    backend_copy = root / "backend"
    shutil.copytree(BACKEND_DIR, backend_copy, ignore=_IGNORED)
    data_dir.mkdir(parents=True, exist_ok=True)

    with (data_dir / "keycloak-cbom.json").open("w", encoding="utf-8") as file:
        json.dump(FIXTURE_CBOM, file, indent=2)

    registry = REAL_DATA_DIR / "pqc-algorithms.json"
    if not registry.exists():
        raise FileNotFoundError(f"The PQC registry is required to build the fixture: {registry}")
    shutil.copy2(registry, data_dir / "pqc-algorithms.json")

    completed = subprocess.run(
        [sys.executable, "run_pipeline.py"],
        cwd=str(backend_copy),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        timeout=600,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise RuntimeError(f"The fixture pipeline failed:\n{tail}")

    marker.write_text(completed.stdout[-2000:], encoding="utf-8")
    return data_dir


def data_dir() -> Path:
    return build()


def load(filename: str):
    """Loads one generated file from the fixture dataset."""
    path = data_dir() / filename
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def assets():
    return load("ecdat-assets.json")["assets"]


def report():
    return load("ecdat-migration-report.json")


def strategy_of(bom_ref: str):
    """The migration strategy the real pipeline decided for a fixture finding."""
    for record in report()["assets"]:
        if record["bom_ref"] == bom_ref:
            return (record.get("migration_strategy") or {}).get("strategy")
    return None


def use_fixture_data(*modules):
    """Points already-imported modules at the fixture dataset.

    `main` and `services.ai_advisor` resolve their data directory from a
    module-level `DATA_DIR` each time they read, so a test that calls their
    functions in-process can redirect them here instead of depending on
    whatever ECDAT last scanned. Production code is unchanged; only the
    module attribute inside the test process moves.
    """
    directory = data_dir()
    for module in modules:
        if not hasattr(module, "DATA_DIR"):
            raise AttributeError(f"{module.__name__} has no DATA_DIR to redirect.")
        module.DATA_DIR = directory
    return directory


def ref_with_strategy(strategy: str, inherited: bool = False) -> str:
    """A fixture finding whose strategy is `strategy`, chosen by the pipeline.

    Tests state the behaviour they need ("a HYBRID finding") instead of
    naming a UUID, so they keep working if the fixture grows.
    """
    for record in report()["assets"]:
        decision = record.get("migration_strategy") or {}
        if decision.get("strategy") != strategy:
            continue
        if bool(decision.get("inherited_from")) != inherited:
            continue
        return record["bom_ref"]
    raise AssertionError(f"The fixture must contain a {strategy} finding (inherited={inherited}).")


# ---------------------------------------------------------------------------
# Serving the fixture dataset over the real API
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def api_server(timeout: float = 60.0):
    """Runs the real FastAPI app over the fixture dataset, on its own port.

    Same application code, isolated data: the API tests get a dataset they
    can make exact assertions about without depending on what the developer's
    ECDAT last scanned, and without touching the running dev server.
    """
    dataset = data_dir()
    backend_copy = dataset.parent / "backend"
    port = _free_port()

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(backend_copy),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"The fixture API server exited early:\n{process.stdout.read()[-1500:]}")
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=2):
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("The fixture API server did not become ready in time.")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    directory = build(force="--force" in sys.argv)
    print(f"Fixture dataset: {directory}")
    print(f"Findings: {expected_assets()}")
    for role, bom_ref in REFS.items():
        print(f"  {role:22s} {bom_ref:34s} -> {strategy_of(bom_ref)}")

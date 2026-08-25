import json
from pathlib import Path


# services/pqc_registry.py
# Project structure:
#
# ECDAT/
# ├── backend/
# │   └── services/
# │       └── pqc_registry.py
# └── data/
#     └── pqc-algorithms.json
#
# Therefore we need to go:
# services -> backend -> ECDAT

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

PQC_REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "pqc-algorithms.json"
)


def load_pqc_registry():
    """Load the PQC algorithm registry."""

    if not PQC_REGISTRY_PATH.exists():
        raise FileNotFoundError(
            f"PQC registry not found: {PQC_REGISTRY_PATH}"
        )

    with open(
        PQC_REGISTRY_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if "algorithms" not in data:
        raise ValueError(
            "PQC registry must contain 'algorithms'."
        )

    if not isinstance(data["algorithms"], list):
        raise ValueError(
            "'algorithms' must be a list."
        )

    return data


def get_pqc_algorithms():
    """Return all registered PQC algorithms."""

    data = load_pqc_registry()
    return data["algorithms"]


def find_pqc_algorithm(name):
    """Find a PQC algorithm by exact name."""

    algorithms = get_pqc_algorithms()

    for algorithm in algorithms:
        if algorithm["name"] == name:
            return algorithm

    return None


def get_algorithms_by_family(family):
    """Return algorithms belonging to a specific family."""

    algorithms = get_pqc_algorithms()

    return [
        algorithm
        for algorithm in algorithms
        if algorithm["family"] == family
    ]
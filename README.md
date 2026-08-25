# ECDAT

Explainable Cryptographic Discovery, Quantum Risk Assessment and Migration Planning Platform — a research prototype for SIH Problem Statement 26164.

## Phase 1 status

This repository currently provides only the runnable project foundation:

- FastAPI backend with a versioned health endpoint.
- Next.js + TypeScript + Tailwind frontend with a live backend-health indicator.
- Python and frontend smoke tests.
- Architecture and local-development documentation.

Cryptographic discovery, CBOM, risk, PQC, AI, and dashboard features are intentionally not implemented until their scheduled phases.

## Quick start

See [docs/installation.md](docs/installation.md). The backend health endpoint is available at `GET /api/v1/health` when running locally.

## Architecture

See [docs/architecture.md](docs/architecture.md) for boundaries and Phase 1 decisions.

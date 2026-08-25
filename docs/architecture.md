# ECDAT architecture

## Scope of this document

This describes the implemented Phase 1 foundation, not planned functionality.

## Structure

```
backend/     FastAPI application and deterministic analysis-service boundaries
frontend/    Next.js user interface
data/        Runtime-only local data (not committed)
demo/        Future self-contained demo source project
docs/        Implementation documentation
scripts/     Repeatable developer commands as the project grows
tests/       Cross-system tests as the project grows
```

The backend is organized around transport (`api`), data contracts (`schemas`), persistence models (`models`), and domain services (`services`). Future cryptographic analysis modules will be pure and deterministic where possible; the HTTP layer will only coordinate them.

## Phase 1 decisions

- **Python + FastAPI + Pydantic**: typed API contracts and built-in OpenAPI support.
- **Next.js + React + TypeScript + Tailwind**: typed, component-based web interface with a standard dashboard-ready base.
- **SQLite later, behind a persistence boundary**: no database is created in Phase 1 because no persistent entities exist yet. This avoids inventing schema before the CBOM and asset models are designed.
- **Versioned API prefix**: all public endpoints begin with `/api/v1` to preserve compatibility as the application evolves.
- **No AI integration in the foundation**: deterministic backend services will remain authoritative.

## Current request flow

```
Browser → Next.js UI → GET /api/v1/health → FastAPI → Health response
```

The frontend reads its backend base URL from `NEXT_PUBLIC_ECDAT_API_BASE_URL`, defaulting to `http://127.0.0.1:8000` for local development.

# ECDAT — Project Context

> ECDAT = "Enterprise Cryptographic Discovery and (post-quantum) migration Analysis Tool" (the name is not spelled out anywhere in the code; inferred from `AnalyzeRequest`, API title, and UI copy: "ECDAT Cryptographic Discovery and Post-Quantum Migration API").

This document describes what the ECDAT codebase actually does today, as observed directly in the code on branch `ecdat-1` (last updated 2026-09-15, after (1) the backend-consolidation and AI-data-consistency fixes, (2) the AI Advisor UI/UX integration and dashboard visual-design pass, (3) the backend risk-scoring unification, (4) making `RiskContext` genuinely per-asset/evidence-derived, (5) a dedicated full frontend UI/UX overhaul, (6) a composition/visual-hierarchy redesign of the asset-detail view and dashboard, (7) a premium visual-identity redesign (color system, hero, charts, sidebar), and (8) a console-grade visual system and workspace re-composition (layered atmosphere/glass/glow tokens, command topbar, 7-stage pipeline, vertical migration decision flow, 2-column investigation workspace) — see `CHANGELOG.md`). It is descriptive, not aspirational — see `TODO.md` for gaps and problems.

## 1. What ECDAT does

ECDAT discovers cryptographic assets in a source-code repository, assesses their quantum-vulnerability risk, and recommends a post-quantum-cryptography (PQC) migration path. Concretely, it:

1. Triggers **CBOMKit** (an external, separately-running service) to scan a GitHub repository and produce a CycloneDX **CBOM** (Cryptography Bill of Materials).
2. Runs a 13-stage local Python pipeline (`backend/run_pipeline.py`) that turns the raw CBOM into a chain of enriched JSON datasets: classification → risk scoring → blast radius → migration complexity/priority → PQC candidate mapping/ranking → migration actions → a final unified migration report.
3. Serves all of these datasets over a FastAPI HTTP API.
4. Renders the results in a single-page React dashboard (charts, asset tables, filters, per-asset drill-down).
5. Offers an "AI Migration Advisor" that sends one asset's ECDAT results to a locally-hosted **Ollama** LLM (`qwen3:14b`) and displays a structured natural-language recommendation.

There is no user authentication, no persistent database, and no multi-user/multi-project concept — it operates on one CBOM/one repository at a time, stored as flat JSON files in `data/`.

## 2. Core features (as implemented)

- **Automated repository analysis** — a form in the dashboard ("Analyze Repository") posts a GitHub URL + branch, which asynchronously runs CBOMKit scan + the full ECDAT pipeline as a background OS subprocess, with polling for status (`backend/main.py`, `analyze_repository.py`).
- **Cryptographic asset inventory** — full list of detected crypto components (algorithms, keys, certificates, protocols) with CBOM evidence (file/line/context) (`cbom_parser.py`, `/api/assets`).
- **Classification** — maps each asset to a knowledge base of known algorithms (`backend/knowledge/crypto_knowledge.py`) to determine quantum-vulnerability category, primitive, and purpose (`classify_cbom.py`).
- **Risk scoring** — as of 2026-09-14, `explain_cbom.py` is the single place risk is ever calculated, producing two intentionally different 0–100 figures per asset: a "basic" quantum-vulnerability-only score and a "contextual" weighted score (quantum risk + business criticality + data lifetime + exposure + migration time + evidence quality; see `ARCHITECTURE.md` §5/§10 for the full unification history). Every risk figure anywhere in the system — `/api/risk` (basic), the dashboard, `/api/asset/{name}`, and the AI advisor (all contextual) — is now either read directly from that one computation's output or mechanically re-projected from it, with an automated consistency check (`backend/check_risk_consistency.py`) that fails the analysis pipeline if any of them ever disagree. The "contextual" weighting's business-context inputs (`business_criticality`, `exposure`, `migration_time_years`) are, as of 2026-09-14, derived per asset from that asset's own CBOM evidence (`backend/services/risk_context.py`) rather than one fixed guess applied to every asset in every repository — see `ARCHITECTURE.md` §11.
- **Mosca-style migration urgency analysis** — compares data lifetime + migration time against an assumed quantum threat horizon (`services/mosca_analysis.py`).
- **Blast radius** — dependency-graph-based estimate of how many other components would be affected if an asset is migrated (`services/blast_radius.py`, `services/dependency_graph.py`).
- **Migration complexity & priority** — weighted composite scores combining risk, blast radius, and complexity (`services/migration_complexity.py`, `services/migration_priority.py`).
- **PQC candidate mapping & ranking** — maps a vulnerable algorithm to one or more NIST PQC replacement families, then ranks candidates by compatibility/purpose fit (`services/pqc_mapper.py`, `services/pqc_ranker.py`, `data/pqc-algorithms.json`).
- **Source-code impact analysis** — derives affected files/classes/functions from CBOM evidence locations (`services/source_impact_analyzer.py`).
- **Migration action generation** — produces a short list of concrete developer action items per asset (`services/migration_action_generator.py`).
- **Unified migration report** — merges every stage above into one per-asset record (`generate_migration_report.py`, `/api/asset/{name}`), which is what the dashboard and AI advisor primarily consume.
- **AI Migration Advisor** — Qwen3:14B (via Ollama) explains the ECDAT results for a selected asset in plain language, in a fixed 6-section format (RISK/MIGRATION/PQC/ACTIONS/IMPACT/SUMMARY, each shown with a matching icon). Embedded as a compact panel inside the asset-detail workspace (bottom-right of its 2×2 grid — see below), with an idle/loading/success/error+retry state machine, a one-line context strip tying it to the risk/priority/PQC data shown beside it, and a small availability indicator ("Ready"/"Analyzing"/"Unavailable") derived from that same state. See `AI_ADVISOR.md`.
- **Dashboard UI** — a command topbar (asset search sharing state with the Asset Explorer's own search box, `Ctrl/⌘+K` and `/` shortcuts, live backend status); an asymmetric hero (headline with a cyan→blue→violet gradient on its closing words, an orbital inline-SVG visual, a large glowing Quantum Readiness ring beside a 2×2 grid of supporting counts); a repository-analysis panel with a 7-stage numbered pipeline visualization beside a "Migrate First" Critical Findings panel (top HIGH/CRITICAL assets as two-line ranked rows); three donut/ring charts (risk severity, migration strategy including "Not Applicable", source impact, via Recharts); a filterable/searchable card-based asset explorer; and a per-asset investigation workspace (full-height overlay) — a header band with the large severity-colored risk score, migration priority and PQC recommendation, then **Source & Evidence** and **Risk Intelligence** stacked beside a vertical **Migration Path** decision flow, with the **AI Advisor** full-width below. All on one scrollable page with a 9-item sidebar (no router). Colors are assigned by meaning throughout: severity hues for risk/impact, cyan only for real PQC candidates, violet for the AI Advisor, blue for actions/interactive chrome, magenta only as a decorative gradient accent. See `ARCHITECTURE.md` §8/§12–§15 for the full history of how this UI was built up across five rounds.

## 3. Technology stack

### Backend
- **Python** (venv at `backend/venv`, target CPython 3.14 per compiled `.pyc` names)
- **FastAPI** 0.141.1 + **Uvicorn** 0.52.4 (ASGI server — started manually, no committed run script)
- **Pydantic** for request bodies
- **requests** 2.34.2 for calling CBOMKit and Ollama HTTP APIs
- No ORM/database — all persistence is flat JSON files under `data/`
- No `requirements.txt` / `pyproject.toml` is committed anywhere in the repo — dependencies are only inferable from the venv's installed packages

### Frontend
- **React** 19.2.8 + **Vite** 8.2.2 (dev server / bundler)
- **Recharts** 3.10.1 for donut/ring charts (bar charts until the premium visual-identity round — see `ARCHITECTURE.md` §14)
- **lucide-react** 1.34.0 for icons
- **oxlint** for linting (`npm run lint` — currently fails in this local environment for reasons unrelated to the code; see `TODO.md`)
- Plain hand-written CSS (`App.css`, rewritten 2026-09-14 as a single tokenized design-system stylesheet — CSS custom properties for colors/spacing/radius/shadows/motion — and extended 2026-09-15 with glass, glow and a decorative-only magenta accent token plus short motion primitives that honor `prefers-reduced-motion`; `index.css` is a 6-line reset) — no Tailwind/CSS-in-JS/component library. Typography is Inter (UI) + Space Grotesk (headline and dominant numerics), loaded by a Google Fonts `@import` at the top of `App.css`, which needs network access (`TODO.md` #27).
- `App.jsx` is still the single state/effects orchestrator (no router — `react-router` is not a dependency, in-page anchor scrolling), but is now a thin composition layer: nearly all rendering lives in `frontend/src/components/` (see the layout table below), built up across five rounds — an initial presentational extraction (`Badge.jsx`, `StatCard.jsx`, `DistributionBar.jsx`, `States.jsx`, `AIAdvisorPanel.jsx`); a structural overhaul adding `HeroOverview.jsx`, `PipelineStepper.jsx`, `RepositoryAnalysisPanel.jsx`, `Sidebar.jsx`, `AssetFilters.jsx`, `AssetExplorer.jsx`, `AssetDetailPanel.jsx`; a composition/visual-hierarchy round that replaced the original flat asset-detail sections with workspace panels (`detail/AssetHeaderBand.jsx`, `RiskImpactPanel.jsx`, `MigrationFlow.jsx`, `EvidencePanel.jsx`) and added `CriticalFindingsPanel.jsx`; a premium visual-identity round that replaced the bar-chart `AnalyticsPanel.jsx` with the donut-chart `DonutPanel.jsx`; and a 2026-09-15 console-grade visual-system round that added `Topbar.jsx` and re-composed the asset-detail workspace. No new npm dependency was added across any of the five rounds — same React/Vite architecture throughout. See `ARCHITECTURE.md` §12–§15 and `CHANGELOG.md` for the full history.
- No test setup (no Jest/Vitest/RTL config or test files under `frontend/`) — every UI round so far was instead verified with a throwaway, dependency-free Chrome DevTools Protocol driver script (Node's built-in `fetch`/`WebSocket` against a locally-launched headless Chrome), kept outside the repository; see `CHANGELOG.md` for what each round's script exercised.

### External services (must be running separately, not part of this repo)
- **CBOMKit** at `http://localhost:8081` — performs the actual repository scan
- **Ollama** at `http://localhost:11434` — runs the `qwen3:14b` model for the AI advisor

### Data
- `data/*.json` — the pipeline's working "database" (overwritten on every analysis run)
- `data-backup/` — an apparent manual snapshot/duplicate of `data/` (checked into git; see `TODO.md`)
- `demo/` — sample/duplicate CBOM files used ad hoc during development

## 4. Repository layout

```
backend/
  main.py                 THE canonical FastAPI app — every route, including /api/analyze and /api/ai/advice
  api/main.py              Deprecated shim: re-exports `app` from main.py (kept so `uvicorn api.main:app` still works)
  cbomkit_client.py         Calls CBOMKit, polls for results, saves CBOM to data/keycloak-cbom.json
  analyze_repository.py     Orchestrates cbomkit_client.py + run_pipeline.py (subprocess)
  run_pipeline.py           Runs the 13 pipeline stage scripts in order
  cbom_parser.py, classify_cbom.py, explain_cbom.py (THE risk computation),
  score_cbom.py (legacy "basic risk" view, re-projected from explain_cbom.py's
  output — see ARCHITECTURE.md §10), generate_blast_radius.py,
  generate_migration_complexity.py, generate_migration_priority.py,
  generate_pqc_migration.py, generate_pqc_ranking.py,
  generate_pqc_migration_plan.py, generate_migration_actions.py,
  generate_migration_report.py, check_risk_consistency.py (final pipeline
  gate)     The 13 active pipeline stages, in run order
  score_contextual_cbom.py  Deprecated, kept on disk but no longer run by the
  pipeline — see ARCHITECTURE.md §10
  services/                Pure-function scoring/classification/mapping logic used by the stage scripts,
  including risk_context.py (derives a per-asset RiskContext from real CBOM
  evidence — see ARCHITECTURE.md §11)
  models/risk_factors.py    RiskContext dataclass (field definitions + the two fields that remain fixed,
  documented threat-model assumptions rather than per-asset-derived)
  knowledge/crypto_knowledge.py  Algorithm knowledge base for classification
  test_*.py                 Ad hoc pytest-style test scripts (not run by any CI config found)
  main_backup.py, main_backup_before_pipeline.py, cbom_parser_backup.py  Stale backup copies
frontend/
  src/App.jsx                Page orchestrator: state, effects, data-fetching/joining; delegates all rendering
  src/App.css                Tokenized design-system stylesheet (colors, spacing, radius, motion),
  restructured 2026-09-14 for the new component set below
  src/api.js                 fetch() wrapper for every backend endpoint (unchanged 2026-09-14; getPriority()
  and getHealth() were pre-existing exports newly wired into the UI this round)
  src/index.css, main.jsx    Vite/React bootstrap
  src/components/            Badge.jsx, StatCard.jsx, DistributionBar.jsx, States.jsx, AIAdvisorPanel.jsx,
  HeroOverview.jsx, PipelineStepper.jsx, RepositoryAnalysisPanel.jsx,
  DonutPanel.jsx, Sidebar.jsx, Topbar.jsx, AssetFilters.jsx, AssetExplorer.jsx,
  AssetDetailPanel.jsx, CriticalFindingsPanel.jsx
  src/components/detail/     AssetHeaderBand.jsx, RiskImpactPanel.jsx, MigrationFlow.jsx,
  EvidencePanel.jsx  (the asset-detail workspace's panels --
  see ARCHITECTURE.md §15)
data/                       Generated + input JSON ("the database")
data-backup/                Duplicate copy of data/ checked into git
demo/                       Sample CBOM files
```

## 5. Related documents

- `ARCHITECTURE.md` — actual system/data-flow architecture, including known inconsistencies
- `AI_ADVISOR.md` — AI advisor implementation detail (endpoint, prompt, model, limitations)
- `TODO.md` — prioritized issue list
- `CHANGELOG.md` — dated history of what changed, starting from this documentation pass

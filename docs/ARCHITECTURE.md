# ECDAT — Architecture

This document reflects the architecture as actually implemented, traced through the code (not the intended/idealized design). Where the real implementation diverges from what you'd expect, that divergence is called out explicitly.

> **Update (2026-09-14, backend consolidation + AI data-consistency):** the two-backend split described below (§6) has been resolved, and the AI advisor's data source described in §3/§5 has been fixed.
> **Update (2026-09-14, AI Advisor UI/UX + dashboard visual design):** the AI Advisor's frontend integration and the dashboard's CSS were reworked — see §8 and §9. No backend or API changes were needed for this round.
> **Update (2026-09-14, risk-scoring unification):** the three-parallel-pipelines problem described in §5 has been resolved at the data-generation level (not just at the AI advisor's consumption level, as the first update above did). See the rewritten §5 and §10.
> **Update (2026-09-14, RiskContext contextualization):** `RiskContext` is no longer one hardcoded object shared by every asset in every repository — it is now derived per asset from real CBOM evidence. See §11. Risk scores for assets whose only evidence is in test/demo/doc paths, or that involve network-facing protocols, changed as a direct and intended consequence.
> **Update (2026-09-14, frontend UI/UX overhaul):** the frontend was substantially restructured and componentized (hero overview, pipeline visualization, card-based asset explorer, a fixed asset-detail section order, a live backend-health indicator) — see §8 (revised) and the new §12. No backend or API changes were made or needed for this round.
> **Update (2026-09-14, composition & visual-hierarchy redesign):** the asset-detail view was restructured again, from a flat 6-section stack into a 2×2 "investigation workspace" grid; §8/§12 below have been corrected to describe this current structure rather than the superseded one. See §13.
> **Update (2026-09-14, premium visual-identity redesign):** color system, hero section, sidebar nav, and data-visualization style were reworked (still no backend/API changes) — see the new §14.
> **Update (2026-09-15, console-grade visual system + workspace re-composition):** a fourth frontend-only round — layered atmosphere/glass/glow design tokens, a command topbar, a 7-stage pipeline, a vertical migration decision flow, a 2-column asset-detail workspace with the AI Advisor full-width below, and truthfulness fixes to two dashboard figures. §13's grid description is superseded — see the new §15.
> Sections have been updated in place to describe the current state; see `CHANGELOG.md` for exactly what changed and why.

## 1. High-level component diagram

```
 ┌────────────┐      GitHub URL       ┌───────────┐
 │  React UI  │ ───────────────────▶  │  FastAPI  │
 │ (Vite,     │   POST /api/analyze   │  backend  │
 │  port 5173)│                       │ (port 8000)│
 └─────┬──────┘                       └─────┬─────┘
       │  GET /api/* (poll + read data)      │ subprocess
       │                                      ▼
       │                              analyze_repository.py
       │                                      │
       │                         ┌────────────┴────────────┐
       │                         ▼                          ▼
       │                 cbomkit_client.py            run_pipeline.py
       │                         │                          │
       │                         ▼                          ▼
       │                 ┌───────────────┐        13 local Python stages
       │                 │   CBOMKit     │        (see §3)
       │                 │ (external,    │                │
       │                 │  port 8081)   │                ▼
       │                 └───────┬───────┘        data/ecdat-*.json
       │                         ▼                          │
       │              data/keycloak-cbom.json ◀─────────────┘
       │                    (raw CBOM)                (feeds back into
       │                                                pipeline stage 1)
       │
       │  POST /api/ai/advice {asset}
       ▼
 ┌───────────┐   HTTP    ┌────────┐
 │  FastAPI  │ ────────▶ │ Ollama │  model: qwen3:14b
 │  backend  │           │ :11434 │
 └───────────┘           └────────┘
```

`backend/main.py` is the single canonical FastAPI application (run as `uvicorn main:app` from the `backend/` directory) — it now implements every route the frontend calls, including `/api/analyze` + `/api/analyze/status` and `/api/ai/advice`. `backend/api/main.py` is kept only as a backward-compatible shim (`from main import app`) so `uvicorn api.main:app` still works and serves identical behavior; it no longer contains its own route definitions. See §6.

## 2. Repository-analysis flow (as implemented)

The flow requested in the task brief is close to reality but the actual chain is:

```
GitHub Repository URL (entered in dashboard)
  → POST /api/analyze  (backend/main.py — see §6 "known inconsistency")
  → background thread runs analyze_repository.py as a subprocess
      → cbomkit_client.py:
          POST http://localhost:8081/api/v1/scan {scanUrl, branch}
          poll  GET  http://localhost:8081/api/v1/cbom/last/5  every 10s (up to 30 min)
          save matching CBOM to data/keycloak-cbom.json   ← always this filename, see §7
      → run_pipeline.py runs 13 stage scripts in sequence (stops on first failure), the last of which is a consistency check rather than a data-generation stage:
          1. cbom_parser.py            keycloak-cbom.json        → ecdat-assets.json
          2. classify_cbom.py          ecdat-assets.json         → ecdat-classified-assets.json
          3. explain_cbom.py           ecdat-classified-assets   → ecdat-explainable-risk.json           (THE single authoritative risk computation)
          4. score_cbom.py             ecdat-explainable-risk    → ecdat-risk-assessed-assets.json       (legacy "basic risk" view, re-projected from #3 — see §10)
          5. generate_blast_radius.py       ecdat-assets + ecdat-explainable-risk        → ecdat-blast-radius.json
          6. generate_migration_complexity  ecdat-assets + explainable-risk + blast      → ecdat-migration-complexity.json
          7. generate_migration_priority    explainable-risk + blast + complexity        → ecdat-migration-priority.json
          8. generate_pqc_migration.py      ecdat-explainable-risk.json                  → ecdat-pqc-migration.json
          9. generate_pqc_ranking.py        (pqc-migration + assets)                     → ecdat-pqc-ranked.json
         10. generate_pqc_migration_plan.py (ranking + priority/complexity)              → ecdat-pqc-migration-plan.json
         11. generate_migration_actions.py  (pqc-migration-plan, etc.)                   → ecdat-migration-actions.json
         12. generate_migration_report.py   ALL of the above                             → ecdat-migration-report.json  (final unified per-asset record)
         13. check_risk_consistency.py      cross-checks #3 against #4 and #12           → fails the pipeline (exit 1) if any asset's risk figures disagree
  → frontend polls GET /api/analyze/status every 3s until status is "completed"/"failed"
  → on completion, dashboard re-fetches /api/summary, /api/assets, /api/migration-report/assets
  → FastAPI serves data/ecdat-*.json (mostly ecdat-migration-report.json) via /api/*
  → React dashboard renders it (stat cards, charts, asset table, detail panel)
```

Compared to the simplified flow in the task brief (`GitHub → CBOMKit → Cryptographic Assets → ECDAT Analysis → Risk/Migration/PQC/Blast Radius/Source Impact → FastAPI → React`), the real pipeline is materially the same *shape* but has **13 discrete stages** instead of one "ECDAT Analysis" step. **As of 2026-09-14, exactly one of those stages (`explain_cbom.py`) performs the actual risk calculation** — every other place that reports a risk figure either reads its output directly or re-projects a piece of it; see §5 and §10 for the history of how this was unified.

## 3. AI-advisor flow (as implemented)

```
User selects an asset in the dashboard, clicks "Generate AI Advice"
  → POST /api/ai/advice {asset: <name>}                         (backend/main.py)
  → services/ai_advisor.py: build_context(asset_name)
      reads data/ecdat-migration-report.json ONLY — the same unified,
      authoritative file /api/asset/{name} and the dashboard read —
      and extracts: current_risk, classification, migration_impact
      (priority/blast_radius/complexity), pqc_migration, recommendation,
      ranked_candidates[0], source_impact, and the first 5 migration_actions
  → assembles a compact JSON "context" object + fixed prompt template
  → POST http://localhost:11434/api/generate  {model: "qwen3:14b", prompt, stream:false, think:false}
  → Ollama returns { response: "<free text>" }
  → FastAPI returns { asset, model: "qwen3:14b", advice: "<free text>" }
  → React splits the text on "\n", renders lines matching
    /^(RISK|MIGRATION|PQC|ACTIONS|IMPACT|SUMMARY):$/i as <h4> headers, everything else as <p>
```

This now matches the brief's `ECDAT Analysis → AI Advisor → Ollama → Qwen3:14b → AI Recommendation → React UI` shape exactly. **Fixed 2026-09-14:** the AI advisor previously re-read four separate intermediate pipeline files (`ecdat-contextual-risk-assets.json`, `ecdat-migration-priority.json`, `ecdat-pqc-migration-plan.json`, `ecdat-migration-actions.json`) instead of the final unified report, which meant it could show a different "current risk" than the dashboard for the same asset. It now reads only `ecdat-migration-report.json` — the same file `/api/asset/{name}` and the dashboard are built from — so the risk/priority/PQC figures in an AI answer are guaranteed to match what the dashboard shows. Verified live against Ollama: for asset `DSA`, the dashboard's `current_risk` is `{score: 65.75, severity: "HIGH"}` and the AI's RISK section states "a high risk score of 65.75 and a high severity rating" — the same number. See `AI_ADVISOR.md` for full detail and `CHANGELOG.md` for the change record.

As a side effect of reading the unified report, the advisor's context now also includes `source_impact` (affected file/class/function counts and impact level), which it previously omitted entirely despite the dashboard's AI advisor panel already claiming to review "source-impact results."

## 4. Backend API surface

All routes are prefixed `/api` except `/`, `/health`. Every `GET /api/<thing>` endpoint reads one specific `data/ecdat-*.json` file at request time (no caching, no in-memory state beyond `analysis_state`). Endpoints exist for: `status`, `summary`, `assets` (+ `/{name}`), `risk` (+ `/{name}`), `priority` (+ `/{name}`), `complexity` (+ `/{name}`), `blast-radius` (+ `/{name}`), `pqc` (+ `/{name}`), `pqc-ranking` (+ `/{name}`), `source-impact` (+ `/{name}`), `actions` (+ `/{name}`), `migration-report/assets` (+ `/{name}`), `migration-actions`, `pqc-migration-plan`, `asset/{name}` (the "unified" combiner endpoint), `analyze` (POST) + `analyze/status`, `ai/advice` (POST).

`GET /api/asset/{name}` is the richest endpoint: it loads **9 separate JSON files** per request and stitches them together by asset name, preferring fields from the final report when present. This is what the frontend's asset-detail panel calls (`getAsset` in `api.js`).

## 5. Resolved: three parallel risk-scoring pipelines (fixed 2026-09-14)

The pipeline used to compute "risk" three separate times, from the same input (`ecdat-classified-assets.json`), using three different code paths that were never reconciled against each other:

| Stage script | Output file | Consumed by |
|---|---|---|
| `score_cbom.py` → `services/risk_engine.calculate_base_risk` | `ecdat-risk-assessed-assets.json` | `/api/risk`, `/api/risk/{name}` only |
| `score_contextual_cbom.py` → `services/contextual_risk.calculate_contextual_risk` | `ecdat-contextual-risk-assets.json` | AI advisor's `risk` context section only |
| `explain_cbom.py` → same `calculate_contextual_risk` function, plus `generate_risk_explanation` | `ecdat-explainable-risk.json` | Everything downstream: blast radius, complexity, priority, PQC mapping, and the final `ecdat-migration-report.json` (i.e. the whole dashboard) |

Both contextual computations called the exact same `calculate_contextual_risk()` with a `RiskContext` built from **hardcoded defaults** (`models/risk_factors.py`: `business_criticality="MEDIUM"`, `data_lifetime_years=5`, `migration_time_years=2`, `exposure="INTERNAL"`, `quantum_threat_horizon_years=10` — identical for every asset in every repository, never derived from the actual scanned project; **fixed 2026-09-14, see §11**). So `ecdat-contextual-risk-assets.json` and `ecdat-explainable-risk.json` always produced numerically identical scores per asset — verified empirically on the current dataset (0 mismatches across all 29 assets) before touching anything — but that was only true because both call sites happened to construct `RiskContext()` with no overrides; nothing *enforced* it. Likewise, `calculate_base_risk()` is a pure function of an asset's classification alone, so `score_cbom.py`'s independent call to it and `calculate_contextual_risk()`'s internal call to the same function (as its `base_risk` component) were also verified to already agree on every asset — again by coincidence of identical inputs, not by construction.

**On 2026-09-14 this was unified at the data-generation level** (not just at the AI advisor's consumption level, which is what the first `explain_cbom.py`-reads-only-the-report fix from earlier that day addressed). See §10 for exactly what changed. The net effect: `explain_cbom.py` is now the *only* place in the entire codebase that calls `calculate_base_risk()` or `calculate_contextual_risk()` — every other risk figure anywhere in the system (API responses, the dashboard, the AI advisor) is either read directly from `explain_cbom.py`'s output or mechanically re-projected from it, provably rather than coincidentally consistent.

**"Basic" (quantum-only) risk and "contextual" (weighted) risk remain two intentionally different numbers for the same asset** — that is not a bug. For `RSA-OAEP` in the current dataset: `/api/risk/RSA-OAEP` reports `{score: 100, severity: "CRITICAL"}` (quantum vulnerability alone), while `/api/asset/RSA-OAEP`, the dashboard, and the AI advisor all report `{score: 65.75, severity: "HIGH"}` (the full weighted contextual score, which also factors in business criticality/data lifetime/exposure/migration time/evidence quality). Both numbers are correct for what they each claim to measure, and both are now guaranteed to be internally consistent — the same `RSA-OAEP` "basic" score can never disagree between `/api/risk` and anywhere else that shows a basic score (there's only one other place: nowhere else does), and the same `RSA-OAEP` "contextual" score can never disagree between the dashboard, `/api/asset/{name}`, `/api/migration-report/assets`, and the AI advisor — verified live for this exact asset (see `CHANGELOG.md`).

## 6. Resolved: two divergent FastAPI apps (fixed 2026-09-14)

There used to be two nearly-identical FastAPI applications:

- `backend/main.py` — defined `POST /api/analyze`, `GET /api/analyze/status` (repository-analysis trigger, used by the dashboard's "Analyze Repository" panel) and `POST /api/ai/advisor` with body `{asset_name}`, but **not** `/api/ai/advice`.
- `backend/api/main.py` — defined `POST /api/ai/advice` with body `{asset}` (the exact contract `frontend/src/api.js`'s `getAIAdvice()` calls), but **not** `/api/analyze`.

Neither file, run alone, could serve the full frontend. **Resolution:** `backend/main.py` is now the single canonical application — it gained a `POST /api/ai/advice` route (new `AIAdviceRequest{asset: str}` model) that calls the same `services/ai_advisor.generate_advice()` the old `api/main.py` used. The old `/api/ai/advisor` route (body `{asset_name}`) was left in place, unused by the frontend but harmless, for backward compatibility — nothing else in the repo was found to depend on it. `backend/api/main.py` was rewritten to a 30-line shim:

```python
from main import app  # after inserting backend/ onto sys.path
```

so `uvicorn api.main:app` keeps working and now serves the exact same routes as `uvicorn main:app`, instead of a silently-diverging copy. Verified: importing both `main` and `api.main` confirms `api.main.app is main.app`, and both `uvicorn main:app` and the full frontend contract (all endpoints listed in `PROJECT_CONTEXT.md`) were exercised live — see `CHANGELOG.md` for the test log.

**Recommended way to run the backend:** `uvicorn main:app --reload` from inside `backend/`.

### Sub-finding, corrected: route-duplication semantics

The original version of this document stated that when a route path is decorated twice in the same FastAPI file, "FastAPI silently keeps only the last definition." **That was wrong** — verified empirically (`TestClient`/live request against `/api/pqc-ranking`, which had two `@app.get("/api/pqc-ranking")` definitions in `backend/main.py`): Starlette's router matches routes in *registration order* and returns the **first** match, so the *first* `def get_pqc_ranking()` (the richer handler, returning `project`/`report`/`summary`/`mapping_validation`/`top_candidates`/`assets`) was always the one that ran; the second, bare `return load_json(...)` definition was the dead one. That dead duplicate has been removed from `backend/main.py`. (`get_migration_actions` was never actually a duplicate in the buggy sense — it was two *different* route paths, `/api/actions` and `/api/migration-actions`, whose handler functions merely happened to share a Python name; both remain reachable and both were left as-is.)

## 7. Known quirk: fixed CBOM filename

`cbomkit_client.py` always writes the scanned CBOM to `data/keycloak-cbom.json`, and `cbom_parser.py` always reads from that same fixed path — regardless of which GitHub repository was actually analyzed. Functionally this still works for a single analysis at a time (the file is simply overwritten each run), but the name is misleading (a hold-over from the original Keycloak demo repo) and there is no way to keep results from more than one analyzed repository at once, or to tell from the data alone which repository a given `data/ecdat-*.json` snapshot came from (no repository/branch/timestamp metadata is stored anywhere in the JSON outputs).

## 8. Frontend architecture

`App.jsx` is still the single state/effects orchestrator (no router; the sidebar's nav items call `document.querySelector/getElementById(...).scrollIntoView(...)` to jump within one long page — these are real `<button>` elements rather than `<div onClick>`, for keyboard access). State is plain `useState`/`useEffect`/`useCallback`/`useRef` (no Redux/Context/React Query). As of the 2026-09-14 frontend overhaul (§12), `App.jsx` itself renders almost nothing directly — it fetches/derives data and passes it down to `frontend/src/components/`.

Effects: (1) initial dashboard load (`getSummary`, `getAssets`, `getMigrationReportAssets`, and — new in §12 — `getPriority`, all in parallel); (2) per-selected-asset detail load, extracted into a `useCallback`-wrapped `loadAssetDetail` so a failed load can offer a **Retry** button that re-runs the same fetch, rather than a dead-end message; (3) a `setInterval`-based 3-second poll of `/api/analyze/status` while an analysis is running; (4) resets the AI-advisor state to idle whenever `selectedAsset` changes, so a previous asset's AI answer can never bleed into a newly-selected asset's view; (5) an Escape-key listener that closes the full-height asset-detail overlay; (6) (new, §12) a 15-second-interval `getHealth()` poll driving a live `backendConnected` boolean.

The sidebar's connection indicator is now a live health check (§12), not static markup — `TODO.md` item 9 is closed as of this round.

### AI Advisor placement and state machine (2026-09-14)

Previously the AI Advisor was a standalone `<section>` at the very bottom of the page, below the footer-adjacent content, disconnected from the asset detail view except by a shared `selectedAsset` variable. It is now rendered by `components/AIAdvisorPanel.jsx` **inside** the asset-detail overlay, immediately after the top summary stat cards — i.e. the first thing a user sees after risk/priority/complexity/blast-radius, not the last thing on the page. It renders a self-contained data snapshot (asset name, algorithm/primitive, risk, priority, complexity, blast radius, PQC recommendation, source impact — all pulled from the already-fetched `assetDetail`, no extra network call) above the AI CTA/result, so the panel reads as a complete piece of intelligence on its own.

State is an explicit 4-value machine (`aiStatus`: `"idle" | "loading" | "success" | "error"`) instead of the previous three independent booleans/strings (`aiLoading`, `aiError`, `aiAdvice`) that could theoretically disagree with each other. Two correctness properties, both verified with a live headless-browser test (see `CHANGELOG.md`):

- **Duplicate-request guard:** `handleGenerateAIAdvice` early-returns if a request is already `"loading"`, in addition to the button's own `disabled` attribute — defense in depth against re-entrancy (e.g. rapid keyboard activation).
- **Stale-response discard:** a `selectedAssetRef` tracks the currently-selected asset synchronously. If the user switches to a different asset while a request for the previous asset is still in flight, the resolving `.then`/`catch` detects the mismatch and drops the result instead of attributing it to the wrong asset. Selecting a *different* asset also proactively resets `aiStatus`/`aiAdvice`/`aiError` to idle, so a stale success/error block is never left on screen under the wrong asset's heading.

### Component extraction (2026-09-14)

`frontend/src/components/` now holds pieces that used to be defined inline at the top of `App.jsx` or duplicated across it:

- `Badge.jsx` — `SeverityBadge` (one component for risk/priority/complexity/blast-radius/source-impact levels, replacing the previous two parallel implementations, `RiskBadge` and an ad hoc `impact-badge` markup block) and `TagBadge`.
- `StatCard.jsx`, `DistributionBar.jsx` — moved verbatim from `App.jsx` (`DistributionBar` remains unused, exactly as before — it was already dead code in the original file).
- `States.jsx` — `LoadingState`, `ErrorState` (now actually used, for the asset-detail load-failure retry path), `EmptyState` (now used for the "no assets found" table state).
- `AIAdvisorPanel.jsx` — the AI Advisor card described above.

This is presentation-layer extraction only — no new state-management library, no routing change, and `App.jsx` remains the single owner of all application state (props flow one direction into these components; no new global state was introduced).

## 9. CSS design system (rewritten 2026-09-14)

`App.css` was rewritten in place (same file, same className contract — every className the JSX uses was cross-checked against the stylesheet before and after) rather than patched incrementally, because it had accumulated substantial duplication from prior redesign passes: `.asset-detail-panel`, `.detail-card`, `.candidate-ranking-list`/`.candidate-ranking-row`, `.classification-grid`, `.pqc-migration-grid`, `.asset-toolbar`, `.asset-search`, `.clear-search`, and others were each defined 2–4 times in the old file, with the browser's normal cascade rules (later same-specificity rule wins) silently deciding the outcome. It also carried fully dead selectors matching no element in the JSX at all: `.recommendation-box`, `.migration-actions` (plural container), `.migration-action-number/-content/-title/-description`, and `.risk-detail-grid/-item/-label` plus `.risk-score`/`.risk-severity`/`.risk-reason` — all confirmed via `grep` to have zero matching elements before removal.

The rewrite introduces `:root`-level CSS custom properties as the single source of truth for: surface/border/text color tiers, a 4-step severity palette (`--sev-low` green / `--sev-medium` amber / `--sev-high` orange / `--sev-critical` red — previously HIGH and CRITICAL shared the exact same red, `#ef4444`, and were visually indistinguishable), a spacing scale (`--space-1` … `--space-8`), a radius scale (reduced from the old 12–14px cards to 6–10px, a more restrained "enterprise security tool" look per the requested visual direction), and shared shadow/transition tokens. The previous two parallel badge implementations (`.risk-badge`/`.risk-{level}` and `.impact-badge`/`.impact-{level}`) were unified into one `.badge`/`.badge-{low,medium,high,critical,unknown}` family used everywhere a severity/level appears (risk, priority, complexity, blast radius, source impact), driven by the single `SeverityBadge` component (§8). A small `.btn`/`.btn-primary`/`.btn-outline`/`.btn-sm` button system and a global `:focus-visible` outline were added, since neither existed before (buttons were each styled ad hoc per section).

## 10. Risk-scoring unification (2026-09-14)

Mechanically, three changes closed the gap described in §5:

1. **`backend/score_cbom.py` no longer calls `calculate_base_risk()` itself.** It now reads `data/ecdat-explainable-risk.json` (produced by `explain_cbom.py`), looks up each asset by name, and re-projects `risk_assessment.base_risk` into the exact same output shape `ecdat-risk-assessed-assets.json` always had. `/api/risk`/`/api/risk/{name}` in `backend/main.py` were **not modified at all** — they still just `load_json("ecdat-risk-assessed-assets.json")`; the file's schema is unchanged, only its provenance is. Verified: the freshly-regenerated `ecdat-risk-assessed-assets.json` is byte-for-byte identical to the pre-change file for every asset (no numeric drift — the fix closes a *structural* gap, not a *numeric* one, on the current dataset).
2. **`backend/run_pipeline.py` was reordered**: `explain_cbom.py` now runs before `score_cbom.py` (previously `score_cbom.py` → `score_contextual_cbom.py` → `explain_cbom.py`), since `score_cbom.py` now depends on `explain_cbom.py`'s output.
3. **`backend/score_contextual_cbom.py` was removed from the active pipeline** (not deleted — kept on disk with a deprecation docstring, matching how `backend/api/main.py` was handled in §6). It computed a byte-for-byte duplicate of `explain_cbom.py`'s own risk calculation, using the identical hardcoded `RiskContext`, and its output file had zero readers anywhere in the codebase (verified by a repo-wide search before removing it from the pipeline — the AI advisor used to be its one reader, until the earlier 2026-09-14 fix pointed it at the unified migration report instead).

A new stage, **`backend/check_risk_consistency.py`**, now runs last in `run_pipeline.py`. It cross-checks every asset's risk figures in `ecdat-risk-assessed-assets.json` and `ecdat-migration-report.json` against the authoritative `ecdat-explainable-risk.json` record, and **fails the pipeline (exit code 1) if any figure disagrees** — turning a future silent regression (e.g. someone reintroducing an independent risk calculation) into an immediate, loud pipeline failure instead of a subtle dashboard/AI-advisor mismatch discovered by a user. It can also be run standalone: `python check_risk_consistency.py`.

**Not changed:** `data/ecdat-risk-assessed-assets.json` and `data/ecdat-contextual-risk-assets.json` still exist on disk from the last pipeline run (neither file was deleted, per instruction) — the former continues to be regenerated (now via the re-projection above) on every future analysis; the latter is now a frozen snapshot that will never be updated again unless someone manually reruns `score_contextual_cbom.py`. The underlying `RiskContext` defaults were out of scope for this round (fixed separately, see §11) and `/api/risk`'s generic-500 error handling remains open.

## 11. RiskContext contextualization (2026-09-14)

### What `RiskContext` contained, and why it was hardcoded

`models/risk_factors.py`'s `RiskContext` dataclass has five fields: `business_criticality`, `data_lifetime_years`, `migration_time_years`, `exposure`, `quantum_threat_horizon_years`. Before this change, `explain_cbom.py` constructed exactly **one** `RiskContext` object (`business_criticality="MEDIUM"`, `data_lifetime_years=5`, `migration_time_years=2`, `exposure="INTERNAL"`, `quantum_threat_horizon_years=10`) *outside* its per-asset loop and passed the same object to `calculate_contextual_risk()` for every asset. The comment above it literally read `# Current prototype context` — it was a placeholder that was never replaced with anything that read from the CBOM, so every asset in every analyzed repository got the identical assumed business context, no matter what the code actually did.

### Real signals now used, and how they map to `RiskContext`

`backend/services/risk_context.py` (new) adds `derive_risk_context(asset)`, called once per asset inside `explain_cbom.py`'s existing loop (replacing the single shared object). It builds a `RiskContext` from fields already present in `ecdat-classified-assets.json` — the same file `explain_cbom.py` already reads, so this introduces no new pipeline dependency:

| `RiskContext` field | Source signal | Derivation |
|---|---|---|
| `exposure` | CBOM evidence: each occurrence's `location` (file path) and `context` (API-usage string), plus `asset_type` | `INTERNET` if `asset_type` contains `"protocol"`/`"certificate"`, or any occurrence's path/context contains a network keyword (`ssl`, `tls`, `ssh`, `socket`, `http`, `x509`, `certificate`, `handshake`, `net.`); else `INTERNAL`. |
| `business_criticality` | CBOM evidence: occurrence file paths, occurrence count | `LOW` if *every* occurrence is under a test/demo/doc/fixture/vector-style path; `HIGH` if the asset recurs in 5+ distinct occurrences; else `MEDIUM` (the prior universal default, now used only for the genuinely ambiguous case). |
| `migration_time_years` | CBOM evidence: occurrence count; classification `category` | 1/2/4 years by occurrence-count bucket (≤2 / 3–6 / 7+), +1 year if `category` is `asymmetric` or `protocol` (cross-party interoperability tends to slow real migrations), capped at 10. |
| `data_lifetime_years` | *(none — see below)* | Fixed at `5`, via `DEFAULT_DATA_LIFETIME_YEARS`. |
| `quantum_threat_horizon_years` | *(none — see below)* | Fixed at `10`, via `DEFAULT_QUANTUM_THREAT_HORIZON_YEARS`. |

**Two dimensions were deliberately left fixed rather than forced to vary.** `data_lifetime_years` (how long the data a given algorithm protects must stay confidential) and `quantum_threat_horizon_years` (when a cryptographically-relevant quantum computer is expected to exist) are not facts a CBOM can reveal — they are organizational/threat-model assumptions about the future, not observations about the code. Inventing a per-asset value for either (e.g. "this asset touches 3 files, so its data lifetime must be X years") would have been exactly the kind of arbitrary-score fabrication the task asked to avoid. Both constants are now centralized in `services/risk_context.py` with a documented rationale, replacing what used to be duplicated hardcoded literals scattered across `explain_cbom.py` and the now-deprecated `score_contextual_cbom.py`.

### Effect on the calculation itself

**`services/contextual_risk.calculate_contextual_risk()`'s formula and weights were not touched at all** — same 40/20/15/10/10/5% weighting, same severity thresholds. Only *what feeds into it* changed: `context` is now asset-specific instead of one shared object. As a side effect, `services/mosca_analysis.calculate_mosca_risk()`'s "migration urgency" (which combines `data_lifetime_years + migration_time_years` against `quantum_threat_horizon_years`) now also varies per asset, since `migration_time_years` does — an asset with many occurrences and an `asymmetric`/`protocol` category will show a more urgent Mosca timeline than one appearing once in a hash-only context, without any change to `mosca_analysis.py` itself.

**This changes real risk numbers, on purpose.** For example, `RSA-OAEP` in the current dataset only ever occurs in `docs/development/custom-vectors/...` (test-vector generation code, not shipped production source) — so it now derives `business_criticality="LOW"` instead of the old universal `"MEDIUM"`, and its contextual `final_score` dropped from `65.75` (`HIGH`) to `56.75` (`MEDIUM`). That is the fix working as intended: the old number was wrong (it treated test-vector code as equally business-critical as production code, because it never looked); the new number is derived from real evidence of where the asset actually appears. `/api/risk`'s "basic" quantum-only score is unaffected (`calculate_base_risk()` never took a `RiskContext` and still doesn't) — it remains `100`/`CRITICAL` for `RSA-OAEP`, exactly as before.

### Determinism, pipeline safety, and consistency

- **Deterministic**: `derive_risk_context()` is a pure function of the asset dict — no randomness, no I/O, no external calls, no reliance on dict/set iteration order. Verified with a dedicated test (`test_risk_context.py`, `test_deterministic_for_identical_input`).
- **No new pipeline dependency**: reads only fields already inside `ecdat-classified-assets.json`, the same file `explain_cbom.py` already had open — no reordering of `run_pipeline.py` was needed (unlike the risk-unification round).
- **API response shapes unchanged**: `/api/risk`, `/api/priority`, `/api/migration-report/assets`, `/api/asset/{name}`, and `/api/ai/advice` all still return exactly the same JSON shapes as before — only the numeric risk values inside those shapes changed, which is the intended effect of fixing the underlying calculation's input.
- **`check_risk_consistency.py` (§10) still passes** after this change — it verifies that "basic" risk and "contextual" risk stay internally consistent with `ecdat-explainable-risk.json`, which remains true regardless of what `RiskContext` values feed into that file. Re-run after this change: 86/86 figures consistent.

## 12. Frontend UI/UX overhaul (2026-09-14)

### Scope and constraints

This round redesigned the frontend's structure and visual presentation without touching `backend/`, any API response schema, or `frontend/src/api.js` — verified by diff (§8's "Files modified" list in `CHANGELOG.md` for this entry contains no backend paths). The goal was a first-time-viewer-legible product experience (framed in the task brief as a Smart India Hackathon judge's first impression): immediately clear what ECDAT discovers, which assets are dangerous, migration priority, PQC alternatives, how the AI Advisor works, and how repository scanning works — using only data the backend already returns.

### `App.jsx`'s new role

Previously `App.jsx` (~2,308 lines) both held all state and rendered every section inline. It now still owns all state/effects/data-fetching (§8), but delegates essentially all rendering to `frontend/src/components/`. Two additions to the data layer, both reusing pre-existing-but-previously-unwired API functions rather than adding new backend surface:

- `getPriority()` is now fetched alongside the dashboard's other bulk fetches; its per-asset `migration_priority`/`migration_complexity`/`blast_radius` figures are joined (by asset name, client-side) onto the `/api/migration-report/assets` list to produce `enrichedAssets`, which `AssetExplorer` renders. This is why every asset card can show Priority/Complexity/Blast Radius without any new backend call.
- `getHealth()` is now polled every 15 seconds to drive `Sidebar`'s connection indicator (§8), closing `TODO.md` item 9.

### New component set

`frontend/src/components/`:

| Component | Role |
|---|---|
| `HeroOverview.jsx` | Headline, description, an SVG readiness ring (derived from existing `/api/summary` fields — see below), and the 4 top-level stat cards. |
| `PipelineStepper.jsx` | Visualizes the repository-analysis pipeline as 6 conceptual stages. Only ever shows coarse "active/done/failed" states per the backend's actual `/api/analyze/status` granularity — see the caveat in §2/§12's Known limitations. |
| `RepositoryAnalysisPanel.jsx` | Composes the pipeline stepper with the pre-existing repository-URL/branch form (now a real `<form onSubmit>`) and its status banner. |
| `Sidebar.jsx` | Nav + the live health indicator. |
| `AssetFilters.jsx` | Search input + 4 filter selects (unchanged behavior, extracted). |
| `AssetExplorer.jsx` | Card-based asset list (replaces the old `<table>`), each card showing risk/priority/complexity/blast-radius/source-impact severities and a PQC recommendation. |
| `AssetDetailPanel.jsx` | Orchestrates the asset-detail workspace's fixed layout (below). |

**Superseded by §13/§14 and no longer present:** `AnalyticsPanel.jsx` (replaced by `DonutPanel.jsx`, §14) and the original flat `detail/AssetIdentityHeader.jsx`/`RiskPriorityStrip.jsx`/`ImpactAnalysis.jsx`/`PQCRecommendation.jsx`/`MigrationActions.jsx` (replaced by the 2×2 workspace components listed in §13). This row is kept only so a reader following an old commit doesn't go looking for files that no longer exist.

`AIAdvisorPanel.jsx` was modified in place (not replaced) across all three frontend rounds: per-section icons on its parsed-response headings (this round), a compact single-line context strip replacing an 8-item snapshot grid (§13), and an availability-indicator dot/label (§14). Its props, its 4-state machine (`idle/loading/success/error`), and the `POST /api/ai/advice` contract it calls are unchanged from §8's original description throughout.

### Asset-detail layout (superseded by §13 — see there for the current structure)

The section order described in the original version of this round — a flat **Identity → Risk/Priority strip → Impact Analysis → PQC Recommendation → Migration Actions → AI Advisor** stack — was replaced later the same day by the 2×2 workspace grid described in §13. It is recorded here only for history; `AssetDetailPanel.jsx` no longer renders a flat stack.

### "Reuse existing data" in practice

Two numbers on the new hero section are explicitly derived, not newly computed by the backend:

- **Migration readiness %** — `100 - (high_or_critical_priority_assets / total_assets) * 100`, computed client-side from `/api/summary`'s existing `high_or_critical_priority_assets` and `total_assets` fields — i.e. it is *priority*-based, not risk-severity-based. (Corrected 2026-09-15: this bullet previously named `risk_severity_distribution`, which the code never used.) Documented in-code as a transparent percentage of existing data, not a new backend metric.
- **Asset Explorer's per-card Priority/Complexity/Blast Radius** — from the `getPriority()` join described above, not invented.

### Known limitation: pipeline-stage precision

`PipelineStepper` displays 6 named stages purely for narrative/comprehension purposes. The backend's actual `POST /api/analyze` / `GET /api/analyze/status` only ever reports one of `idle/starting/running/completed/failed` (§2) — there is no per-stage progress signal anywhere in the backend. The component does not pretend otherwise: while status is `"running"`, all stages after the first are shown as generically "active" together, not individually sequenced. A future backend change emitting structured per-stage progress would let this become precise; out of scope for this frontend-only round.

## 13. Composition & visual-hierarchy redesign (2026-09-14)

A second frontend-only round, done because the componentized result from §12 still read as a long vertical stack of equal-weight cards rather than a grouped investigation workspace.

> **Superseded layout (2026-09-15):** the 2×2 grid described below is no longer current. An uncommitted, undocumented intermediate 3-column variant (Evidence | Risk | Migration, AI Advisor full-width) replaced it first; the 2026-09-15 round then replaced that with Evidence + Risk Intelligence stacked beside a vertical Migration Path, AI Advisor full-width below — see §15. The three bug write-ups at the end of this section remain accurate history.

**Asset-detail view restructured into a 2×2 grid.** `AssetDetailPanel.jsx` now renders a full-width header band (`detail/AssetHeaderBand.jsx` — identity on the left, a large risk-severity readout on the right, since risk is ECDAT's core signal and previously sat in a same-size card among four others) followed by `.asset-workspace-grid`, a 2-column grid whose 4 children land in this exact order/position:

```
[ Risk & Impact ]      [ Migration Path ]
[ Source & Evidence ]  [ AI Advisor ]
```

- `detail/RiskImpactPanel.jsx` — complexity/blast-radius/source-impact as a secondary metric tier, plus the "why this priority" explanation text.
- `detail/MigrationFlow.jsx` — the migration recommendation as an arrow-connected sequence (`Current Cryptography → Quantum Risk → PQC Candidate → Migration Action`), with ranked alternatives and the full action list behind `<details>` progressive disclosure instead of always-expanded lists.
- `detail/EvidencePanel.jsx` — three quiet file/class/function counters, with the actual affected-file/class/function lists behind a disclosure toggle.
- `AIAdvisorPanel.jsx` — unchanged contract, but its old 8-item snapshot grid was replaced with a single-line context strip so the panel is sized to match its grid neighbor instead of spanning full width as a mega-card.

The five components this replaced (`detail/AssetIdentityHeader.jsx`, `RiskPriorityStrip.jsx`, `ImpactAnalysis.jsx`, `PQCRecommendation.jsx`, `MigrationActions.jsx`) were deleted; their logic was folded into the four components above.

**Dashboard given an asymmetric first-viewport row.** A new `CriticalFindingsPanel.jsx` (top 5 HIGH/CRITICAL assets, ranked client-side by the same severity ordinal every badge uses) sits beside `RepositoryAnalysisPanel` in a `1.6fr / 1fr` grid row (`.dashboard-row-primary`), instead of both stacking full-width. A shared `.section-heading` (eyebrow + title) pattern was introduced for consistent hierarchy across this row, the analytics section, and the Asset Explorer.

**Asset Explorer cards redesigned for severity dominance.** A wide colored left rail plus prominent Risk/Priority badges are now the dominant visual signal per row; Complexity/Blast Radius/Source Impact were demoted to one quiet meta line. HIGH/CRITICAL rows get a restrained background tint.

**Layered background depth** (two restrained radial-gradient glows + a faint masked grid texture) was added to `.app-shell` — refined further in §14.

**Three real bugs were found only by rendering the app in a browser**, none visible from reading the CSS/JSX in isolation:
1. A **modal stacking-context bug** — giving `.main-content` its own `z-index` (for the background layering above) trapped the asset-detail workspace's `position: fixed; z-index: 1000` overlay inside `.main-content`'s local stacking context, so it compared against the sidebar as a whole and rendered *underneath* it. The entire asset identity block was invisible on every asset-detail view until this was found. Fixed by removing the z-index from `.main-content` (only `.sidebar` needs it).
2. A **grid min-width overflow bug** — `.dashboard-row-primary`'s `1.6fr 1fr` columns silently overflowed the viewport (the Critical Findings panel clipped off-screen), because grid items default to `min-width: auto`, which prevents a track from shrinking below its content's intrinsic width. Fixed with an explicit `min-width: 0` on the row's direct children (same fix applied to `.asset-workspace-grid`).
3. A **flex-axis bug** — `.workspace-identity`'s `flex: 1 1 320px` sized it correctly as a width basis in the header's row layout, but once a ≤900px responsive rule switched the header to `flex-direction: column`, that same basis applied to height instead, rendering a 320px-tall, mostly-empty box on mobile widths. Fixed by resetting the flex-basis inside that breakpoint.

## 14. Premium visual-identity redesign (2026-09-14)

A third frontend-only round, targeted specifically at visual identity (color, typography, hero treatment, chart style) rather than structure — the structure from §12/§13 was already correct going in, and nothing in this round touches the DOM structure §13 describes above.

- **Color system made intentional**: `--accent-cyan`/`--accent-cyan-strong` added, reserved specifically for PQC/technology meaning; `--accent-violet` reserved specifically for AI meaning; every existing violet-colored element that actually named a PQC candidate (asset-card PQC text, the migration-flow's PQC node, ranked-candidate badges, the AI Advisor's inline "PQC → ‹candidate›" callout) was retargeted to cyan, while elements representing the AI Advisor itself stayed violet.
- **Hero rewritten**: new headline/copy, a real primary CTA that scrolls to and focuses the repository form, a dependency-free inline-SVG decorative visual, and an asymmetric readiness-card-plus-2×2-tiles layout replacing 4 equal stat cards.
- **Charts converted from bar to donut/ring** (`DonutPanel.jsx` replaces the deleted `AnalyticsPanel.jsx`), colored by the same meaning-based rule as everything else (severity hex values for the two severity-shaped charts; cyan/blue/gray for the non-severity migration-strategy chart).
- **Sidebar nav expanded** from 6 to 9 items (added AI Advisor, Reports) with a restyled, restrained active-state accent bar.
- **AI Advisor gained an availability indicator** (Ready/Analyzing/Unavailable), derived entirely from the existing `idle/loading/success/error` state machine — no new API call, since there is still no Ollama health-check endpoint wired up.

No bugs were found this round — see `CHANGELOG.md`'s test log for the full live-browser verification (responsive sweep at 1440/1280/1024/900/768/400px, zero overflow, zero console errors, multiple assets opened, full AI Advisor round-trip). *(2026-09-15 note: that overflow check compared only page scroll width, so it could not see content clipped inside the fixed sidebar — the collapsed-rail logo was in fact clipped at ≤900px; see §15.)*

## 15. Console-grade visual system & workspace re-composition (2026-09-15)

A fourth frontend-only round, built from a detailed written brief (no reference image was attached to the request). No `backend/` file, API contract, `frontend/src/api.js` function, or npm dependency changed.

### Design tokens (`App.css` `:root`)

| Token group | Use |
|---|---|
| `--font-display` (Space Grotesk) | Headline and dominant numerics only — hero h1, readiness %, stat values, the asset risk score, donut centers, evidence counters. All other text is Inter. Both load via a Google Fonts `@import` (needs network — `TODO.md` #27). |
| `--glass-bg`, `--glass-bg-strong`, `--glass-border`, `--glass-blur` | Translucent blurred surfaces, reserved for the topbar, sidebar, readiness card and the asset-detail header band. |
| `--glow-cyan` / `-blue` / `-violet` / `-critical` / `-high` / `-low` / `-magenta` | Box-shadow glows for signature moments (active nav, primary CTA, severity surfaces on hover, AI identity) — never applied broadly. |
| `--accent-magenta`, `--accent-magenta-strong` | Decorative only (atmosphere, gradient end-stops, one orbital node); never labels a data category. |
| `--shadow-elevated`, `--radius-xl`, eased `--transition-*` | Elevation and motion refinements. |

The §14 color meanings still hold and are enforced more strictly: cyan appears only where a real PQC candidate exists. `.asset-card-pqc-none`, `.critical-finding-pqc-none`, `.flow-node-pqc-none`, `.risk-hero-pqc-none` and `.ai-context-none` render "No direct replacement" / "Not Applicable" in neutral text.

### Background layering

`.app-shell::before` (four radial glows) and `::after` (grid plus two faint diagonal line patterns) are fixed layers at `z-index: -1`, and `body` / `.app-shell` are transparent so the canvas color comes from `html`. At their previous `z-index: 0` the `::after` layer — the shell's last child — painted over every positioned panel. A negative layer only stays visible if no in-flow ancestor paints an opaque background, which is why `body` and `.app-shell` must stay transparent.

### Motion invariants

- Entrance keyframes (`ecdat-rise-in`, `ecdat-scale-in`) animate the individual `translate` / `scale` properties, not `transform`. A filled animation outranks normal declarations, so animating `transform` pinned it and disabled every `:hover` lift.
- `.panel.asset-explorer` has `animation: none`. `AssetDetailPanel`'s fixed, full-viewport overlay renders inside that section, and any transform-type property on it would make the explorer the overlay's containing block and clip it.
- Stagger delays use two-class selectors; a later single-class `animation` shorthand would reset them to 0. A global `prefers-reduced-motion` rule collapses all animation and transition durations.

### Component changes

| Component | Change |
|---|---|
| `Topbar.jsx` (new) | Command bar bound to `App.jsx`'s existing `search` state (same variable as `AssetFilters`). `Ctrl/⌘+K` and `/` focus it; `/` is ignored while another input has focus. Live backend chip; the AI chip is a static model description, not a status claim. |
| `HeroOverview.jsx` | Gradient on the closing words only; orbital SVG (radial core glow, two counter-rotating orbit groups with key nodes); workflow chain relabeled to the brief's stage names; the priority stat card relabeled (see below). |
| `PipelineStepper.jsx` | 7 stages (added "Migration Plan"; kept "AI Ready" because the pipeline never runs the model). Connector spans removed — connectors, lit states and numbered badges are pure CSS (`::before` lines, CSS counters); per-stage identity colors via `pipeline-stage-{key}`. |
| `CriticalFindingsPanel.jsx` | Two-line rows: name / score / risk badge, then "PQC → candidate · Priority X" (replacing two adjacent unlabeled badges). |
| `AssetExplorer.jsx`, `AssetFilters.jsx` | Identity and PQC path share one subline; `not-applicable` label and filter option added. |
| `AssetDetailPanel.jsx` | Wraps Evidence + Risk Intelligence in `.workspace-column`; AI Advisor stays full-width below the grid. |
| `detail/AssetHeaderBand.jsx` | Large severity-colored risk score (only when numeric), severity, migration priority, and PQC recommendation as header facts. |
| `detail/MigrationFlow.jsx` | Vertical decision pathway (`ArrowDown` connectors) — the horizontal flow scrolled and hid its fourth node at 1440px. |
| `detail/EvidencePanel.jsx`, `detail/RiskImpactPanel.jsx` | Heading icons. |
| `AIAdvisorPanel.jsx` | Icon in the CTA and a neutral no-candidate class. State machine, props and API call unchanged. |
| `App.jsx` | Renders `Topbar`; Migration donut gains a "Not Applicable" slice, color and click-to-filter mapping. |

### Asset-detail workspace (current)

```
[ Header band: identity | risk score + severity | priority | PQC recommendation ]
[ Source & Evidence ]  [ Migration Path                                  ]
[ Risk Intelligence ]  [ Current -> Quantum Risk -> PQC -> Action (vertical) ]
[                            AI Advisor                                  ]
```

`.asset-workspace-grid` is `minmax(0, 1fr) minmax(0, 1.1fr)` with `align-items: start` — stretching either column to the other's height is what had left the evidence/risk panels as mostly empty boxes. It becomes a single column at ≤1200px.

### Truthfulness fixes to existing figures

- The stat card titled "High / Critical Risk" always displayed `high_or_critical_priority_assets` (2) while `risk_severity_distribution` has 4 HIGH assets — beside a risk donut reading "4 at risk". It is now titled "High / Critical Priority", with the real risk count as its subtitle. The readiness copy now says "high-priority assets".
- The Migration donut omitted `migration_type_distribution["not-applicable"]` (6), so its ring summed to 23 of 29 assets and those cards read "Not yet classified".

### Responsive behavior

- ≤1300px: the repository / Critical Findings row stacks.
- ≤1200px: metrics go single-column, the hero stays a row with a 170px visual, the workspace goes single-column.
- ≤900px: 76px icon rail (brand text is `display: none` — `font-size: 0` left it ~150px wide and pushed the logo off-screen); each donut panel becomes a full-width row (ring left, legend right).
- ≤650px: hero visual hidden, 30px headline, pipeline becomes a vertical list with vertical connectors, header facts wrap, card subline stacks, and the topbar hides its AI chip and shortcut hint.

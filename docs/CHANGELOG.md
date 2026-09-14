# ECDAT — Changelog

Dated log of meaningful changes to the codebase and to this documentation set. Newest entry first. Every future code change made with Claude Code should add an entry here (see rule at the bottom of `TODO.md`/repo instructions).

---

## 2026-09-14 — Frontend composition & visual-hierarchy redesign (second overhaul round)

**Date:** 2026-09-14

### What changed

A second, narrower redesign pass on top of the frontend overhaul below, triggered by feedback that the componentized result still read as "a stack of cards" rather than a premium investigation workspace — the problem was information architecture and visual composition, not missing pieces.

- **Asset-detail view restructured from a vertical stack into a 2x2 investigation grid.** A full-width header band (identity left, a large "risk hero" readout right — severity rendered once, at 32px, as the single most prominent piece of typography on the page) is followed by a `2fr` grid: **Risk & Impact** | **Migration Path** (top row), **Source & Evidence** | **AI Advisor** (bottom row) — related information grouped into visual regions instead of six equal-weight sections requiring sequential scrolling.
- **Migration Path is now a visual flow** (`Current Cryptography → Quantum Risk → PQC Candidate → Migration Action`, arrow-connected nodes) instead of a paragraph plus a separate card. Ranked alternatives and the full action list moved behind `<details>` progressive disclosure.
- **Source & Evidence demoted to three quiet counters** (files/classes/functions) with the actual file/class/function lists behind a disclosure toggle, so evidence supports the finding instead of forcing a scroll past it.
- **AI Advisor made compact**: the old 8-item snapshot grid was replaced with a single-line context strip ("Analyzing DSA (signature) — HIGH risk, HIGH priority, PQC → ML-DSA-65") that ties the panel to the data beside it, sized to match its grid neighbor instead of spanning full width as a mega-card.
- **Dashboard first viewport made asymmetric**: a new `CriticalFindingsPanel` (top 5 HIGH/CRITICAL assets, ranked) sits beside the repository-analysis panel in a 1.6fr/1fr row, instead of every section stacking full-width. Added a shared `.section-heading` (eyebrow + title) typography pattern used across Critical Findings / Migration Intelligence / Asset Explorer for consistent hierarchy.
- **Asset Explorer cards redesigned for severity dominance**: a wide colored left rail + prominent Risk/Priority badges, with Complexity/Blast Radius/Source Impact demoted to one quiet meta line; HIGH/CRITICAL rows get a restrained background tint so they stand out while scanning the list.
- **Layered background depth** added to the app shell: two restrained radial-gradient glows plus a very faint masked grid texture, fixed behind the sidebar/main content.
- New components: `CriticalFindingsPanel.jsx`, `detail/AssetHeaderBand.jsx`, `detail/RiskImpactPanel.jsx`, `detail/MigrationFlow.jsx`, `detail/EvidencePanel.jsx`. Removed (folded into the above): `detail/AssetIdentityHeader.jsx`, `detail/RiskPriorityStrip.jsx`, `detail/ImpactAnalysis.jsx`, `detail/PQCRecommendation.jsx`, `detail/MigrationActions.jsx`.

### Bugs found and fixed via live browser testing (not visible from source alone)

- **Modal stacking-context bug:** giving `.main-content` its own `z-index` (added in the first overhaul round for background layering) trapped the asset-detail workspace's `position: fixed; z-index: 1000` overlay *inside* `.main-content`'s local stacking context, so it compared against the sidebar as a whole and rendered *underneath* it — the entire asset identity block was invisible, hidden behind the sidebar, on every asset-detail view. Fixed by removing the z-index from `.main-content` (only `.sidebar` needs it).
- **Grid-overflow bug:** `.dashboard-row-primary`'s `1.6fr 1fr` columns silently overflowed the viewport (Critical Findings panel clipped off-screen) because grid items default to `min-width: auto`, which prevents a track from shrinking below its content's intrinsic width. Fixed with `.dashboard-row > * { min-width: 0; }` (same fix applied to `.asset-workspace-grid`).
- **Flex-axis bug:** `.workspace-identity`'s `flex: 1 1 320px` sized it correctly as a *width* basis in the header's row layout, but once the ≤900px responsive rule switched the header to `flex-direction: column`, that same basis applied to *height* instead, rendering a 320px-tall, mostly-empty identity box on mobile widths. Fixed by resetting `.workspace-identity { flex: 0 0 auto; }` inside that breakpoint.

All three were caught only by rendering the app in a real browser and inspecting it — none were visible from reading the CSS/JSX in isolation.

### Files created

- `frontend/src/components/CriticalFindingsPanel.jsx`
- `frontend/src/components/detail/AssetHeaderBand.jsx`, `RiskImpactPanel.jsx`, `MigrationFlow.jsx`, `EvidencePanel.jsx`

### Files removed

- `frontend/src/components/detail/AssetIdentityHeader.jsx`, `RiskPriorityStrip.jsx`, `ImpactAnalysis.jsx`, `PQCRecommendation.jsx`, `MigrationActions.jsx` (content folded into the new components above)

### Files modified

- `frontend/src/App.jsx` — added `criticalFindings` (client-side severity-ranked slice of already-fetched data), restructured the dashboard JSX into the asymmetric row + migration-intelligence section.
- `frontend/src/App.css` — new workspace-grid/migration-flow/critical-findings/section-heading/background-depth CSS; removed all CSS superseded by the new asset-detail structure; reworked asset-card and responsive rules.
- `frontend/src/components/AssetDetailPanel.jsx`, `AssetExplorer.jsx`, `AIAdvisorPanel.jsx` — rewritten/updated to the new composition described above.
- No changes to `frontend/src/api.js`, any `backend/` file, or any API response schema.

### Tests performed

- `npm run build` — succeeds throughout (final: 37.55 kB CSS / 590.07 kB JS; same pre-existing bundle-size advisory as before).
- Live CDP-driven browser testing across: dashboard first viewport, migration-intelligence charts, asset explorer (29 cards, correct severity styling), search filter, empty state, a HIGH-severity asset's full workspace grid (verified 2x2 panel order programmatically), migration-flow node count, evidence progressive disclosure (collapsed by default, opens on click), AI Advisor idle/loading/error/success (including one real transient Ollama 500 correctly caught by the existing error+retry UI, then a successful retry), a simulated CRITICAL severity check (DOM-only class override, confirmed red `--sev-critical` styling renders correctly since no CRITICAL asset exists in the current dataset), and responsive widths 1024/900/400px.
- **Zero console errors, zero warnings, zero uncaught exceptions** in the final clean run. **Zero horizontal overflow** at every tested width.
- Screenshots captured and visually reviewed at each step; the three bugs above were each found by a screenshot or a rect/computed-style check looking wrong, not anticipated in advance.
- Cleanup: dev server (port 5211), headless Chrome (port 9445) and its temporary profile directory, and all `.scratch-*` driver scripts were stopped/deleted after testing; `git status` confirmed clean of test artifacts.

### Known remaining visual weaknesses

- No asset in the current dataset actually has CRITICAL risk severity, so the CRITICAL treatment (avatar, risk-hero, asset-card tint) was verified only via a temporary DOM class override, not a real record — the styling exists and was visually confirmed, but has not been seen end-to-end through a real CRITICAL asset in this environment.
- The migration-flow's four nodes scroll horizontally (`overflow-x: auto`, matching the existing pipeline-stepper pattern) rather than reflowing, on panel widths narrower than ~430px — acceptable but not the most elegant treatment on very cramped desktop widths (fixed by the ≤1200px breakpoint collapsing the grid to one column well before that point in practice).
- Same pre-existing items as the first overhaul round remain open: bundle-size warning, no automated frontend test suite.

---

## 2026-09-14 — Frontend UI/UX overhaul (dedicated redesign phase)

**Date:** 2026-09-14

### What changed

A dedicated, large-scope redesign of the entire frontend, done separately from (and after) the AI Advisor UI/UX integration + dashboard visual redesign entry below — that earlier round restyled the existing structure in place; this round restructured the page itself into a componentized, judge-presentable product experience while preserving every existing API contract and backend behavior untouched.

**Structural rewrite:**
- `frontend/src/App.jsx` rewritten from a ~2,308-line monolith into a lean orchestrator: state/effects/data-fetching remain centralized (nothing moved to a state-management library — still plain `useState`/`useEffect`/`useCallback`/`useRef`), but all rendering is delegated to new components.
- Added a parallel `getPriority()` fetch to the initial dashboard load (alongside the pre-existing `getSummary`/`getAssets`/`getMigrationReportAssets`) and a 15-second-interval `getHealth()` poll feeding a live `backendConnected` boolean — both API functions already existed in `frontend/src/api.js` and were previously unused by the UI; no new endpoint, no `api.js` change.
- Built `enrichedAssets` by joining the existing `/api/migration-report/assets` list with the existing `/api/priority` list by asset name, client-side, adding per-row priority/complexity/blast-radius severity to the asset list without any new backend call or invented metric.
- Computed a "migration readiness" percentage as a transparent, explicitly-commented derivation of two pre-existing `/api/summary` fields (`100 - (high_or_critical / total_assets) * 100`) — not a new backend metric.

**New components (`frontend/src/components/`):**
- `HeroOverview.jsx` — hero section: eyebrow label, headline, description, an SVG readiness ring, and the 4 top-level stat cards (extended `StatCard.jsx` with an optional `tone` prop for critical/accent styling).
- `PipelineStepper.jsx` — visualizes the repository-analysis pipeline as 6 conceptual stages (Repository → CBOMKit Scan → Crypto Discovery → Risk Assessment → PQC Mapping → AI Ready). Deliberately marks all stages after the first as generically "active" together while status is `"running"`, rather than claiming per-stage precision the backend's coarse `idle/starting/running/completed/failed` status does not provide — an explicit honesty constraint, documented in-code.
- `RepositoryAnalysisPanel.jsx` — composes an icon header, the pipeline stepper, and the existing repository-URL/branch form (now a real `<form onSubmit>` instead of a plain `<div>`) with its status banner.
- `AnalyticsPanel.jsx` — generic chart-panel component replacing three near-duplicated inline Recharts blocks (Risk Distribution / Migration Distribution / Source Impact), parameterized by icon/title/description/data/color.
- `Sidebar.jsx` — extracted sidebar nav, now also rendering the live `backendConnected` state (a `connection-dot-down` style + "Backend Unreachable" text when the health poll fails), replacing the previously-static "Backend Connected" markup (`TODO.md` item 9 — see Known issues; this closes it).
- `AssetFilters.jsx` — extracted search input + 4 filter `<select>`s, same `aria-label`s as before.
- `AssetExplorer.jsx` — replaces the old `<table>`-based asset list with a card-list (`.asset-card`), each card showing a risk-severity-colored left border and a metrics row (Risk / Priority / Complexity / Blast Radius / Source Impact via `SeverityBadge`, plus PQC recommendation text) — i.e. each asset "reads like a small security assessment" instead of a spreadsheet row.
- `AssetDetailPanel.jsx` — new orchestrator composing the asset-detail overlay in an explicit required order: Identity → Risk/Priority strip → Impact Analysis → PQC Recommendation → Migration Actions → AI Advisor.
- `detail/AssetIdentityHeader.jsx` — asset identity section (category/primitive/quantum status + a risk-reason sentence with an inline severity badge).
- `detail/RiskPriorityStrip.jsx` — the Risk/Priority/Complexity/Blast Radius summary cards, plus a new `.priority-explanation` paragraph surfacing `migration_priority.explanation.summary`/`.reasons` from the existing `/api/priority` response — real backend data that was already being returned but was not previously rendered anywhere in the UI.
- `detail/ImpactAnalysis.jsx` — source-impact stats and affected file/class/function lists (previously inline in `App.jsx`).
- `detail/PQCRecommendation.jsx` — merges what were three separate cards (migration-type info, PQC recommendation, ranked-candidate list) into one card with a "Ranked Alternatives" subheading.
- `detail/MigrationActions.jsx` — numbered migration action list (previously inline).
- `AIAdvisorPanel.jsx` — modified, not rewritten (props/API contract unchanged): added per-section icons (`Gauge`/`Target`/`Shield`/`ListChecks`/`Activity`/`Sparkles` for RISK/MIGRATION/PQC/ACTIONS/IMPACT/SUMMARY) to the parsed response headings, and updated the descriptive copy under the panel heading.

**Visual design (`frontend/src/App.css`):**
- Removed genuinely dead rules, verified by cross-checking className usage against the JSX (distinguishing static `className="..."` literals from dynamic template-literal classes like `` `badge-${tone}` ``, which a naive grep would false-positive as unused): `.asset-table`, `.table-header`, `.table-row` (+ its responsive override), `.asset-name`, `.muted`, `.topbar` (+ its `h1` + responsive override), `.page-description`, `.status-pill`, `.detail-section-header` (+ children), `.current-risk-grid` (+ responsive override). Renamed `.asset-panel` → `.asset-explorer`.
- Added new sections for every new component above: `.hero*` (eyebrow/intro/readiness ring+meter with tone-colored SVG stroke), `.pipeline-stepper`/`.pipeline-step*` (with a pulse animation for the active state), `.repository-analysis-icon`, `.analytics-panel-chart`, `.asset-card*` (including `.risk-accent-{low,medium,high,critical}` left-border variants), `.stat-card-critical`/`.stat-card-accent` tone variants, `.connection-dot-down`, `.identity-risk-reason`/`.identity-vulnerable`, `.priority-explanation*`, `.pqc-ranking-heading`.
- Updated the existing 650px responsive breakpoint block: removed the now-dead `.topbar`/`.table-*` overrides, added mobile-appropriate rules for every new section (`.hero-intro h1` font-size, `.hero-readiness` wrapping, `.repository-analysis-header`/`.asset-card`/`.pipeline-stepper` stacking to a single column).
- Design direction actually applied: dark theme retained and refined (existing token system from the prior visual-redesign round extended, not replaced), restrained borders/gradients (no new neon or heavy glow effects added), 6–10px radii kept consistent with the prior round's "enterprise security tool" direction, meaningful `lucide-react` icons on every new panel/section, and a `:focus-visible` outline (added in the prior round) verified to still apply to every new interactive element.

### Why

The task asked for a substantial, professional redesign — not a cosmetic pass — so that a first-time viewer (framed as a Smart India Hackathon judge) can immediately understand what ECDAT does, which assets are dangerous, which to migrate first, what PQC alternatives exist, how the AI Advisor helps, and how repository scanning works, while preserving every existing API contract, backend behavior, and piece of existing functionality. Explicit design constraints: reuse existing data instead of inventing new metrics, keep the plain React/Vite architecture (no new UI framework, no router), and make firm design decisions rather than deferring every visual choice back to the user.

### Files created

- `frontend/src/components/HeroOverview.jsx`, `PipelineStepper.jsx`, `RepositoryAnalysisPanel.jsx`, `AnalyticsPanel.jsx`, `Sidebar.jsx`, `AssetFilters.jsx`, `AssetExplorer.jsx`, `AssetDetailPanel.jsx`
- `frontend/src/components/detail/AssetIdentityHeader.jsx`, `RiskPriorityStrip.jsx`, `ImpactAnalysis.jsx`, `PQCRecommendation.jsx`, `MigrationActions.jsx`

### Files modified

- `frontend/src/App.jsx` — rewritten as a lean orchestrator delegating to the components above; added the `getPriority()` fetch, the `getHealth()` polling effect, and the `enrichedAssets` join; all pre-existing handlers/effects (`handleGenerateAIAdvice`, `handleAnalyzeRepository`, Escape-key close, 3-second analysis-status polling, stale-AI-response guard) preserved verbatim in logic.
- `frontend/src/App.css` — dead-rule removal + new sections, described above.
- `frontend/src/components/StatCard.jsx` — added optional `tone` prop.
- `frontend/src/components/AIAdvisorPanel.jsx` — added per-section icons and updated header copy; state machine, props, and API contract unchanged.
- No changes to `frontend/src/api.js`, `frontend/src/index.css`, `frontend/src/main.jsx`, `frontend/package.json`, or any `backend/` file, any API response schema, or any `data/*.json` file.

### Tests performed

- `npm run build` (`vite build`) — succeeded twice (once mid-refactor to confirm no import/structural errors, once final): final bundle 31.93 kB CSS / 588.40 kB JS (single-chunk size warning is pre-existing, see `TODO.md` item 12, unaddressed here for the same out-of-scope reason as before).
- **Live, real browser end-to-end verification**, same dependency-free technique as the prior UI round (a locally-launched headless Chrome driven over the Chrome DevTools Protocol from a throwaway Node script using only built-in `fetch`/`WebSocket`; script deleted after use, verified gone): ran the real FastAPI backend and a fresh Vite dev server, then verified, against the live running app and a real local Ollama (`qwen3:14b`):
  - Hero heading, readiness percentage (93%), and all 4 stat-card values render correctly.
  - Pipeline stepper renders all 6 correctly labeled stages.
  - Asset Explorer renders 29 cards, matching `/api/summary`'s `total_assets`.
  - Search filtering ("rsa") correctly narrows the card list.
  - Selecting an asset opens the detail panel with the correct heading, and the rendered section order exactly matches the required hierarchy (Identity → Risk/Priority strip → Source Impact → PQC → Migration Actions → AI Advisor), verified programmatically via `document.querySelector('.asset-detail-panel').children`'s className list, not just visually.
  - AI Advisor idle button text, loading text, and a full live round-trip against Ollama (real response, all 6 section-heading icons present) all matched exactly.
  - Close button and section navigation work correctly.
  - Responsive emulation at 900px and 400px viewport widths: zero horizontal overflow (`scrollWidth > clientWidth` false at both).
  - **Zero console errors, zero console warnings, zero uncaught page exceptions** across the entire run.
- Screenshots captured at each step for visual review (hero, repository-analysis panel with pipeline stepper, analytics charts, asset explorer card list, search-filtered state, asset-detail top/AI sections, AI loading/result states, both responsive breakpoints) — reviewed and confirmed to show the intended restrained dark cybersecurity aesthetic with no visual defects.
- Test-infrastructure cleanup performed after verification: the Vite dev server (port 5210) and the headless Chrome debug instance (port 9444) used for this round's testing were stopped; the throwaway CDP driver script (`frontend/.scratch-cdp-driver2.mjs`) was deleted; confirmed via `git status` that no scratch/test artifacts remain untracked. The long-standing unattributable process on port 8000 (see `TODO.md` item 13) was left untouched, per the standing note not to force-kill it.

### Known issues / remaining limitations

- `PipelineStepper`'s stage-by-stage visualization is honest about its own limits: because `/api/analyze/status` only ever reports `idle/starting/running/completed/failed` with no per-stage telemetry, the component cannot and does not claim to know which of the 6 displayed stages is currently executing during `"running"` — it shows all of them as generically active together. A future backend change to report structured per-stage progress would let this become precise instead of approximate.
- No automated regression tests were added for any of the new components — as with the prior UI round, verification was live/manual via the CDP driver script (see above) and would need to be re-run manually after future related changes. (Same open item as `TODO.md` #8.)
- The bundle-size warning (now 588.40 kB, up slightly from ~582 kB) remains unaddressed — same out-of-scope reasoning as the prior round (`TODO.md` item 12); component extraction in this round was presentation-layer only and did not introduce code-splitting.
- All previously-open items in `TODO.md` not specifically closed by this round (dependency manifest, generic AI-advisor error handling, fixed CBOM filename, backup/duplicate file clutter, no AI cancel/streaming, hardcoded service URLs, stale integration tests, the port-8000 mystery process, blast-radius ordering non-determinism, `test_pqc_mapper.py`'s Unicode crash, `RiskContext`'s remaining fixed constants) remain open and unaffected by this frontend-only round.

### Closed by this round

- `TODO.md` item 9 ("Sidebar 'Backend Connected' indicator is static markup, not a live health check") — `Sidebar.jsx` now reflects a real 15-second `getHealth()` poll.

---

## 2026-09-14 — RiskContext contextualization (Phase 4A)

**Date:** 2026-09-14

### What changed

**Traced first (no code changes during tracing):**
- Read `models/risk_factors.py` fresh: `RiskContext` is a 5-field dataclass (`business_criticality`, `data_lifetime_years`, `migration_time_years`, `exposure`, `quantum_threat_horizon_years`) with its own sensible-looking defaults — but those defaults were never the issue; the issue was that `explain_cbom.py` constructed exactly **one** `RiskContext` object *outside* its per-asset loop (comment: `# Current prototype context`) and passed the same object to `calculate_contextual_risk()` for every single asset, regardless of that asset's actual evidence.
- Read `services/contextual_risk.py`'s formula in full before changing anything: quantum risk 40% / business criticality 20% / data lifetime 15% / exposure 10% / migration time 10% / evidence quality 5%, feeding into `mosca_analysis.py`'s urgency timeline. **This formula and its weights were not modified.**
- Inventoried what real, per-asset signals `ecdat-classified-assets.json` (the file `explain_cbom.py` already reads, before any downstream stage runs) actually contains: `occurrences` (each with a CBOM-recorded `location` file path and `context` API-usage string), `asset_type`, and `classification.category`/`purpose`. Confirmed by inspecting the real dataset (`pyca/cryptography`) that these fields contain genuinely discriminating signal — e.g. `RSA-OAEP`'s only evidence is under `docs/development/custom-vectors/...` (test-vector generation, not shipped source), while other assets appear under `src/cryptography/hazmat/...` (real library source) or `.../serialization/ssh.py` (a network protocol).
- Confirmed only `explain_cbom.py` (active) and the deprecated `score_contextual_cbom.py` (inactive, left alone) construct `RiskContext` in production code; `test_mosca.py`/`test_contextual_risk.py` construct their own contexts to unit-test the formula directly and needed no changes.

**Then implemented:**
- Added `backend/services/risk_context.py` (new): `derive_risk_context(asset)`, a pure function that builds a `RiskContext` from that asset's own CBOM evidence:
  - `exposure` — `INTERNET` if `asset_type` indicates a protocol/certificate, or any occurrence's file path/API-context string contains a network keyword (`ssl`, `tls`, `ssh`, `socket`, `http`, `x509`, `certificate`, `handshake`, `net.`); else `INTERNAL`.
  - `business_criticality` — `LOW` if every occurrence is under a test/demo/doc/fixture/vector-style path; `HIGH` if the asset recurs across 5+ distinct occurrences; else `MEDIUM` (the prior universal default, now reserved for the genuinely ambiguous case).
  - `migration_time_years` — scales 1/2/4 years by occurrence-count bucket, +1 year for `asymmetric`/`protocol` categories (cross-party interoperability), capped at 10.
  - `data_lifetime_years` and `quantum_threat_horizon_years` — **deliberately left as fixed, centralized, documented constants** (5 and 10, matching the prior defaults). Neither is a fact observable in a CBOM (they're assumptions about the future — how long protected data stays sensitive, and when quantum computers become a threat), so deriving a fake per-asset value for either would have been exactly the kind of "invent an arbitrary score to look contextual" the task explicitly said not to do.
- Updated `backend/explain_cbom.py`: removed the single shared `RiskContext(...)` construction; calls `derive_risk_context(asset)` inside the existing per-asset loop instead. No other line of `explain_cbom.py`'s control flow changed.
- Added `backend/test_risk_context.py` (new, 8 tests, matching the existing plain-assert script convention used by `test_risk.py`/`test_contextual_risk.py`/`test_mosca.py`): network-exposure detection, internal-only default, test-vector-only → LOW criticality, high-occurrence → HIGH criticality, ambiguous → MEDIUM criticality, migration-time scaling by usage/category, determinism for identical input, and confirmation that the two fixed dimensions never vary per asset.

### Why

`docs/TODO.md` (High Priority item 1) had flagged that `RiskContext` defaults were hardcoded and identical for every asset in every repository, undermining the "contextual" framing shown to users. The task asked for a project-aware `RiskContext` built only from real, already-available signals — not invented scores — while preserving the existing formula, API shapes, and the risk-consistency guarantee from the prior round.

### Files modified

- `backend/services/risk_context.py` — new.
- `backend/explain_cbom.py` — per-asset context derivation instead of one shared object.
- `backend/test_risk_context.py` — new.
- `data/ecdat-explainable-risk.json`, `ecdat-blast-radius.json`, `ecdat-migration-complexity.json`, `ecdat-migration-priority.json`, `ecdat-migration-report.json`, `ecdat-pqc-migration.json`, `ecdat-pqc-ranked.json`, `ecdat-pqc-migration-plan.json` — regenerated by re-running the full pipeline (contextual risk scores legitimately changed for assets whose real evidence differs from the old universal assumption; `ecdat-risk-assessed-assets.json` and `ecdat-migration-actions.json` did **not** change, as expected — see Tests performed).
- `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/TODO.md` — updated.
- No changes to `backend/main.py`, `backend/services/contextual_risk.py` (the formula/weights), `backend/services/mosca_analysis.py`, any API response schema, `backend/run_pipeline.py`'s stage list/order, or `frontend/`.

### Tests performed

- `python test_risk_context.py` — all 8 new tests pass.
- Re-ran `test_risk.py`, `test_contextual_risk.py`, `test_mosca.py`, `test_migration_priority.py` — all still pass with identical output to before, confirming the underlying formula (`calculate_contextual_risk`, `calculate_mosca_risk`) was not altered.
- Ran the full pipeline end-to-end via `python run_pipeline.py`: all 13 stages, including the risk consistency check, reported `SUCCESS`.
- Ran `check_risk_consistency.py` standalone after the pipeline run: **86/86 risk figures still consistent with the authoritative source** — confirms the consistency guarantee from the prior round survives this change (it verifies internal agreement between files, which holds regardless of what feeds the authoritative computation).
- Inspected the regenerated `ecdat-explainable-risk.json` directly: **8 distinct `(business_criticality, exposure, migration_time_years)` combinations** now appear across the dataset (previously exactly 1, always). Spot-checked `RSA-OAEP`: now derives `business_criticality="LOW"` (all its evidence is under `docs/development/custom-vectors/...`), and its contextual `final_score` correctly dropped from `65.75` (`HIGH`) to `56.75` (`MEDIUM`) as a direct, explainable consequence.
- Started the backend and tested every endpoint the task specified, for `RSA-OAEP`:
  - `/api/summary` — 200; distribution counts shifted as expected (`risk_severity_distribution` now shows more `MEDIUM`/fewer `HIGH` assets, consistent with several assets' evidence pointing to non-production/test-vector paths).
  - `/api/risk/RSA-OAEP` — 200; **unchanged**: `{score: 100, severity: "CRITICAL"}` — correct, since the "basic" quantum-only score never depended on `RiskContext` at all.
  - `/api/priority/RSA-OAEP` — 200; `quantum_risk.score` now `56.75`/`MEDIUM` (previously `65.75`/`HIGH`), correctly propagated.
  - `/api/migration-report/assets` — 200; `RSA-OAEP`: `{risk_score: 56.75, risk_severity: "MEDIUM"}` — matches.
  - `/api/asset/RSA-OAEP` — 200; `current_risk: {score: 56.75, severity: "MEDIUM"}` — matches exactly.
  - `POST /api/ai/advice {"asset": "RSA-OAEP"}` — live call against real local Ollama `qwen3:14b` (44s): RISK section states "a medium risk score of 56.75" — **exactly matching every other surface's new number**, confirming the consistency guarantee holds end-to-end through the AI advisor too, not just the deterministic API layer.
- **Repository analysis:** same limitation as prior rounds — CBOMKit is not running in this environment, so the CBOMKit-scan half of `POST /api/analyze` could not be exercised. The local half (the entire 13-stage pipeline, which is what this change actually touches) was run directly and verified above.

### Known issues / remaining limitations

- The heuristics in `services/risk_context.py` are deliberately simple and keyword-based (documented, auditable, deterministic) rather than a sophisticated static-analysis pass — e.g. a file merely named `test_helpers.py` inside an otherwise-production directory would be caught by the `LOW_CRITICALITY_PATH_KEYWORDS` "test" keyword even if it's actually shared production tooling. This is a reasonable, transparent first approximation, not a claim of perfect accuracy.
- `data_lifetime_years` and `quantum_threat_horizon_years` remain global constants by design (see "Why" above) — a future round could make these configurable per analysis (e.g. an optional field on `POST /api/analyze`) without touching this round's per-asset derivation logic, but that was out of scope here (frontend changes were explicitly excluded from this phase).
- All limitations already logged in `TODO.md` from prior rounds (no `requirements.txt`, generic `/api/ai/advice` error handling, the port-8000 mystery process, `generate_blast_radius.py`'s ordering non-determinism, `test_pqc_mapper.py`'s Unicode crash, etc.) remain open and unaffected by this round.

---

## 2026-09-14 — Backend risk-scoring unification

**Date:** 2026-09-14

### What changed

**Traced first (no code changes during tracing):**
- Confirmed, by reading every stage script fresh rather than trusting prior documentation, that `explain_cbom.py` was already the sole input to every downstream pipeline stage (`generate_blast_radius.py`, `generate_migration_complexity.py`, `generate_migration_priority.py`, `generate_pqc_migration.py`, `generate_pqc_ranking.py`, `generate_pqc_migration_plan.py`, `generate_migration_actions.py`, `generate_migration_report.py`) — all read `ecdat-explainable-risk.json` and nothing else for risk.
- Confirmed `score_cbom.py` independently called `services/risk_engine.calculate_base_risk()` a second time, writing `ecdat-risk-assessed-assets.json`, read only by `backend/main.py`'s `/api/risk`, `/api/risk/{name}`, and (as a fallback) `/api/asset/{name}`.
- Confirmed (repo-wide search) that `score_contextual_cbom.py`'s output, `ecdat-contextual-risk-assets.json`, had **zero readers anywhere in the active codebase** — its one former reader, the AI advisor, was already redirected to the unified migration report in an earlier round.
- Confirmed the AI advisor (`services/ai_advisor.py`) already read only `ecdat-migration-report.json` — unaffected by, and not requiring changes for, this round.
- Empirically verified, on the current dataset, that all three pipelines' numbers already agreed (0 mismatches across 29–57 assets, depending on file) — i.e. there was no *currently observable* bug, only an *architectural* one: nothing enforced the agreement, so a future change to any one of the three code paths could have silently introduced a real mismatch.

**Then fixed:**
- Rewrote `backend/score_cbom.py` to stop calling `calculate_base_risk()` itself. It now reads `ecdat-explainable-risk.json` and re-projects each asset's `risk_assessment.base_risk` into the exact same `ecdat-risk-assessed-assets.json` shape as before — same file, same schema, same `/api/risk` response format, only the provenance changed.
- Reordered `backend/run_pipeline.py` so `explain_cbom.py` runs before `score_cbom.py` (previously the reverse), since `score_cbom.py` now depends on `explain_cbom.py`'s output.
- Removed `score_contextual_cbom.py` from the active pipeline stage list (not deleted — kept on disk with a deprecation docstring, the same pattern used for `backend/api/main.py` in an earlier round).
- Added `backend/check_risk_consistency.py`, a new script that cross-checks every asset's risk figures in `ecdat-risk-assessed-assets.json` and `ecdat-migration-report.json` against the authoritative `ecdat-explainable-risk.json`, and added it as the final stage of `run_pipeline.py` — a future regression now fails the pipeline loudly (exit code 1) instead of shipping a silent inconsistency.
- **Incidental fix, discovered because it blocked full pipeline verification:** `backend/generate_migration_actions.py` crashed with `UnicodeEncodeError` on a Unicode arrow character (`→`) in an informational `print()` statement when run under Windows' default `cp1252` console encoding — a pre-existing bug unrelated to risk scoring (the actual output file was already written correctly before the crash; only the summary print failed). Fixed by replacing the arrow with ASCII (`->`). Confirmed the same pattern also crashes `test_pqc_mapper.py` (not fixed — out of scope, logged in `TODO.md`).

### Why

`docs/TODO.md` (High Priority item 1) had flagged that the pipeline computed risk three separate, unreconciled times, and that nothing guaranteed `/api/risk` would stay numerically consistent with everything else if any of the three code paths ever changed independently. The task asked for exactly one authoritative risk-scoring pipeline, achieved with the smallest safe change: no API response format changes, no data files deleted, no frontend changes, and the existing `services/risk_engine.py`/`services/contextual_risk.py` calculation logic itself untouched — only *how many times, and from where,* that logic gets invoked.

### Files modified

- `backend/score_cbom.py` — rewritten to re-project from the authoritative dataset instead of recomputing independently.
- `backend/score_contextual_cbom.py` — deprecation docstring added; not deleted.
- `backend/run_pipeline.py` — stage list reordered and reduced (13 → 12 data-generation stages + 1 consistency-check stage); `score_contextual_cbom.py` removed.
- `backend/generate_migration_actions.py` — one Unicode-character fix in a print statement (unrelated incidental bug, fixed because it blocked full pipeline testing).
- `backend/check_risk_consistency.py` — new.
- `data/ecdat-risk-assessed-assets.json`, `data/ecdat-explainable-risk.json`, and 10 other `data/ecdat-*.json` files — regenerated by re-running the full pipeline end-to-end as part of testing (see below); **not deleted**, and `data/ecdat-contextual-risk-assets.json` was deliberately left un-regenerated (frozen from the last run, since its stage no longer runs).
- `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/AI_ADVISOR.md`, `docs/TODO.md`, `docs/CHANGELOG.md` — updated.
- No changes to `backend/main.py`, `frontend/`, or any API response schema.

### Tests performed

- **Empirical pre-change audit:** wrote a one-off comparison (not committed — superseded by the permanent `check_risk_consistency.py`) confirming `ecdat-risk-assessed-assets.json` vs. `ecdat-explainable-risk.json`'s `base_risk` and `ecdat-contextual-risk-assets.json` vs. `ecdat-explainable-risk.json`'s `final_score` had **0 mismatches** across the then-current dataset, before making any code change — establishing that the fix addresses a structural risk, not a currently-visible bug.
- Ran the full pipeline end-to-end via `python run_pipeline.py`: all 13 stages (including the new consistency check) reported `SUCCESS`; final run printed "All risk figures are consistent with the authoritative source" after checking 86 risk figures (57 from `ecdat-risk-assessed-assets.json` + 29 from `ecdat-migration-report.json`).
- Ran `check_risk_consistency.py` standalone — same result.
- Diffed `data/` against git after the full pipeline re-run: **`ecdat-risk-assessed-assets.json` and `ecdat-explainable-risk.json` (and every other pipeline output except two) are byte-for-byte identical to before** — direct proof the fix changed *provenance*, not *values*. `ecdat-blast-radius.json` and `ecdat-migration-priority.json` showed diffs, but inspection confirmed they were pure list-ordering differences (same UUIDs/assets, same scores, different array order) caused by Python's per-process string-hash randomization affecting `set`/`dict` iteration order inside `generate_blast_radius.py`'s dependency-graph code — a pre-existing non-determinism bug, unrelated to and unmodified by this change (verified: neither file's generator script was touched). Logged in `TODO.md`.
- Started the backend (`uvicorn main:app`) and tested every endpoint the task specified:
  - `/api/summary` — 200, unchanged shape (`total_assets: 29`, etc.).
  - `/api/risk` — 200; sampled `RSA-OAEP`: `{score: 100, severity: "CRITICAL"}` (quantum-only "basic" score).
  - `/api/risk/RSA-OAEP` — 200, same figure as above.
  - `/api/priority` — 200, unchanged shape.
  - `/api/migration-report/assets` — 200; `RSA-OAEP`: `{risk_score: 65.75, risk_severity: "HIGH"}` (contextual score — deliberately a *different* number from the basic score above, per design).
  - `/api/asset/RSA-OAEP` — 200; `current_risk: {score: 65.75, severity: "HIGH"}` — matches the migration-report figure exactly.
  - `POST /api/ai/advice {"asset": "RSA-OAEP"}` — live call against the real local Ollama `qwen3:14b` (42.5s): returned a correctly-sectioned answer whose RISK section describes "a high risk score and severity level" — consistent with the `65.75`/`HIGH` contextual figure every other surface shows for this asset.
  - Cross-checked directly against `data/ecdat-explainable-risk.json` for `RSA-OAEP`: `base_risk = {100, CRITICAL}`, `final_score/severity = {65.75, HIGH}` — exactly matching `/api/risk` and everywhere-else, respectively. This closes the loop: **every risk-reporting surface for one specific asset was verified to trace back to the single authoritative record.**
  - Ran the existing service-level test scripts `test_risk.py`, `test_contextual_risk.py`, `test_mosca.py`, `test_migration_priority.py` — all pass, confirming no regression in the underlying calculation logic itself (which was not touched).
  - Re-ran `test_api_validation.py` — fails at the same pre-existing assertion as before (`total_assets == 59` vs. actual 57), confirming this round introduced no new regression in that already-known-stale suite.
- **Repository analysis:** CBOMKit is not running in this environment, so the CBOMKit-scan half of `POST /api/analyze` could not be exercised end-to-end (same limitation as prior rounds). Instead, the *entire local half* of what a repository analysis does — `run_pipeline.py`'s 13 stages against the existing `data/keycloak-cbom.json` — was run directly and verified above, which is the part relevant to this task (the reordering and the new consistency gate).

### Known issues

- `RiskContext` defaults (`backend/models/risk_factors.py`) are still hardcoded and identical for every repository — "contextual" risk still isn't actually contextual. Unchanged, still open (`TODO.md`).
- `/api/risk`'s generic exception handling and the basic-vs-contextual naming/labeling inconsistencies inside `generate_migration_priority.py`'s output (it labels the contextual final score `"quantum_risk"`) were not touched — cosmetic/pre-existing, out of scope.
- **Newly discovered:** `generate_blast_radius.py`'s dependency-graph code produces non-deterministic array *ordering* (not values) across separate process runs, due to Python's string-hash randomization affecting internal `set`/`dict` iteration. Confirmed pre-existing and unrelated to this round's changes (the script was not touched). Logged in `TODO.md`.
- **Newly discovered:** `test_pqc_mapper.py` crashes with the same `UnicodeEncodeError`-on-Windows-console pattern as the `generate_migration_actions.py` bug fixed this round, but in a different file that was not touched (out of scope for this round). Logged in `TODO.md`.
- `data/ecdat-contextual-risk-assets.json` is now a frozen artifact from the last pipeline run before this change — it will not be updated by future analyses unless someone manually runs the now-deprecated `score_contextual_cbom.py`. Not deleted, per instruction; a candidate for manual cleanup once confirmed truly unused by anything outside this repository.
- The mysterious unattributable process still observed holding `127.0.0.1:8000` (first noticed in the prior round) was still present during this round's testing and still could not be identified or stopped; harmless since `main.py` has no in-memory caching (any process serving that port reflects current disk state regardless of when it started), but still worth the user checking manually per the prior round's note.

---

## 2026-09-14 — AI Advisor UI/UX integration + dashboard visual redesign

**Date:** 2026-09-14

### What changed

**AI Advisor integration:**
- Moved the AI Migration Advisor from a standalone `<section>` at the bottom of the page into the asset-detail overlay, rendered immediately after the risk/priority/complexity/blast-radius summary cards, via a new `AIAdvisorPanel` component.
- The panel now shows a factual data snapshot — **asset name, algorithm/primitive, risk, priority, complexity, blast radius, PQC recommendation, and source impact** — sourced from the already-fetched asset detail (no extra API call), directly above the AI-generated text.
- Replaced three independent AI state variables (`aiLoading`, `aiError`, `aiAdvice`) with one explicit state machine (`aiStatus`: `idle | loading | success | error`) with exact required copy: idle button "Get AI Recommendation"; loading text "Qwen3:14b is analyzing this cryptographic asset..."; a dedicated **Retry** button in the error state; a **Regenerate** button in the success state.
- Added a duplicate-request guard in `handleGenerateAIAdvice` (checked in code, not just via the button's `disabled` attribute).
- Fixed a real race condition: switching to a different asset while an AI request for the previous asset was still in flight could show the wrong asset's result. Fixed with a `selectedAssetRef` that the in-flight request checks before committing its result, plus an effect that resets AI state to idle whenever `selectedAsset` changes.
- Confirmed (and did not need to change) that AI generation never blocks the rest of the dashboard — verified live that the sidebar remains clickable during a real ~33–49s Ollama call.

**Dashboard visual redesign (professional cybersecurity aesthetic):**
- Extracted `StatCard`, `DistributionBar` (still unused, as before), a unified `SeverityBadge`/`TagBadge` (replacing the previous two parallel badge implementations — `RiskBadge` plus an ad hoc `impact-badge` block), `LoadingState`/`ErrorState`/`EmptyState`, and the new `AIAdvisorPanel` into `frontend/src/components/`.
- Wired `EmptyState` into the "no assets found" table state and `ErrorState` into the asset-detail load-failure path — the latter is now retryable (extracted `loadAssetDetail` into a `useCallback` so a **Retry** button can re-run it, instead of the old dead-end "Unable to load asset analysis." message).
- Converted the five scroll-to-section sidebar nav items from `<div onClick>` to real `<button>` elements (keyboard-focusable/activatable); gave the "Dashboard" nav item a working scroll-to-top handler (previously a no-op).
- Added `aria-label`s to the search input, the clear-search button, and all four filter `<select>` elements; grouped the four filters into a semantic `.asset-filters` wrapper (previously flex children mixed directly into the search box's own container).
- Added an Escape-key handler that closes the full-height asset-detail overlay.
- Fixed a pre-existing duplicate DOM id (`id="pqc-migration-section"` appeared on both the global PQC distribution panel and the per-asset PQC detail card) by renaming the per-asset one to `asset-pqc-migration-section`.
- Rewrote `App.css` as a single tokenized design system (CSS custom properties for surface/border/text colors, a 4-step severity palette with **HIGH and CRITICAL now visually distinct** — orange vs. red, previously identical — spacing scale, radius scale, shadow/transition tokens), removing ~400 lines of confirmed-dead and duplicate CSS accumulated from prior redesign passes (multiple redefinitions of `.asset-detail-panel`, `.detail-card`, `.candidate-ranking-*`, `.classification-grid`, `.pqc-migration-grid`; fully dead selectors `.recommendation-box`, `.migration-actions`/`.migration-action-number/-content/-title/-description`, `.risk-detail-*`). Added a `.btn`/`.btn-primary`/`.btn-outline`/`.btn-sm` button system and a global `:focus-visible` outline, neither of which existed before. Reduced border-radius from 12–14px to 6–10px and removed most card gradients/heavy shadows per the requested restrained, professional visual direction.
- **Bug found and fixed via live testing (not anticipated beforehand):** the asset table, PQC candidate ranking list, and migration action list used React `key` props that were not actually guaranteed unique (`asset.bom_ref`, `candidate.candidate`, `action.step`) — the real dataset contains repeated `bom_ref` values across multiple CBOM occurrences of the same underlying key material, which produced 500+ "Encountered two children with the same key" console errors in a real browser. Fixed by always incorporating the array index into every list key.

### Why

The task asked for the AI Advisor to be "accessible from the asset detail experience" as "an important intelligence feature, not an afterthought," with explicit idle/loading/success/error+retry states and duplicate-request prevention, plus a professional security-dashboard visual pass without breaking existing functionality or the API contract. No backend or `frontend/src/api.js` changes were needed to accomplish this — the existing `POST /api/ai/advice` contract already supported everything required.

### Files modified

- `frontend/src/App.jsx` — AI state machine rewrite, AI Advisor relocated into asset detail, nav-item accessibility, filter/search accessibility + restructuring, Escape-key handler, retryable asset-detail loading, duplicate-id fix, React key fixes.
- `frontend/src/App.css` — full rewrite as a tokenized design system (same className contract as before; cross-checked against the JSX both directions).
- `frontend/src/components/Badge.jsx`, `StatCard.jsx`, `DistributionBar.jsx`, `States.jsx`, `AIAdvisorPanel.jsx` — new.
- `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/AI_ADVISOR.md`, `docs/TODO.md`, `docs/CHANGELOG.md` — updated to describe the resulting implementation.
- No changes to any `backend/` file, any `data/*.json` file, or `frontend/src/api.js` this round.

### Tests performed

- `npm run build` (`vite build`) after every meaningful edit — passed throughout; final build: 2383 modules, ~26.96 kB CSS / ~581.9 kB JS (pre-existing single-chunk size warning, unrelated to this change and not addressed — see Known Issues).
- **Live, real browser end-to-end testing:** launched the actual FastAPI backend (`uvicorn main:app`), the actual Vite dev server, and a locally-installed headless Chrome (`--headless=new --remote-debugging-port`), then drove real interactions over the Chrome DevTools Protocol from a throwaway Node script using only Node's built-in `fetch`/`WebSocket` (no new npm dependency was installed; the script was deleted after the run). This is not a claim of "should work" — every item below was observed directly against the running app and a real local Ollama (`qwen3:14b`, confirmed reachable):
  - Dashboard loads; stat cards render real values (`29`, `292`, `4`, `2`).
  - Risk-level filter narrows the asset table from 57 to 8 rows for `HIGH`.
  - Search narrows results from 57 to 6 for `"rsa"`.
  - Clicking an asset row opens the detail overlay with the correct heading (`RSA-OAEP`).
  - The AI Advisor card is present in the detail view with all 8 required snapshot fields populated with real values.
  - Idle button text is exactly "Get AI Recommendation".
  - Clicking it shows the loading block with exactly "Qwen3:14b is analyzing this cryptographic asset...", disables the button, and — confirmed by clicking a sidebar nav item during the wait — the rest of the dashboard remains interactive.
  - The real Ollama call completed (33s and 45s on two separate runs) and rendered a correctly-sectioned response (RISK/MIGRATION/PQC/...) whose stated risk score matched the dashboard's own `current_risk`.
  - Switching to a different asset mid-session correctly cleared the previous asset's AI result and reset the button to the idle label.
  - The Escape key closed the asset-detail overlay.
  - The repository-analysis form accepted input, and clicking "Analyze Repository" transitioned the status panel to "Analysis Running" (CBOMKit is not running in this environment, so it is expected to reach "failed" shortly after — the trigger/status-rendering path itself was what was being verified, and it worked correctly, matching the already-documented pipeline behavior).
  - **First run: 521 console messages, all but 3 were "duplicate key" React errors.** After the key fix described above and a rebuild, the identical test sequence was re-run end-to-end: **0 console errors, 0 console warnings, 0 uncaught page exceptions.**
- Cleanup: the throwaway CDP driver script, the test backend/frontend server instances, and the headless Chrome instance were all stopped after testing. One anomaly encountered during cleanup: a process reported as PID 36872 remained listed as the `LISTENING` owner of port 8000 in `netstat`/`Get-NetTCPConnection` even though neither `tasklist` nor `Get-Process`/`Get-CimInstance` could find a process with that PID — i.e. something was still actually serving `/health` correctly on port 8000 under an unidentifiable process handle. This was not resolved (no broad/forceful process termination was attempted, to avoid risking unrelated processes) — see Known Issues.

### Known issues

- A stale-looking but still-responding listener on `127.0.0.1:8000` survived normal process inspection/cleanup after this session's testing (see above). If the user is not intentionally running a persistent backend on port 8000, they may want to identify and restart it manually (e.g. via Task Manager with "show processes from all users," or a reboot) before relying on that port.
- Everything already listed as open in `AI_ADVISOR.md`'s "Limitations" section remains open (no streaming, no client-side cancel, generic 500-level error text, no caching, hardcoded Ollama URL/model).
- The pre-existing large-single-JS-chunk build warning (~582 kB) was not addressed — would require code-splitting, out of scope for a UI/AI-integration pass that was explicitly asked not to restructure the app wholesale.
- No automated regression tests were added for the new components (`AIAdvisorPanel`, `Badge`, `States`) or for the AI state machine — verification this round was live/manual (see Tests performed) and would need to be re-run manually after future related changes.
- `DistributionBar` and `LoadingState` remain defined-but-unused utility components (the former was already unused before this round; the latter is new but not yet wired into any call site — `EmptyState` and `ErrorState` are the two that got actually used this round).

---

## 2026-09-14 — Phase 1 (backend architecture) + Phase 2 (AI data consistency)

**Date:** 2026-09-14

### Changes

1. **Resolved the two divergent FastAPI backends.** `backend/main.py` is now the single canonical application:
   - Added `POST /api/ai/advice` (Pydantic model `AIAdviceRequest{asset: str}`), matching exactly the contract `frontend/src/api.js`'s `getAIAdvice()` calls. This was previously only implemented in `backend/api/main.py`.
   - Left the pre-existing `POST /api/ai/advisor` (`{asset_name}`) route in place, unused by the frontend, for backward compatibility — verified nothing else in the repo (frontend, tests) references it.
   - Removed a dead, second `@app.get("/api/pqc-ranking")` definition (the bare `return load_json(...)` one). Verified empirically (see "Tests performed") that Starlette matches routes in *registration order* and returns the first match — so the first, richer definition was always the one actually serving traffic; the second was silent dead code. (This corrects a factual error in the original `ARCHITECTURE.md`, which had claimed the *last* definition wins.)
2. **Rewrote `backend/api/main.py` into a 30-line backward-compatible shim** (`from main import app`, after inserting `backend/` onto `sys.path`) instead of maintaining a second, independently-drifting copy of every route. `uvicorn api.main:app` and `uvicorn main:app` now serve byte-identical behavior. The file was **not** deleted, per instruction.
3. **Fixed the AI advisor's data-consistency bug.** Rewrote `backend/services/ai_advisor.py`'s `build_context()`/`find_asset()`:
   - Now reads only `data/ecdat-migration-report.json` (the same unified, authoritative dataset `/api/asset/{name}` and the dashboard are built from), instead of independently re-reading four separate intermediate pipeline files (`ecdat-contextual-risk-assets.json`, `ecdat-migration-priority.json`, `ecdat-pqc-migration-plan.json`, `ecdat-migration-actions.json`).
   - Asset lookup (`find_report_asset`) is now case-insensitive, matching every other lookup endpoint in `backend/main.py` (previously case-sensitive only in this one service).
   - Context now also includes `source_impact` (impact level + affected file/class/function counts), previously omitted entirely despite the dashboard UI already claiming the advisor reviews it.
   - The Ollama call itself (URL, model `qwen3:14b`, `stream:false`, `think:false`, `temperature:0.2`, `num_predict:300`, 300s timeout) and the prompt template's six-section format were **not** changed, per instruction (preserve the existing Qwen3/Ollama integration, no new model, no new dependencies).

### Why

`docs/ARCHITECTURE.md` (2026-09-14 documentation pass) had identified that neither FastAPI app alone could serve the full frontend contract, and that the AI advisor could show a different "current risk" number than the dashboard for the same asset because it read a different (though numerically-equivalent-by-coincidence) intermediate file. Both were flagged High Priority in `docs/TODO.md`. This work closes both gaps without redesigning the UI, splitting `App.jsx`, changing the AI model, or adding new dependencies.

### Files modified

- `backend/main.py` — added `/api/ai/advice` + `AIAdviceRequest`; removed one dead duplicate route.
- `backend/api/main.py` — reduced to a deprecated shim re-exporting the canonical app.
- `backend/services/ai_advisor.py` — `build_context()`/asset-lookup rewritten to source from the unified migration report.
- `docs/PROJECT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/AI_ADVISOR.md`, `docs/TODO.md`, `docs/CHANGELOG.md` — updated to describe the resulting implementation.
- No changes to `frontend/`, `data/`, or any pipeline stage script (`cbom_parser.py` through `generate_migration_report.py`).

### Tests performed

- Imported both `main` and `api.main` directly (via the project's `venv` Python) and confirmed `api.main.app is main.app`, and that `main.app.routes` has zero duplicate paths (35 total routes).
- Started the canonical backend (`uvicorn main:app --port 8000`) and hit every endpoint listed in the task's required list — `/health`, `/api/status`, `/api/summary`, `/api/assets`, `/api/migration-report/assets` (+ `/{asset}`), `/api/asset/{asset}`, `/api/risk`, `/api/priority`, `/api/complexity`, `/api/blast-radius`, `/api/pqc`, `/api/pqc-ranking`, `/api/source-impact`, `/api/actions`, `/api/analyze/status` — all returned HTTP 200 with non-trivial bodies.
- Exercised `POST /api/analyze` (repository-analysis trigger) against an unreachable CBOMKit instance: correctly transitions `idle → running → failed` with a descriptive error, and correctly accepts a new run once the previous one has finished (409-guard logic unaffected).
- **Exercised `POST /api/ai/advice` live, end-to-end, against a real running Ollama instance (`qwen3:14b`, confirmed reachable at `localhost:11434`)** for asset `DSA`: response HTTP 200 in ~49s; the model's RISK section correctly stated "a high risk score of 65.75 and a high severity rating," exactly matching `current_risk = {score: 65.75, severity: "HIGH"}` from `ecdat-migration-report.json` / `/api/asset/DSA` — confirming the consistency fix works with the real model, not just in unit-level context building.
- Verified case-insensitive lookup: `build_context("DSA")` and `build_context("dsa")` resolve to the identical record (asset-name field aside); confirmed live via the API with `{"asset": "dsa"}` producing a correct, matching answer.
- Verified graceful degradation: `POST /api/ai/advice {"asset": "TotallyMadeUpAlgorithm"}` returns HTTP 200 with the model correctly stating the asset is unrecognized, rather than erroring or hallucinating data.
- Verified the legacy `POST /api/ai/advisor {"asset_name": "DSA"}` still works (HTTP 200), confirming backward compatibility.
- Spot-checked `/api/asset/RSA` end-to-end (a real asset in the current dataset) — correct `current_risk`/`recommendation` returned.
- Ran the repo's existing `backend/test_api_validation.py` and `backend/test_api_integration.py` against the live backend. Both fail on their first assertion (`total_assets == 59`; `GET /api/asset/ECDH` → 404) — **confirmed via `git stash` that both failures reproduce identically on the pre-change code**, i.e. they are pre-existing stale-fixture issues (the current `data/ecdat-assets.json` has 57 assets and does not contain an `ECDH` entry; the dataset was regenerated from a different scan at some point after these tests were written), not regressions introduced by this change. Logged as a newly-confirmed TODO item.
- `cd frontend && npm run build` — succeeds (`vite build`, 2379 modules, ~3s), only a pre-existing bundle-size advisory unrelated to this change. No frontend files were modified.
- `cd frontend && npm run lint` (oxlint) — fails with a native-binding load error (`An Application Control policy has blocked this file`) — a **pre-existing local Windows environment restriction**, unrelated to any change in this session (no frontend file was touched); not fixable without altering OS policy or reinstalling native packages, which was out of scope.

### Known issues (unchanged or newly confirmed by this work)

- The pipeline's three-way risk-scoring split (`score_cbom.py` / `score_contextual_cbom.py` / `explain_cbom.py`) still exists at the data-generation level; only the AI advisor's *consumption* of it was fixed to align with the dashboard. `/api/risk` still serves the intentionally different "basic" score (not currently surfaced anywhere in `App.jsx`).
- `RiskContext` defaults (`backend/models/risk_factors.py`) are still hardcoded and identical for every repository — not addressed this round.
- No backend dependency manifest (`requirements.txt`) still does not exist.
- Generic `except Exception → HTTP 500` error handling on `/api/ai/advice` was preserved as-is (not in scope for this round — see `TODO.md`).
- **Newly confirmed** (previously only suspected, TODO item 22): `backend/test_api_validation.py` and `backend/test_api_integration.py` are stale relative to the current `data/*.json` fixtures and currently fail on their very first assertions. They were not modified, since fixing test fixtures was outside this round's scope.
- `frontend/` lint (`oxlint`) cannot currently run in this local environment due to a blocked native binary — this is an environment issue, not a code issue, and predates this session.

---

## 2026-09-14 — Documentation baseline established (no code changes)

**Type:** Documentation only. No application code, configuration, or data files were modified.

Performed a full read-through of the ECDAT repository (`backend/`, `frontend/`, `data/`, `demo/`, configuration files) on branch `ecdat-1` and created `docs/` as the persistent project-memory reference for future work:

- `docs/PROJECT_CONTEXT.md` — current features, tech stack, module map
- `docs/ARCHITECTURE.md` — real frontend/backend architecture and data flow, including the repository-analysis pipeline (13 stages) and the AI-advisor flow
- `docs/AI_ADVISOR.md` — exact current AI advisor implementation (endpoint, Ollama config, prompt, context building, frontend integration, limitations)
- `docs/TODO.md` — prioritized list of issues discovered during inspection
- `docs/CHANGELOG.md` — this file

### Notable findings from this inspection (see `ARCHITECTURE.md` / `TODO.md` for full detail)

- Two parallel FastAPI apps exist (`backend/main.py` and `backend/api/main.py`) with overlapping but non-identical routes; neither one alone can serve the full frontend contract (one has `/api/analyze`, the other has the `/api/ai/advice` shape the frontend actually calls).
- Three independent risk-scoring code paths produce three separate JSON outputs (`ecdat-risk-assessed-assets.json`, `ecdat-contextual-risk-assets.json`, `ecdat-explainable-risk.json`) consumed by different parts of the system (plain `/api/risk`, the AI advisor, and everything else/the dashboard, respectively).
- The AI advisor builds its context from different source files than the dashboard's "current risk," so the two can show different numbers for the same asset.
- `RiskContext` business-context defaults (`models/risk_factors.py`) are hardcoded and identical for every asset/repository — "contextual" risk is not actually derived from the analyzed project.
- The CBOM working file is always named `data/keycloak-cbom.json` regardless of which repository was scanned.
- The repo carries dead/backup files (`backend/main_backup*.py`, `backend/cbom_parser_backup.py`, `data-backup/`, duplicate `demo/cbom*.json`) and no `requirements.txt`/lockfile-equivalent for the backend.

This baseline reflects the state of the code as of commit `accbb19` ("Add AI migration advisor UI") on branch `ecdat-1`.

---

## Prior history (from git log, not independently re-verified — for orientation only)

- `accbb19` — Add AI migration advisor UI
- `8c55296` — Integrate Qwen3 AI migration advisor (introduced `services/ai_advisor.py`; edited both `backend/main.py` and `backend/api/main.py`)
- `ac3f6d7` — Add automated CBOMKit repository analysis
- `cd96d57` — checkpoint: backend restored and dashboard working
- `7407cfe` — feat: add interactive asset filtering and chart controls

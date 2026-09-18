# ECDAT — Project Context

> ECDAT's name is never expanded in the code. The API title is "ECDAT API", described as "ECDAT Cryptographic Discovery and Post-Quantum Migration API".

This document summarizes what the ECDAT codebase does **today** (branch `ecdat-1`, 2026-09-18). It is descriptive, not aspirational. `ARCHITECTURE.md` has the technical detail, `CHANGELOG.md` the dated history, and `TODO.md` open issues.

ECDAT is a **prototype**. It analyzes one repository's cryptography at a time, stores results as flat JSON files, and runs entirely on local services.

---

## 1. What ECDAT does

ECDAT turns a **Cryptography Bill of Materials (CBOM)** for a source-code repository into an explainable post-quantum migration analysis. Concretely:

1. **Discovery (via CBOMKit).** The dashboard sends a GitHub repository URL + branch to the backend's scan service, which validates the target, selects a scanner from the scanner registry, and asks a separately running **CBOMKit** instance to scan the repository and return a CycloneDX CBOM. ECDAT then validates and normalizes that CBOM before analysing it. What can be discovered depends on CBOMKit's source-code analysis; ECDAT itself does not parse source code. The full flow is in §3.1.
2. **Analysis.** A 13-stage Python pipeline produces, per finding:
   - classification and evidence-based purpose
   - explainable quantum risk
   - blast radius, migration complexity and migration priority
   - ranked PQC candidates
   - a purpose-aware migration strategy
   - migration actions
   - a unified report

   A final consistency check verifies that every risk figure agrees.
3. **Serving.** A FastAPI backend exposes the results, plus read-only What-If, Evidence Explorer and blast-radius relationship endpoints.
4. **Exploration.** A React dashboard shows the portfolio and a per-finding investigation workspace, rendered on desktop and tablet widths as a shared 3D security space.
5. **Explanation.** An AI Advisor sends one finding's computed results to a locally hosted **Ollama** model (`qwen3:14b`) and displays a plain-language analysis.

### Scanner coverage — what is and is not implemented

| Target | Status |
|---|---|
| **Git / GitHub source repositories** | **Implemented**, through the CBOMKit adapter (`cbomkit-repository`). Requires a reachable CBOMKit instance; when CBOMKit is unreachable the scan fails at the availability stage and says so. |
| Compiled binaries and firmware | **Not implemented.** Declared as a planned target; no scanner exists. |
| Dependency / library inventories | **Not implemented.** Declared as a planned target; no scanner exists. |
| Container images | **Not implemented.** Declared as a planned target; no scanner exists. |
| Hardware, cloud infrastructure, cloud KMS/TLS inventory | **Not implemented**, and not declared as a planned target. |
| Live network traffic, TLS endpoints, running processes | **Not implemented.** |

The three planned targets are returned by `GET /api/scan/capabilities` with `status: "not-implemented"` and shown in the UI as *"Not implemented: compiled binaries, dependency / library inventories, container images."* Nothing in the product implies coverage that does not exist.

**Also not implemented:**
- multi-repository history
- a database or authentication
- automatic discovery of business context: business criticality and data lifetime come only from an optional, organization-supplied config file, and none ships with the repository

---

## 2. Key concepts and terminology

| Term | Meaning in ECDAT |
|---|---|
| **Finding** | One CBOM component (algorithm, key material, …), identified by its **`bom_ref`**. |
| **`bom_ref`** | The CycloneDX `bom-ref`, and the **only** canonical finding identity. Algorithm names repeat: the current dataset has two distinct `RSA-2048` findings. All joins, API routes, UI selection, What-If, Evidence Explorer and blast-radius lookups use `bom_ref`. |
| **Quantum status** | Classification result: `vulnerable`, `weak`, `quantum-aware`, `quantum-resistant`, `contextual` (key material) or `unknown`. |
| **Purpose / role** | What the finding is used for (e.g. key establishment, signature, hashing). It is resolved from CBOM and source evidence with a recorded confidence and source. An algorithm-family fallback is marked LOW confidence and not treated as repository evidence. |
| **UNKNOWN value** | An input ECDAT cannot observe, e.g. data lifetime without configuration. It is excluded from weighted scores, which are rescaled, and is never guessed or scored as zero. |
| **Ranking-model candidate** | A PQC algorithm ranked by the candidate-ranking model. **It is not automatically a migration recommendation.** |
| **Migration strategy** | The authoritative migration decision per `bom_ref` (see below). |
| **Selected PQC component / path** | The PQC algorithm chosen by a **DIRECT_PQC** or **HYBRID** strategy. Only these strategies have one. |
| **KEEP** | No PQC migration applies (e.g. hashes, MACs, KDFs), optionally with a classical-hardening note. |
| **NEEDS_REVIEW** | The migration decision is **unresolved**. The evidence doesn't determine the role, so no PQC component is selected, even if the ranking model ranked candidates. |
| **PQC Candidates (dashboard count)** | Findings with a selected PQC path: DIRECT_PQC + HYBRID. |

---

## 3. Core features (as implemented)

**Discovery and identity**
- **GitHub repository scanning.** A first-class scan workflow with real per-stage status (§3.1).
- **CBOM parsing.** Components and dependency relationships are extracted. Duplicate component records are merged **only** when their `bom_ref` is identical, keeping every evidence occurrence; findings are never merged by name.

**Classification and risk**
- **Evidence-aware classification.** An algorithm knowledge base gives category and quantum status; `purpose_resolver.py` resolves purpose from the CBOM primitive, then source API context, then a LOW-confidence family fallback, and flags conflicting evidence for review.
- **Explainable quantum risk.** `explain_cbom.py` is the single risk calculation. It weights base quantum risk, a path-derived business-criticality proxy, data lifetime, exposure, migration time and evidence quality (40/20/15/10/10/5). Unknown factors are excluded and weights rescaled, and each factor's contribution is recorded. `check_risk_consistency.py` fails the pipeline if any risk figure elsewhere disagrees.
- **RiskContext per finding.** Exposure, criticality proxy and migration time are derived from each finding's own evidence (paths, API contexts, occurrence count, category). The quantum threat horizon is a documented fixed default (10 years).
- **Business context and Mosca-style timelines.** An optional `data/business-context.json`, keyed by `bom_ref`, can supply business criticality and data lifetime. Only when a data lifetime is known does ECDAT run the Mosca-style check (data lifetime + migration time vs. threat horizon). The result is informational in risk and a weighted factor in priority. With no config file present, these values are UNKNOWN and Mosca analysis is not performed.

**Impact and prioritization**
- **Blast radius.** Direct dependencies, direct dependents and transitive dependents from recorded CycloneDX `dependsOn` relationships, with a 0–100 impact score.
- **Migration complexity.** An additive 0–100 score (cryptographic, dependency, migration-time, evidence-surface and data-lifetime factors), computed from each finding's own records.
- **Migration priority.** Weighted risk / blast radius / complexity, plus optional business criticality and Mosca urgency, with unknowns excluded. Levels drive the dashboard's readiness figure.

**PQC migration**
- **PQC mapping and ranking.** Seven registry algorithms: ML-KEM-512/768/1024, ML-DSA-44/65/87 and SLH-DSA (FIPS 203/204/205). The ranking scores each candidate on purpose compatibility, registry compatibility, parameter suitability, risk, blast radius and complexity.
- **Purpose-aware migration strategy** (`services/migration_strategy.py`). One of `KEEP`, `DIRECT_PQC`, `HYBRID`, `NEEDS_REVIEW` per `bom_ref`, with confidence, rationale, decision factors and explanation. HYBRID is chosen over DIRECT_PQC when there is evidence of external exposure or HIGH/CRITICAL complexity or blast radius. Key material inherits its governing algorithm's strategy through the CBOM dependency graph.
- **Recommendation state** (`services/recommendation_state.py`). The shared layer that restates every `recommendation` record from the strategy:
  - DIRECT_PQC / HYBRID: `confirmed`, with the selected component.
  - NEEDS_REVIEW: `decision: NEEDS_REVIEW`, no candidate.
  - KEEP: no candidate.

  The ranking model's own output is kept under `recommendation.ranking_model`. The plan and report generators, the report/asset API endpoints, the dashboard count and the AI Advisor all use this layer.
- **Source impact and migration actions.** Affected files, classes and functions come from recorded occurrences. Strategy-specific developer actions are generated per finding; for NEEDS_REVIEW, "do not replace until review is resolved".
- **Unified migration report.** One record per `bom_ref`, used by the dashboard and AI Advisor.

**Interactive analysis**
- **What-If Simulator.** For a DIRECT_PQC or HYBRID finding, evaluates migrating to a valid PQC option of the right family. It re-runs the real risk and priority engines on a copy and shows before/after/delta for risk and priority plus portfolio readiness. It is clearly labelled a simulation and never changes data. NEEDS_REVIEW and KEEP findings show a non-simulatable state.
- **Evidence Explorer.** A read-only "why" view:
  - identity and the raw CycloneDX component
  - purpose evidence and source occurrences
  - quantum status
  - risk contributions, with unknown factors kept explicit
  - blast radius, complexity and priority
  - strategy and PQC status
  - a seven-step evidence→decision chain
- **Blast Radius visualization.** A tree of the recorded dependency relationships: what the finding depends on, the findings that depend on it, and indirect dependents nested under their recorded parent. Summary metrics and a "No dependency relationships recorded" state are included. No edge is drawn without a CBOM relationship.
- **AI Advisor.** Explains the ECDAT results in RISK / MIGRATION / PQC / ACTIONS / IMPACT / SUMMARY sections (the UI calls this "AI Analysis"). The context follows the strategy: only DIRECT_PQC/HYBRID findings get a `recommended_candidate`, and NEEDS_REVIEW gets ranking output explicitly marked "NOT A RECOMMENDATION". The model's text is generated and not guaranteed.

---

## 3.1 The repository scan workflow

```
GitHub URL
  → target validation      parse/canonicalise owner, repository, branch
  → scanner registry       select a scanner that supports the target kind
  → CBOMKit adapter        POST /api/v1/scan, poll /api/v1/cbom/last/N
  → CBOM validation /      reject unusable CBOMs; add missing containers only
    normalization
  → 13-stage pipeline      the existing, unchanged ECDAT analysis
  → publish                write the scan record and history
  → 3D Security Space      "Open in Security Space" focuses the new dataset
```

Implemented by `backend/services/scanning/` and exposed as `POST /api/scan` (alias `POST /api/analyze`), `GET /api/scan/status`, `GET /api/scan/capabilities` and `GET /api/scan/history`.

- **Real progress.** The status payload reports the seven stages above with `pending / running / done / failed` and a per-stage detail line, plus the 13 pipeline substages and the stage currently executing. No stage advances on a timer; every transition is a real completion.
- **Validation before analysis.** A CBOM that is not a CycloneDX object, has no components, has components without a `bom-ref`, has two *different* components sharing one `bom-ref`, or contains no cryptographic components is **rejected before the pipeline runs**, so a bad scan cannot overwrite a good analysis. Repeated *identical* component entries are a warning, not an error — CBOMKit emits them routinely (the current CBOM has 27) and ECDAT keys findings by `bom_ref`, so each is analysed once.
- **Normalization is minimal.** Only missing `components` / `dependencies` containers are added. No value is invented, corrected or inferred.
- **A scan never reuses an older CBOM.** CBOMKit stores every CBOM it has produced, so a previously scanned repository already has one waiting. ECDAT records what CBOMKit holds *before* requesting the scan and only accepts a CBOM whose CBOMKit record is later (newer timestamp, or a different commit). If CBOMKit keeps the record it already had — its answer for an unchanged commit — the result is labelled **cached**, in the status message and in the UI, and never presented as a freshly scanned commit.
- **Honest failures.** Every failure carries a reason code — `empty-url`, `unsupported-host`, `malformed-url`, `invalid-branch` (target validation); `no-scanner`, `scanner-unavailable`, `scanner-crashed`; `cbomkit-unavailable`, `cbomkit-scan-rejected`, `cbomkit-timeout`, `unsupported-target`; a validation code; `pipeline-stage-failed` or `pipeline-stage-timeout` — and names the stage it failed at.
- **One scan at a time, across processes.** The API and the CLI share one scan slot (an in-process lock plus `data/.ecdat-scan.lock`), so two pipelines can never write the dataset at once. A second request gets `409`. Runtime files are written atomically, and a record left `running` by a killed process is closed out as `interrupted` at startup.
- **Dependency counts are named, not conflated.** The scan panel reports *recorded dependency entries* as the scanner produced them (37 in the current CBOM); the map and blast radius use *unique dependency edges* (19). Both are real; `ARCHITECTURE.md` §2.1.3 defines each.
- **Extensible by design.** Scanners implement one `Scanner` interface (`check_availability`, `scan`) and are added to the registry; binary, library and container scanners can be added without touching the service, the API or the UI, and are currently declared as not implemented rather than stubbed.

---

## 4. Current dataset snapshot

`data/keycloak-cbom.json` currently holds a CBOMKit scan of `pyca/cryptography` (branch `main`, commit `39138c6`), produced through the scan workflow in §3.1 and verified as a fresh CBOM rather than one CBOMKit already held. The filename is fixed and historical. From it:

- **Findings:** 25 (47 raw component entries, with exact `bom_ref` duplicates merged).
- **Relationships:** 29 recorded dependency entries, giving 15 unique CycloneDX dependency edges. Three findings have none: `x25519`, `x448`, `RSA-OAEP`.
- **Strategies:** KEEP 4, DIRECT_PQC 5, HYBRID 6, NEEDS_REVIEW 10 (the three RSA algorithms and seven key-material findings).
- **PQC Candidates (selected paths):** 11.
- **Priority:** 3 findings are HIGH/CRITICAL (1 CRITICAL, 2 HIGH), giving 88% readiness.
- **Duplicate names:** two distinct `RSA-2048` findings (`afc4f1a7…`, `9eae7f2e…`), a reminder that `bom_ref` is the only identity.
- **Business context:** none configured, so business criticality and data lifetime are UNKNOWN for all findings and Mosca analysis is not performed.

Earlier revisions of these documents describe a 30-finding scan of the same repository at commit `a825ca0`; `CHANGELOG.md` keeps those figures as history. Nothing in the analysis changed — the repository did.

---

## 5. Technology stack

### Backend
- **Python 3.14**, with a virtual environment at `backend/venv`
- **FastAPI** + **Uvicorn**, **Pydantic** request models
- **requests**, for the CBOMKit and Ollama HTTP calls
- **Persistence:** flat JSON files in `data/`, with no database
- **Dependencies:** no committed `requirements.txt` or `pyproject.toml`; they are only visible in the venv

### Frontend
- **React 19** + **Vite 8**; **Recharts** (donut charts); **lucide-react** (icons); **three.js** (the 3D security space, lazily loaded)
- **oxlint** (`npm run lint`)
- **Styling:** one tokenized stylesheet (`App.css`), with Inter and Space Grotesk loaded from Google Fonts, which requires network access
- **Structure:** no router, no global state library, no frontend test runner

### External services (run separately; not part of this repository)
- **CBOMKit** at `http://localhost:8081`, for repository scanning
- **Ollama** at `http://localhost:11434` with `qwen3:14b`, for the AI Advisor

---

## 6. Repository layout

```
backend/
  main.py                      The FastAPI application (all routes)
  api/main.py                  Compatibility shim re-exporting main.app
  analyze_repository.py        CLI over the scan service (one scan, printed stages)
  cbomkit_client.py            CLI over the CBOMKit adapter + CBOM validation
  run_pipeline.py              Runs the 13 stages below in order
  cbom_parser.py → classify_cbom.py → explain_cbom.py → score_cbom.py →
  generate_blast_radius.py → generate_migration_complexity.py →
  generate_migration_priority.py → generate_pqc_migration.py →
  generate_pqc_ranking.py → generate_pqc_migration_plan.py →
  generate_migration_actions.py → generate_migration_report.py →
  check_risk_consistency.py
  services/
    crypto_classifier.py, purpose_resolver.py           classification + purpose evidence
    risk_engine.py, risk_context.py, contextual_risk.py,
    business_context.py, mosca_analysis.py,
    evidence_engine.py, evidence_confidence.py,
    explanation_engine.py                               explainable risk
    dependency_graph.py, blast_radius.py,
    blast_radius_explanation.py                         blast radius
    migration_complexity.py, migration_priority.py      complexity + priority
    pqc_registry.py, pqc_mapper.py, pqc_ranker.py       PQC mapping + ranking
    migration_strategy.py                               KEEP / DIRECT_PQC / HYBRID / NEEDS_REVIEW
    recommendation_state.py                             strategy-authoritative recommendation state
    source_crypto_mapper.py, source_impact_analyzer.py,
    migration_action_generator.py, migration_recommender.py
    migration_scenario.py                               What-If Simulator
    evidence_explorer.py                                Evidence Explorer
    blast_radius_view.py                                blast-radius relationship view
    ai_advisor.py                                       AI Advisor context + Ollama call
    scanning/                                           the scan workflow (§3.1)
      targets.py      GitHub URL/branch validation → ScanTarget
      base.py         Scanner interface, Availability, ScanArtifact, ScannerError
      cbomkit.py      CBOMKit HTTP client + repository scanner adapter
      validation.py   CBOM validation and minimal normalization
      registry.py     scanner registry + declared not-implemented targets
      pipeline.py     runs the existing 13 stages, reporting each one
      service.py      scan lifecycle, state, records and history
  knowledge/crypto_knowledge.py, knowledge/migration_strategy_policy.py
  models/risk_factors.py       RiskContext
  test_*.py                    36 test scripts (run individually with python)
  fixture_dataset.py           deterministic test dataset, independent of data/
  Legacy/unused: main_backup*.py, cbom_parser_backup.py, score_contextual_cbom.py,
                 generate_summary.py, inspect_dependencies.py
frontend/src/
  App.jsx, api.js, migrationStrategy.js, App.css, index.css, main.jsx
  components/  Topbar, Sidebar, HeroOverview, StatCard, RepositoryAnalysisPanel,
               PipelineStepper, CriticalFindingsPanel, DonutPanel, AssetFilters,
               AssetExplorer, AssetDetailPanel, AIAdvisorPanel, Badge, States,
               DistributionBar (unused)
  components/detail/  AssetHeaderBand, EvidencePanel, RiskImpactPanel, MigrationFlow,
                      WhatIfSimulator, BlastRadiusPanel, BlastSpatialView,
                      MigrationTransition, EvidenceExplorer
  components/visualization/  the cryptographic security map (3D scene, 2D fallback,
                             legend, focus panel, model)
  spatial/     the shared 3D security space: engine/ (one renderer, one canvas, one
               camera; environment, posture, landscape, investigation and simulation
               layers), stage/ (SpatialStage, StageLayout, useLayoutMode) and the
               docked React surfaces
data/        Raw CBOM, PQC registry, generated ecdat-*.json, scan runtime records
             (plus some stale files; see ARCHITECTURE.md §4)
data-backup/, demo/   Manual snapshots / sample CBOMs
docs/        ARCHITECTURE.md, PROJECT_CONTEXT.md, AI_ADVISOR.md, CHANGELOG.md, TODO.md
```

---

## 7. Running and validating

- **Backend:** `cd backend && uvicorn main:app --reload` (port 8000).
- **Frontend:** `cd frontend && npm run dev` (port 5173); `npm run build`, `npm run lint`.
- **Pipeline** (overwrites `data/`): `cd backend && python run_pipeline.py`.
- **Scan from the CLI** (needs CBOMKit): `cd backend && python analyze_repository.py https://github.com/owner/repo main`. `python cbomkit_client.py <url> [branch]` fetches and validates a CBOM only.
- **Tests:** from `backend/`, run each `python test_<name>.py`. `test_api_validation.py` and `test_api_integration.py` require the backend running on `:8000`.
- **Consistency check:** `python check_risk_consistency.py`.

---

## 8. Prototype boundaries and extension areas

**Current boundaries**
- One repository/CBOM at a time, in a fixed file; generated JSON does not record its source repository. The scan record (`data/ecdat-scan.json`) and history do record the target.
- Discovery is limited to what CBOMKit finds in source code. Only Git repository targets have a scanner; binaries, libraries and containers are declared not implemented.
- Organizational context must be configured manually.
- The What-If model is family-level, not parameter-set-level.
- There is no authentication, persistence layer or frontend unit testing.

**Possible future extensions (not implemented)**
- Binary, library, container-image, hardware or cloud/KMS/TLS discovery sources, added as scanners behind the existing registry.
- Multi-repository history.
- A business-context editor.
- Parameter-set-aware risk modelling.
- Deployment hardening.

## 9. Related documents

- `ARCHITECTURE.md` — detailed current architecture, formulas, API and data flow
- `AI_ADVISOR.md` — AI Advisor implementation detail
- `CHANGELOG.md` — dated history of changes
- `TODO.md` — open issues

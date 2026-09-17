# ECDAT — Project Context

> ECDAT's name is never expanded in the code. The API title is "ECDAT API", described as "ECDAT Cryptographic Discovery and Post-Quantum Migration API".

This document summarizes what the ECDAT codebase does **today** (branch `ecdat-1`, 2026-09-17). It is descriptive, not aspirational. `ARCHITECTURE.md` has the technical detail, `CHANGELOG.md` the dated history, and `TODO.md` open issues.

ECDAT is a **prototype**. It analyzes one repository's cryptography at a time, stores results as flat JSON files, and runs entirely on local services.

---

## 1. What ECDAT does

ECDAT turns a **Cryptography Bill of Materials (CBOM)** for a source-code repository into an explainable post-quantum migration analysis. Concretely:

1. **Discovery (via CBOMKit).** The dashboard sends a Git repository URL + branch to the backend, which asks a separately running **CBOMKit** instance to scan the repository and return a CycloneDX CBOM. What can be discovered depends on CBOMKit's source-code analysis; ECDAT itself does not parse source code.
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
4. **Exploration.** A React dashboard shows the portfolio and a per-finding investigation workspace.
5. **Explanation.** An AI Advisor sends one finding's computed results to a locally hosted **Ollama** model (`qwen3:14b`) and displays a plain-language analysis.

**Not implemented:**
- scanning of binaries, container images, cloud infrastructure, network traffic or running systems
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
- **Automated repository analysis.** `POST /api/analyze` runs `analyze_repository.py` in the background: a CBOMKit scan followed by the pipeline. Status is polled via `/api/analyze/status` (idle/running/completed/failed only; no per-stage progress).
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

## 4. Current dataset snapshot

`data/keycloak-cbom.json` currently holds a CBOMKit scan of `pyca/cryptography` (commit `a825ca0`). The filename is fixed and historical. From it:

- **Findings:** 30 (57 raw component entries, with exact `bom_ref` duplicates merged).
- **Relationships:** 19 unique CycloneDX dependency edges. Three findings have none: `x25519`, `x448`, `RSA-OAEP`.
- **Strategies:** KEEP 5, DIRECT_PQC 5, HYBRID 10, NEEDS_REVIEW 10 (the three RSA algorithms and seven key-material findings).
- **PQC Candidates (selected paths):** 15.
- **Priority:** 4 findings are HIGH/CRITICAL, giving 87% readiness.
- **Business context:** none configured, so business criticality and data lifetime are UNKNOWN for all findings and Mosca analysis is not performed.

---

## 5. Technology stack

### Backend
- **Python 3.14**, with a virtual environment at `backend/venv`
- **FastAPI** + **Uvicorn**, **Pydantic** request models
- **requests**, for the CBOMKit and Ollama HTTP calls
- **Persistence:** flat JSON files in `data/`, with no database
- **Dependencies:** no committed `requirements.txt` or `pyproject.toml`; they are only visible in the venv

### Frontend
- **React 19** + **Vite 8**; **Recharts** (donut charts); **lucide-react** (icons)
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
  analyze_repository.py        CBOMKit scan + pipeline orchestration (subprocess)
  cbomkit_client.py            CBOMKit client; writes data/keycloak-cbom.json
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
  knowledge/crypto_knowledge.py, knowledge/migration_strategy_policy.py
  models/risk_factors.py       RiskContext
  test_*.py                    32 test scripts (run individually with python)
  Legacy/unused: main_backup*.py, cbom_parser_backup.py, score_contextual_cbom.py,
                 generate_summary.py, inspect_dependencies.py
frontend/src/
  App.jsx, api.js, migrationStrategy.js, App.css, index.css, main.jsx
  components/  Topbar, Sidebar, HeroOverview, StatCard, RepositoryAnalysisPanel,
               PipelineStepper, CriticalFindingsPanel, DonutPanel, AssetFilters,
               AssetExplorer, AssetDetailPanel, AIAdvisorPanel, Badge, States,
               DistributionBar (unused)
  components/detail/  AssetHeaderBand, EvidencePanel, RiskImpactPanel, MigrationFlow,
                      WhatIfSimulator, BlastRadiusPanel, EvidenceExplorer
data/        Raw CBOM, PQC registry, generated ecdat-*.json (plus some stale files; see ARCHITECTURE.md §4)
data-backup/, demo/   Manual snapshots / sample CBOMs
docs/        ARCHITECTURE.md, PROJECT_CONTEXT.md, AI_ADVISOR.md, CHANGELOG.md, TODO.md
```

---

## 7. Running and validating

- **Backend:** `cd backend && uvicorn main:app --reload` (port 8000).
- **Frontend:** `cd frontend && npm run dev` (port 5173); `npm run build`, `npm run lint`.
- **Pipeline** (overwrites `data/`): `cd backend && python run_pipeline.py`.
- **Tests:** from `backend/`, run each `python test_<name>.py`. `test_api_validation.py` and `test_api_integration.py` require the backend running on `:8000`.
- **Consistency check:** `python check_risk_consistency.py`.

---

## 8. Prototype boundaries and extension areas

**Current boundaries**
- One repository/CBOM at a time, in a fixed file; generated JSON does not record its source repository.
- Discovery is limited to what CBOMKit finds in source code.
- Organizational context must be configured manually.
- The What-If model is family-level, not parameter-set-level.
- There is no authentication, persistence layer or frontend unit testing.

**Possible future extensions (not implemented)**
- Binary, container-image or cloud/KMS/TLS discovery sources.
- Multi-repository history.
- A business-context editor.
- Per-stage analysis progress.
- Parameter-set-aware risk modelling.
- Deployment hardening.

## 9. Related documents

- `ARCHITECTURE.md` — detailed current architecture, formulas, API and data flow
- `AI_ADVISOR.md` — AI Advisor implementation detail
- `CHANGELOG.md` — dated history of changes
- `TODO.md` — open issues

# ECDAT — Architecture

This document describes the ECDAT implementation **as it currently exists** (branch `ecdat-1`, 2026-09-17), traced through the code. It is descriptive, not aspirational: anything not implemented is listed as a limitation or extension area (§20), not as a capability. The dated history of how the system reached this state — including the bugs found and fixed along the way — is in `CHANGELOG.md`.

ECDAT is a working **prototype**: one repository/CBOM at a time, flat JSON files instead of a database, no authentication, and locally run services.

---

## 1. Scope

### Implemented

- **Source-repository discovery through CBOMKit.** A Git repository URL + branch is sent to a separately running CBOMKit instance, which scans the repository's source code and returns a CycloneDX CBOM. ECDAT does not scan source code itself; what can be discovered (languages, crypto libraries, API patterns) is whatever CBOMKit supports.
- **CBOM analysis.** A 13-stage Python pipeline turns that CBOM into per-finding classification, explainable quantum risk, blast radius, migration complexity, migration priority, PQC candidate ranking, a purpose-aware migration strategy, migration actions and a unified migration report.
- **FastAPI backend** serving the generated JSON, plus read-only analysis endpoints (What-If Simulator, Evidence Explorer, blast-radius relationship view).
- **React/Vite dashboard** for exploring findings and their evidence.
- **AI Advisor** that sends one finding's already-computed results to a locally hosted Ollama model for a plain-language explanation.

### Not implemented

ECDAT does **not** currently scan compiled binaries or firmware, container images, cloud infrastructure or cloud key-management configuration, live network traffic or TLS endpoints, or running processes. It has no multi-repository history, no user accounts, no database, and no per-stage progress telemetry. Organizational business context (business criticality, data lifetime) is **not** discovered automatically; it is only used if an organization supplies it in a configuration file (§7.3), and no such file ships with the repository.

---

## 2. System overview

```
 React dashboard (Vite, :5173)
   │  GET /api/*                  POST /api/analyze {repository, branch}
   │  POST /api/what-if/*         POST /api/ai/advice {asset: <bom_ref>}
   ▼
 FastAPI backend  backend/main.py (:8000)
   │
   ├─ reads data/*.json on every request (no cache, no database)
   │
   ├─ /api/analyze ──► background thread ──► analyze_repository.py (subprocess)
   │                                           ├─ cbomkit_client.py ──► CBOMKit (:8081, external)
   │                                           │     POST /api/v1/scan, poll /api/v1/cbom/last/5
   │                                           │     └─► data/keycloak-cbom.json
   │                                           └─ run_pipeline.py ──► 13 stages ──► data/ecdat-*.json
   │
   ├─ read-only services: evidence_explorer.py, blast_radius_view.py, migration_scenario.py
   │
   └─ /api/ai/advice ──► services/ai_advisor.py ──► Ollama (:11434, qwen3:14b, external)
```

`backend/main.py` is the single FastAPI application (`uvicorn main:app --reload` from `backend/`). `backend/api/main.py` is a compatibility shim that re-exports the same `app`.

---

## 3. Canonical finding identity: `bom_ref`

Every finding is identified by its CycloneDX `bom-ref` (stored as `bom_ref`). Algorithm names are **not** identities: the current dataset contains two distinct `RSA-2048` findings (`4049d4df…`, `e87e3bf2…`) with different source locations and different dependent keys, plus unnamed key-material findings (`private-key@…`, `public-key@…`).

- Every pipeline stage keys and joins its records by `bom_ref`. Some older records also carry an equal `asset_ref`.
- Every per-finding API route resolves its path parameter as a `bom_ref`. An algorithm name returns 404.
- The What-If, Evidence Explorer and blast-radius endpoints take `bom_ref` only; their request models reject extra fields.
- The frontend selects, fetches and renders findings by `bom_ref`, and remounts the per-finding panels on `bom_ref` change so one finding's data cannot appear under another.

This is enforced by tests. `test_finding_identity.py` checks that all generated stages contain the same `bom_ref` set, and that each stage's copies of upstream values match that finding's own records. Other test files check the duplicate RSA-2048 findings for cross-contamination at each layer.

---

## 4. Pipeline and generated artifacts

`backend/run_pipeline.py` runs these stages in order as separate processes and stops at the first failure. Each stage reads earlier JSON files and writes one output.

| # | Stage script | Main inputs | Output |
|---|---|---|---|
| 1 | `cbom_parser.py` | `keycloak-cbom.json` | `ecdat-assets.json` |
| 2 | `classify_cbom.py` | assets | `ecdat-classified-assets.json` |
| 3 | `explain_cbom.py` | classified assets | `ecdat-explainable-risk.json` (the only risk calculation) |
| 4 | `score_cbom.py` | explainable risk | `ecdat-risk-assessed-assets.json` (legacy "basic risk" view, re-projected from #3) |
| 5 | `generate_blast_radius.py` | assets (incl. CBOM dependencies), explainable risk | `ecdat-blast-radius.json` |
| 6 | `generate_migration_complexity.py` | assets, explainable risk, blast radius | `ecdat-migration-complexity.json` |
| 7 | `generate_migration_priority.py` | explainable risk, blast radius, complexity | `ecdat-migration-priority.json` |
| 8 | `generate_pqc_migration.py` | explainable risk | `ecdat-pqc-migration.json` |
| 9 | `generate_pqc_ranking.py` | PQC migration + risk, blast, complexity, priority | `ecdat-pqc-ranked.json` |
| 10 | `generate_pqc_migration_plan.py` | ranking + risk, blast, complexity, priority | `ecdat-pqc-migration-plan.json` (incl. migration strategy and reconciled recommendation) |
| 11 | `generate_migration_actions.py` | explainable risk, plan | `ecdat-migration-actions.json` |
| 12 | `generate_migration_report.py` | risk, blast, complexity, priority, plan, actions | `ecdat-migration-report.json` (unified per-finding record) |
| 13 | `check_risk_consistency.py` | explainable risk, risk-assessed assets, report | none — exits non-zero if any risk figure disagrees |

**Static inputs:** `data/keycloak-cbom.json` holds the raw CBOM. The filename is fixed regardless of which repository was scanned; the current file comes from a CBOMKit scan of `pyca/cryptography`. `data/pqc-algorithms.json` is the PQC registry.

**Not produced by the active pipeline:** these files are left over from earlier development and no current reader depends on them:
- `ecdat-contextual-risk-assets.json`, from the deprecated `score_contextual_cbom.py`
- `ecdat-risk-summary.json`, from `generate_summary.py`, which is not in the pipeline
- `cbom_parser.py.json` and `cbomkit-test.json`

`data-backup/` and `demo/` are manual snapshots.

The stages are deterministic for a given input: when stages 6–13 were re-run on unchanged inputs during development, they reproduced byte-identical outputs. Dependency lists are sorted so set ordering cannot vary between runs.

---

## 5. CBOM parsing and duplicate handling

`cbom_parser.py` reads the CycloneDX `components` and `dependencies`. For each component it extracts `bom_ref`, name, type, `assetType`, primitive, OID and evidence occurrences (location, line, offset, and the API context from `additionalContext`).

CBOMKit output can repeat the same component. The parser merges records **only when their `bom-ref` is identical**, unioning their occurrences. It never merges because two findings share an algorithm name. The current raw CBOM has 57 component entries for 30 unique `bom-ref`s; the repeats are byte-identical, and no occurrence is lost in the merge. The CBOM `dependencies` list, whose entries are also repeated, is carried through in `ecdat-assets.json` for the blast-radius stage.

---

## 6. Evidence-aware classification

`classify_cbom.py` uses `services/crypto_classifier.py` and the algorithm knowledge base `knowledge/crypto_knowledge.py` to assign each finding a **category** (e.g. asymmetric, hash, mac, key-derivation, crypto-material) and a **quantum status**:

| Quantum status | Meaning |
|---|---|
| `vulnerable` | Broken by Shor's algorithm |
| `weak` | Classically weak |
| `quantum-aware` | Reduced margin under Grover's algorithm |
| `quantum-resistant` | Not meaningfully weakened by quantum attack |
| `contextual` | Key material whose risk depends on its governing algorithm |
| `unknown` | Not classifiable |

**Purpose** is resolved per finding by `services/purpose_resolver.py` from repository evidence, not from the algorithm name. The evidence tiers, in priority order:

1. `cbom-primitive`: the CBOM primitive, when it maps to exactly one purpose (e.g. `signature`, `hash`). The generic `pke` primitive is deliberately not decisive.
2. `source-context`: the recorded API call context of each occurrence.
3. `algorithm-family-fallback`: the algorithm family's general purposes. This is recorded at **LOW** confidence and explicitly marked as not repository evidence.

If tiers disagree, or occurrences point to different purposes, the result is `conflicting` with `purpose_needs_review = true`. Each classification records `purpose_confidence`, `purpose_evidence_source`, `purpose_evidence_reason` and the supporting evidence.

---

## 7. Explainable quantum risk

`explain_cbom.py` is the **only** place risk is calculated. Every other risk figure in the system is read from its output or re-projected from it, and `check_risk_consistency.py` (60 figures on the current dataset) fails the pipeline on any disagreement.

### 7.1 Base quantum risk

`services/risk_engine.calculate_base_risk()` maps quantum status to a 0–100 score, adds a category adjustment and caps the result at 100. The status scores are:

| Status | Score |
|---|---|
| `vulnerable` | 100 |
| `weak` | 85 |
| `reduced-security-margin` | 50 |
| `contextual` | 40 |
| `quantum-aware` | 25 |
| `quantum-resistant`, `unknown` | 0 |

Severity bands: ≥80 CRITICAL, ≥60 HIGH, ≥30 MEDIUM, otherwise LOW.

### 7.2 RiskContext (per finding)

`models/risk_factors.RiskContext` has five fields. `services/risk_context.derive_risk_context()` builds one **per finding**:

| Field | Source |
|---|---|
| `exposure` | `INTERNET` if the asset type or any occurrence path/API context contains a network/protocol keyword (TLS, SSH, socket, HTTP, X.509, certificate, handshake, …); else `INTERNAL`. |
| `business_criticality` | A **path-derived proxy**: `LOW` if every occurrence is in test/demo/doc/vector-style paths, `HIGH` at 5+ occurrences, else `MEDIUM`. Not the organization's own criticality (see §7.3). |
| `migration_time_years` | Occurrence-count bucket (1/2/4 years), +1 for asymmetric/protocol categories, capped at 10. |
| `data_lifetime_years` | Organization-provided only (§7.3); otherwise **UNKNOWN (`None`)**. |
| `quantum_threat_horizon_years` | A documented fixed default (10), shared by all findings. |

The derivation rules record only the resulting values, not which path or keyword matched.

### 7.3 Business context and unknown values

`services/business_context.py` reads an optional `data/business-context.json`. That file has a `default` entry and per-finding entries under `findings`, keyed by **bom_ref**. Each entry can set `business_criticality` and `data_lifetime_years`. **No such file exists in the repository**, so both values are UNKNOWN for every finding in the current dataset.

Unknown values are never guessed or scored as zero. A weighted factor whose input is unknown is **excluded**, and the remaining weights are rescaled to sum to 1.0. Explanations record every excluded factor and why.

### 7.4 Contextual risk

`services/contextual_risk.calculate_contextual_risk()` computes the final score from these base weights, when every factor is known:

| Factor | Weight | Raw score |
|---|---|---|
| Quantum risk | 40% | Base quantum risk |
| Business criticality | 20% | Path-derived proxy |
| Data lifetime | 15% | 0–20 years mapped linearly to 0–100; excluded while UNKNOWN |
| Exposure | 10% | INTERNAL 50, INTERNET 100 |
| Migration time | 10% | 0–10 years mapped linearly to 0–100 |
| Evidence quality | 5% | See §7.6 |

It uses the same severity bands as §7.1. Because data lifetime is unknown in the current dataset, risk is computed over the other five factors with rescaled weights.

### 7.5 Mosca-style timeline analysis

`services/mosca_analysis.calculate_mosca_risk()` compares *data lifetime + migration time* with the quantum threat horizon:

| Condition | Urgency |
|---|---|
| Total exceeds the horizon | CRITICAL |
| Total ≥ 80% of the horizon | HIGH |
| Total ≥ 50% of the horizon | MEDIUM |
| Otherwise | LOW |

The analysis runs **only when a data lifetime is configured**; otherwise it is recorded as not performed. In the risk record it is informational. In migration priority it is an optional weighted factor (§10). With no business context configured, Mosca analysis is not performed for any current finding.

### 7.6 Evidence quality, confidence and explanation

`services/evidence_engine.py` scores evidence quality out of 100:

| Evidence present | Points |
|---|---|
| Source location | 40 |
| Line number | 20 |
| API context | 25 |
| Multiple occurrences | 15 |

`services/evidence_confidence.py` records a confidence level with reasons. `services/explanation_engine.py` writes the prose summary and a per-factor contribution list (raw score, weight, weighted score, input) that sums to the final score. Unknown factors are listed with `known: false` and a reason.

---

## 8. Blast radius

`services/dependency_graph.py` builds a bidirectional graph from the CycloneDX `ref dependsOn X` relationships. In this CBOM, key material depends on its algorithm, and some algorithms depend on a hash (e.g. `Ed25519 → SHA512`, `HMAC-SHA256 → SHA256`). The current dataset has 19 unique edges.

`services/blast_radius.calculate_blast_radius()` records, per finding, the direct dependencies, direct dependents and transitive dependents (as `bom_ref` sets), and a 0–100 score. The score components:

| Component | Points |
|---|---|
| Direct dependencies | 5 each, max 15 |
| Direct dependents | 10 each, max 30 |
| Transitive dependents | 5 each, max 30 |
| Evidence occurrences | 5 each, max 10 |
| Risk | Risk × 0.15, max 15 |

Levels: ≥75 CRITICAL, ≥50 HIGH, ≥25 MEDIUM. Only recorded CBOM relationships are used; sharing a source file does not create a relationship. The score measures potential dependency impact, not a confirmed code change.

---

## 9. Migration complexity

`services/migration_complexity.calculate_migration_complexity()` is an additive 0–100 score, computed from each finding's **own** risk and blast-radius records, joined by `bom_ref`. Its factors:

| Factor | Basis | Max points |
|---|---|---|
| Cryptographic complexity | Category and purpose | 25 |
| Dependency complexity | Dependents | 35 |
| Migration time | Migration time | 20 |
| Evidence surface | Evidence count | 10 |
| Data-lifetime pressure | Data lifetime; 0 when UNKNOWN | 10 |

Levels: ≥75 CRITICAL, ≥50 HIGH, ≥25 MEDIUM.

---

## 10. Migration priority

`services/migration_priority.calculate_migration_priority()` answers "how urgently should this finding be migrated". Its base weights:

| Factor | Weight | Source |
|---|---|---|
| Quantum risk | 0.32 | §7 |
| Blast radius | 0.28 | §8 |
| Migration complexity | 0.20 | §9 |
| Business criticality | 0.10 | Organization-provided via `business-context.json`; UNKNOWN otherwise |
| Mosca urgency | 0.10 | §7.5; UNKNOWN without a data lifetime |

Unknown factors are excluded and the rest rescaled. With both optional factors unknown, as in the current dataset, this reduces exactly to risk 0.40 / blast radius 0.35 / complexity 0.25. Levels: ≥75 CRITICAL, ≥60 HIGH, ≥40 MEDIUM.

Dashboard **readiness** = the share of findings not at HIGH/CRITICAL priority. It is currently 87%: 4 of 30 findings are HIGH/CRITICAL.

---

## 11. PQC mapping and candidate ranking

- **Registry:** `data/pqc-algorithms.json`, read through `services/pqc_registry.py`, holds seven algorithms:
  - ML-KEM-512/768/1024 (FIPS 203, family `KEM`)
  - ML-DSA-44/65/87 (FIPS 204, family `digital-signature`)
  - SLH-DSA (FIPS 205, family `digital-signature`)
- **Mapping:** `services/pqc_mapper.py` assigns a `migration_type` — `pqc-candidate`, `architectural-migration` (e.g. key material, protocols), `no-direct-pqc-replacement` (e.g. hashes, MACs, KDFs) or `not-applicable` — and lists applicable candidates.
- **Ranking:** `services/pqc_ranker.py` scores each candidate out of 100:

  | Factor | Weight |
  |---|---|
  | Purpose compatibility | 0.30 |
  | Candidate compatibility | 0.25 |
  | Parameter-set suitability | 0.15 |
  | Quantum risk | 0.10 |
  | Blast radius | 0.10 |
  | Inverted migration complexity (100 − complexity) | 0.10 |

  Output is ordered by rank, with per-factor breakdowns.

The ranking model produces **ranking-model candidates**. A ranking-model candidate is **not automatically a migration recommendation**: a finding whose role is unresolved still gets ranked candidates (§12, §13).

---

## 12. Purpose-aware migration strategy

`services/migration_strategy.py`, with policy in `knowledge/migration_strategy_policy.py`, decides one strategy per `bom_ref`. It works from the finding's resolved purpose and cryptographic role, never its algorithm name.

| Strategy | Meaning |
|---|---|
| `KEEP` | No PQC migration. Used for roles with no PQC replacement (hashing, MAC, key derivation, symmetric encryption, random/mask generation), optionally with a classical-hardening note, or when already quantum-resistant. |
| `DIRECT_PQC` | Replace the current primitive with the **selected PQC component** of the role's family (KEM for key establishment / public-key encryption, digital-signature for signatures). |
| `HYBRID` | Run the current primitive and the **selected PQC component** together during a transition. Chosen instead of `DIRECT_PQC` when there is evidence of external interoperability (`INTERNET` exposure) or phased-transition pressure (HIGH/CRITICAL complexity or blast radius). |
| `NEEDS_REVIEW` | Unresolved. The evidence does not support a decision: conflicting or missing purpose, several possible roles needing different families (e.g. an RSA finding that may be encryption or signature), a protocol finding without resolved components, quantum status not confirmed vulnerable, or no suitable candidate. It lists `review_options` per possible role, but **no PQC component is selected**. |

Key material has no strategy of its own. It inherits the strategy of the algorithm it depends on, through the CBOM dependency graph (`inherited_from`). It becomes `NEEDS_REVIEW` if that algorithm needs review, is missing, or several governing algorithms conflict.

Each strategy records its confidence, reason code, rationale, decision factors and an eight-question explanation. On the current dataset the split is **KEEP 5, DIRECT_PQC 5, HYBRID 10, NEEDS_REVIEW 10**. The NEEDS_REVIEW findings are the three RSA algorithms (`RSA`, both `RSA-2048`) and seven key-material findings.

---

## 13. Recommendation state: ranking-model candidate vs. migration recommendation

The plan stage's `make_recommendation()` derives a recommendation from the ranking model alone. On its own, that would present the top ranking-model candidate of a NEEDS_REVIEW finding as `RECOMMENDED`. **`services/recommendation_state.py` is the shared recommendation-state layer** that prevents this. Its `reconcile_recommendation(recommendation, strategy)` restates the record from the authoritative strategy:

| Strategy | `recommendation` record |
|---|---|
| `DIRECT_PQC` / `HYBRID` | `confirmed: true`, `selected_component` = the strategy's PQC component; `candidate` is only ever that component |
| `NEEDS_REVIEW` | `decision: NEEDS_REVIEW`, `candidate: null`, `confirmed: false`, `selected_component: null` |
| `KEEP` | no candidate, `confirmed: false` |

The ranking model's own values are **preserved**, labelled, under `recommendation.ranking_model`. The function is idempotent and leaves records without a strategy unchanged.

It is applied in:
- `generate_pqc_migration_plan.py`
- `generate_migration_report.py`, whose back-fill from ranked candidates runs only for legacy records without a strategy
- `/api/asset/{bom_ref}`, `/api/migration-report/assets` and `/api/migration-report/assets/{bom_ref}`, as a defensive guard
- the AI Advisor context (§16)

`has_selected_pqc_path()` defines **`assets_with_pqc_candidates`**, the dashboard's "PQC Candidates" count: DIRECT_PQC + HYBRID with a selected component. That is currently **15**. NEEDS_REVIEW and KEEP are never counted, even when the ranking model ranked candidates for them.

---

## 14. Source impact, migration actions and the unified report

- **Source impact:** `services/source_crypto_mapper.py` and `services/source_impact_analyzer.py` derive affected files, classes, functions and an impact level from the recorded occurrences.
- **Migration actions:** `services/migration_action_generator.py` generates actions from the migration strategy:
  - DIRECT_PQC and HYBRID get replacement or transition steps for the selected component.
  - NEEDS_REVIEW gets "do not replace until the review is resolved" plus per-role evaluation options.
  - KEEP gets inventory and classical-hardening steps.
  - A legacy path by `migration_type` exists for records without a strategy.
- **Unified report:** `generate_migration_report.py` merges classification, risk, migration impact, PQC mapping, the reconciled recommendation, strategy, ranked candidates, source impact and actions into one record per `bom_ref`. The dashboard and AI Advisor read this file.

---

## 15. Read-only analysis services

All three services take a `bom_ref`, read the generated JSON and **never write to `data/`**; tests verify this with file checksums. They reuse pipeline outputs and existing engines rather than duplicating logic.

### 15.1 What-If Simulator — `services/migration_scenario.py`

- **Question answered:** "what if this finding migrated to PQC option X?"
- **Snapshots:** deep-copied, per finding.
- **Checks:** the option is in the registry, the finding is simulatable (NEEDS_REVIEW and KEEP are rejected with reason codes), and the option's family matches the role's family. Unknown or wrong-family options are rejected.
- **Calculation:** re-runs the **real** contextual-risk and migration-priority engines with the quantum status set to `quantum-resistant`, then reports before/after/delta for risk and priority, and portfolio readiness before/after.
- **Carried forward unchanged, with a stated reason:** blast radius, complexity and Mosca urgency.
- **Model limitation:** the risk model scores quantum status, not the parameter set, so options within one family give identical scores.

### 15.2 Evidence Explorer — `services/evidence_explorer.py`

Answers "why did ECDAT classify, score and recommend this path?" by rearranging recorded values, without recomputing any of them:
- **Identity:** including the raw CycloneDX component and scan metadata
- **Purpose evidence**
- **Source occurrences and dependency references**
- **Quantum status**
- **Risk:** contributions, context with how each value is derived, unknown factors, and Mosca status
- **Blast radius, complexity, priority**
- **Strategy**
- **PQC status:** `selected`, `unresolved`, `not-applicable` or `no-candidate`. Ranked candidates are labelled ranking-model output only when the strategy is NEEDS_REVIEW.
- **Evidence→decision chain:** seven steps, each marked established, low confidence, unresolved, unknown or not applicable.

### 15.3 Blast-radius relationship view — `services/blast_radius_view.py`

For one finding, returns:
- the recorded blast-radius score, severity and breakdown
- recorded complexity
- named nodes for exactly the recorded dependency, direct-dependent and transitive-dependent `bom_ref` sets
- only the CycloneDX `dependsOn` edges between them, with each indirect dependent's recorded `via` link

Findings with no recorded relationships return an explicit empty state. Currently three have none: `x25519`, `x448` and `RSA-OAEP`.

---

## 16. AI Advisor

- **Request:** `POST /api/ai/advice {asset: <bom_ref>}` calls `services/ai_advisor.py`.
- **Context:** `build_context()` reads **only** `ecdat-migration-report.json`, so its figures match the dashboard. It includes risk, purpose (with confidence and review flag), priority, blast radius, complexity, PQC mapping, the migration strategy, source impact and the first five actions.
- **Recommendation handling:** follows the migration strategy:
  - **DIRECT_PQC / HYBRID:** `recommended_candidate` is the selected PQC component.
  - **NEEDS_REVIEW:** no `recommended_candidate`. The top ranking-model candidate appears only as `ranking_model_output`, marked `"NOT A RECOMMENDATION"`.
  - **KEEP:** neither.
- **Prompt:** instructs the model to use only the supplied results, explain (not replace) the strategy, and describe ranking output as not a recommendation.
- **Call:** Ollama `qwen3:14b` at `localhost:11434`, non-streaming, temperature 0.2.
- **Response shape:** `{asset, model, advice}`. The UI renders the advice's RISK / MIGRATION / PQC / ACTIONS / IMPACT / SUMMARY sections under an "AI Analysis" heading.

The output is generated text. ECDAT constrains the context but cannot guarantee the model's wording. See `AI_ADVISOR.md`.

---

## 17. Backend API

Every route reads the generated JSON at request time. Per-finding path parameters are `bom_ref`s.

| Area | Routes |
|---|---|
| Service | `GET /`, `GET /health` |
| Dashboard | `GET /api/status`, `GET /api/summary` (counts, distributions, `assets_with_pqc_candidates`, `high_or_critical_priority_assets`) |
| Stage data | `GET /api/assets[/{bom_ref}]`, `/api/risk[/…]` (legacy basic risk), `/api/priority[/…]`, `/api/complexity[/…]`, `/api/blast-radius[/…]`, `/api/pqc[/…]`, `/api/pqc-ranking[/…]`, `/api/source-impact[/…]`, `/api/actions[/…]`, `/api/migration-actions`, `/api/pqc-migration-plan` |
| Report | `GET /api/migration-report/assets[/{bom_ref}]`; `GET /api/asset/{bom_ref}` (unified finding record: inventory, classification, current risk, risk explanation, migration strategy, reconciled recommendation, impact, ranked candidates, source impact, actions) |
| Evidence | `GET /api/evidence/{bom_ref}` |
| Blast radius view | `GET /api/blast-radius/{bom_ref}/graph` |
| What-If | `GET /api/what-if/findings/{bom_ref}`, `POST /api/what-if/simulate {bom_ref, pqc_option}` (422 with `reason_code` on rejection), `POST /api/what-if/portfolio {replacements}` (API only; not used by the UI) |
| Analysis | `POST /api/analyze {repository, branch}`, `GET /api/analyze/status` (idle/running/completed/failed; no per-stage progress) |
| AI | `POST /api/ai/advice {asset}`; legacy `POST /api/ai/advisor {asset_name}` |

---

## 18. Frontend architecture

- **Stack:** React 19 + Vite 8, Recharts (donuts) and lucide-react (icons), with a single tokenized stylesheet (`App.css`). No router, no global state library, no frontend test runner.
- **`App.jsx`:** owns all dashboard state and effects:
  - initial load of summary, assets, report list and priority
  - loading the selected finding's detail by `bom_ref`
  - analysis-status polling
  - backend health polling
  - AI request state, with a stale-response guard
- **`api.js`:** wraps every endpoint used.
- **Dashboard components:**
  - `Topbar`, `Sidebar`
  - `HeroOverview`: readiness plus stat cards, including "PQC Candidates — Direct PQC or hybrid path selected"
  - `RepositoryAnalysisPanel` with `PipelineStepper` (7 narrative stages; only coarse status is shown)
  - `CriticalFindingsPanel`
  - `DonutPanel` (risk, migration type, source impact)
  - `AssetFilters` and `AssetExplorer` (cards keyed by `bom_ref`)
- **Asset investigation workspace (`AssetDetailPanel`):**
  ```
  [ AssetHeaderBand: identity | risk score | migration priority | migration decision ]
  [ EvidencePanel      ]  [ MigrationFlow (Migration Path) + migration strategy   ]
  [ RiskImpactPanel    ]  [   + WhatIfSimulator                                  ]
  [ BlastRadiusPanel (full width)                                                ]
  [ EvidenceExplorer (full width)                                                ]
  [ AIAdvisorPanel (full width)                                                  ]
  ```
- **Strategy-derived wording:** comes from `migrationStrategy.js`, which only displays the backend's decision:
  - **`strategyPqcPath()`:** the PQC path shown on cards, Critical Findings, the Migration Path node and the AI context line.
  - **`migrationDecisionDisplay()`:** the header fact, as follows:

    | Strategy | Header shows |
    |---|---|
    | DIRECT_PQC / HYBRID | "PQC Recommendation · Direct PQC/Hybrid: ‹selected component›" |
    | NEEDS_REVIEW | "Migration Decision: Needs review" |
    | KEEP | "Migration Decision: No PQC migration" |
- **Migration Path ranking line:** labels ranking output "Ranking-model candidate: … — selected by the migration strategy" or "— not selected: migration requires review".
- **Responsive design:** tested at 1440/1024/768/400px. Wide tables and the What-If comparison scroll inside their own containers; the blast-radius tree switches from a fan-out to a left-rail list at ≤900px.

---

## 19. Testing and validation

- **Backend tests:** 32 `backend/test_*.py` scripts, each runnable as `python test_x.py` from `backend/` (no pytest dependency). `test_api_validation.py` and `test_api_integration.py` need the backend running on `:8000`. The suite covers:
  - classification and purpose resolution, risk context and business context, contextual risk and explanations
  - blast radius, complexity, priority, PQC mapping and ranking, strategy
  - recommendation state
  - What-If, Evidence Explorer and the blast-radius view
  - finding identity, and report/actions/plan consistency
- **Pipeline gate:** `check_risk_consistency.py` runs as stage 13.
- **Frontend checks:** `npm run build` and `npm run lint` (oxlint). UI behavior has been verified with scripted browser sessions (Playwright / Chrome DevTools), not with committed frontend tests.

---

## 20. Known limitations and extension areas

**Current limitations**
- One CBOM at a time, in a fixed file (`data/keycloak-cbom.json`); each analysis overwrites `data/`. The generated `ecdat-*.json` files don't record which repository they came from; only the raw CBOM keeps CBOMKit's metadata (repository URL, commit).
- Discovery depends entirely on CBOMKit and the repository's source. No binary, container, cloud, network or runtime discovery exists.
- Business criticality and data lifetime are UNKNOWN unless configured, so Mosca urgency is currently not computed for any finding.
- The risk context's criticality and exposure are heuristics from paths and API contexts; the specific matching signal is not recorded.
- The What-If model distinguishes PQC families, not parameter sets.
- `/api/analyze/status` has no per-stage progress. There is no authentication, no persistence beyond JSON files, and no frontend unit tests.
- Legacy and duplicate files remain: `main_backup*.py`, `cbom_parser_backup.py`, `score_contextual_cbom.py`, `data-backup/`, stale JSON files, and a stray `h origin ecdat-1` file at the repository root.

**Possible extensions (not implemented)**
- Additional discovery sources: binary or container scanning, cloud KMS/TLS inventory.
- Multi-repository storage and history.
- An editor for organizational business context.
- Per-stage pipeline progress, authentication, and parameter-set-aware risk modelling.

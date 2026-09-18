# ECDAT — Architecture

This document describes the ECDAT implementation **as it currently exists** (branch `ecdat-1`, 2026-09-18), traced through the code. It is descriptive, not aspirational: anything not implemented is listed as a limitation or extension area (§20), not as a capability. The dated history of how the system reached this state — including the bugs found and fixed along the way — is in `CHANGELOG.md`.

ECDAT is a working **prototype**: one repository/CBOM at a time, flat JSON files instead of a database, no authentication, and locally run services.

---

## 1. Scope

### Implemented

- **GitHub repository scanning (§2.1).** A validated GitHub URL + branch is dispatched through a scanner registry to the CBOMKit adapter; the returned CycloneDX CBOM is validated and normalized before the pipeline runs. ECDAT does not scan source code itself; what can be discovered (languages, crypto libraries, API patterns) is whatever CBOMKit supports. The scan reports real per-stage status.
- **CBOM analysis.** A 13-stage Python pipeline turns that CBOM into per-finding classification, explainable quantum risk, blast radius, migration complexity, migration priority, PQC candidate ranking, a purpose-aware migration strategy, migration actions and a unified migration report.
- **FastAPI backend** serving the generated JSON, plus read-only analysis endpoints (What-If Simulator, Evidence Explorer, blast-radius relationship view).
- **React/Vite dashboard** for exploring findings and their evidence.
- **AI Advisor** that sends one finding's already-computed results to a locally hosted Ollama model for a plain-language explanation.

### Not implemented

**Scanner coverage.** Only **Git / GitHub source repositories** have a working scanner, and only while a CBOMKit instance is reachable. ECDAT does **not** scan:

| Target | Status |
|---|---|
| Compiled binaries and firmware | **Not implemented** — declared as a planned target (`status: "not-implemented"`), no scanner exists |
| Dependency / library inventories | **Not implemented** — declared as a planned target, no scanner exists |
| Container images | **Not implemented** — declared as a planned target, no scanner exists |
| Hardware and cloud infrastructure / cloud KMS / TLS inventory | **Not implemented**, and not declared as a planned target |
| Live network traffic, TLS endpoints, running processes | **Not implemented** |

The planned targets are advertised through `GET /api/scan/capabilities` and rendered in the UI as not implemented. No scanner is stubbed, and no capability is simulated: a target with no scanner is rejected with `unsupported-target`.

ECDAT also has no multi-repository history, no user accounts and no database. Organizational business context (business criticality, data lifetime) is **not** discovered automatically; it is only used if an organization supplies it in a configuration file (§7.3), and no such file ships with the repository.

---

## 2. System overview

```
 React dashboard (Vite, :5173)
   │  GET /api/*                  POST /api/scan {repository, branch}
   │  POST /api/what-if/*         POST /api/ai/advice {asset: <bom_ref>}
   ▼
 FastAPI backend  backend/main.py (:8000)
   │
   ├─ reads data/*.json on every request (no cache, no database)
   │
   ├─ /api/scan ──► services/scanning/ScanService (background thread)
   │                  ├─ targets.py     validate the GitHub URL + branch
   │                  ├─ registry.py    pick a scanner for the target kind
   │                  ├─ cbomkit.py ──► CBOMKit (:8081, external)
   │                  │                   POST /api/v1/scan, poll /api/v1/cbom/last/N
   │                  ├─ validation.py  validate + normalize the CBOM
   │                  │                   └─► data/keycloak-cbom.json
   │                  ├─ pipeline.py ──► run_pipeline.py's 13 stages ──► data/ecdat-*.json
   │                  └─ publish        data/ecdat-scan.json, data/ecdat-scan-history.json
   │
   ├─ read-only services: evidence_explorer.py, blast_radius_view.py, migration_scenario.py
   │
   └─ /api/ai/advice ──► services/ai_advisor.py ──► Ollama (:11434, qwen3:14b, external)
```

`backend/main.py` is the single FastAPI application (`uvicorn main:app --reload` from `backend/`). `backend/api/main.py` is a compatibility shim that re-exports the same `app`.

---

## 2.1 The repository scan workflow

`backend/services/scanning/` owns everything between a URL and a finished analysis. The whole flow:

```
GitHub URL → target validation → scanner registry → CBOMKit adapter
  → CBOM validation / normalization → existing 13-stage pipeline → publish → 3D Security Space
```

### 2.1.1 Modules

| Module | Responsibility |
|---|---|
| `targets.py` | Parses and canonicalises a GitHub URL (https/http/`www.`/`.git`/ssh forms) into a `ScanTarget` (kind, owner, repository, branch, slug). Raises `TargetError(code, message)`. |
| `base.py` | The scanner seam: `Scanner` ABC (`key`, `title`, `target_kind`, `requires`, `supports()`, `check_availability()`, `scan()`), plus `Availability`, `ScanArtifact` and `ScannerError(code, message)`. |
| `cbomkit.py` | `CBOMKitClient` (`POST /api/v1/scan`, `GET /api/v1/cbom/last/{n}`) and `CBOMKitRepositoryScanner`, which probes availability, records what CBOMKit already holds, starts the scan, polls for a **newer** CBOM (§2.1.4) and returns it with source metadata. |
| `validation.py` | `validate_cbom()` → `{ok, errors, warnings, stats}`; `normalize_cbom()` → `(normalized, notes)`. |
| `registry.py` | `ScannerRegistry.for_target()` selects a scanner; `capabilities()` returns supported targets with live availability plus `PLANNED_TARGETS` (binary, library, container — all `status: "not-implemented"`). |
| `pipeline.py` | Imports `PIPELINE` from `run_pipeline.py` — the single source of truth for the 13 stages — and runs each as a subprocess, reporting start and end per stage and keeping the output tail of a failure. |
| `service.py` | `ScanService`: the lifecycle, thread-safe state, the record and the history. |

### 2.1.2 Lifecycle and status

`STAGE_DEFINITIONS` in `service.py` defines the seven reported stages:

| Key | Stage | Fails with (the code `error_code` actually carries) |
|---|---|---|
| `target` | Validate repository target | `empty-url`, `unsupported-host`, `malformed-url`, `invalid-branch` (raised by `targets.py` before the scan starts, so the API answers `400`) |
| `scanner` | Select scanner | `no-scanner` — no registered scanner supports the target kind |
| `availability` | Check scanner availability | `scanner-unavailable` — carries the scanner's own detail, e.g. "CBOMKit is not reachable at http://localhost:8081 (ConnectionError)" |
| `scan` | Scan repository (CBOMKit) | `cbomkit-unavailable`, `cbomkit-scan-rejected`, `cbomkit-timeout`, `unsupported-target` (from the scanner), or `scanner-crashed` |
| `validation` | Validate & normalize CBOM | the failing validation code itself (`no-crypto-components`, `missing-bom-ref`, `conflicting-bom-ref`, …), or `cbom-write-failed` |
| `pipeline` | ECDAT analysis pipeline | `pipeline-stage-failed` (naming the stage and its exit code) or `pipeline-stage-timeout` (a stage exceeded `STAGE_TIMEOUT_SECONDS`, 600s, and was stopped) |
| `publish` | Publish scan results | — |

An unexpected exception anywhere in the run is reported as `scan-crashed` rather than leaving the scan wedged.

Each stage carries `pending / running / done / failed`, a human detail line and its own timing; the `pipeline` stage additionally reports the 13 real substage names and which one is running. **Nothing is advanced on a timer.**

**One scan at a time, across processes.** `_claim()` checks the state and takes the slot under a single lock hold, and also takes a lock file (`data/.ecdat-scan.lock`) naming the owning process, so the API server and the CLI cannot both run a pipeline over `data/`. A second API request gets `409`; a second process gets a `RuntimeError` naming the holder. A lock left behind by a process that is no longer running is taken over rather than blocking every later scan.

State is published three ways: `GET /api/scan/status` (live snapshot), `data/ecdat-scan.json` (the last scan record) and `data/ecdat-scan-history.json` (the last 20 scans). Both files are runtime artifacts, regenerated by every scan and git-ignored, and both are written atomically (temp file + `os.replace`) so a crash mid-write cannot truncate them. On startup, a persisted record still saying `running` is closed out as `interrupted` / `scan-interrupted`, because nothing can resume that scan.

### 2.1.3 CBOM validation and normalization

Validation runs **before** the pipeline, so a bad scan cannot overwrite a good analysis.

| Errors (scan stops) | Meaning |
|---|---|
| `not-an-object`, `unsupported-bom-format` | Not a CycloneDX CBOM document |
| `missing-components`, `invalid-components`, `invalid-component` | No usable component list |
| `missing-bom-ref` | A component without a `bom-ref` — ECDAT could not identify it |
| `conflicting-bom-ref` | Two **different** components share one `bom-ref` — identity would be ambiguous |
| `invalid-dependencies` | The `dependencies` entry is not a list of objects |
| `no-crypto-components` | Nothing cryptographic was found, so there is nothing to analyse |

| Warnings (scan continues) | Meaning |
|---|---|
| `missing-bom-format`, `missing-spec-version` | Metadata absent; the document is still usable |
| `repeated-component-entry` | The same component appears more than once, byte-identical. CBOMKit does this routinely — the current CBOM has 27 — and `cbom_parser.py` merges them by `bom_ref` (§5), so each is analysed once |
| `missing-dependencies` | No `dependencies` list; blast radius will find no edges |
| `dangling-dependency-ref` | A dependency references a `bom-ref` that has no component |

`stats` reports `components`, `crypto_components`, `findings` (unique cryptographic `bom_ref`s — the number the dashboard shows), `dependency_entries`, `dependency_edges`, `unique_bom_refs` and `asset_types`.

**Dependency terminology** (three different numbers, all correct, so each is named consistently):

| Term | Meaning | Current CBOM |
|---|---|---|
| **Recorded dependency entries** | Objects in the CycloneDX `dependencies` array — one per `ref`, repeated by CBOMKit as often as it observed the relationship | 29 |
| **Recorded `dependsOn` references** (`dependency_edges` in `stats`) | Every `dependsOn` reference across those entries, counted as written | 29 |
| **Unique dependency edges** | Distinct `(ref, dependsOn)` pairs — what `dependency_graph.py` builds the blast radius from, and what the security map draws as links | 15 |

The scan panel reports recorded entries (what the scanner produced); the map and blast radius report unique edges (what the analysis uses). A CBOM whose entries are all distinct makes the two numbers equal.

`normalize_cbom()` only adds missing `components` / `dependencies` containers, returns a copy, and never mutates the input or edits a value. ECDAT does not repair, infer or invent CBOM content.

### 2.1.4 CBOM freshness: a scan never reuses a pre-scan CBOM

CBOMKit keeps every CBOM it has produced and serves them from `/api/v1/cbom/last/{n}`, so a repository scanned before always has a record waiting the instant a new scan is requested. Accepting it would report an older commit's findings as the result of the scan just run.

The scanner therefore:

1. records what CBOMKit already holds for this git URL + branch **before** `POST /api/v1/scan` — its `createdAt`, `commit` and `projectIdentifier`;
2. polls (real HTTP, unchanged interval) and accepts an entry only when it is **demonstrably later**: a newer `createdAt`, or a different commit / project identifier;
3. if CBOMKit keeps the record it already had — a legitimate answer for an unchanged commit — waits `accept_cached_after` (900s — measured CBOMKit re-scans take 3-10 minutes, so a shorter window would label a result cached while a fresh CBOM was still coming) before using it, and then labels it `freshness: "cbomkit-cached"` with `cbom_created_at`, which the completion message and the scan panel both state plainly;
4. otherwise fails with `cbomkit-timeout` rather than quietly analysing stale data.

`source.freshness` is therefore always one of `fresh-scan` or `cbomkit-cached`, and the UI never presents the second as the first.

### 2.1.5 Adding a scanner

A new target kind needs one class implementing `Scanner` — `check_availability()` and `scan(target, progress)` returning a `ScanArtifact` — registered in the registry, plus a target parser if its identifier is not a Git URL. The service, the API, the status payload and the UI need no change. Until such a scanner exists, the target stays in `PLANNED_TARGETS` and is reported as not implemented; it is never stubbed.

---

## 3. Canonical finding identity: `bom_ref`

Every finding is identified by its CycloneDX `bom-ref` (stored as `bom_ref`). Algorithm names are **not** identities: the current dataset contains two distinct `RSA-2048` findings (`afc4f1a7…`, `9eae7f2e…`) with different source locations and different dependent keys, plus unnamed key-material findings (`private-key@…`, `public-key@…`).

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

**Static inputs:** `data/keycloak-cbom.json` holds the raw CBOM. The filename is fixed regardless of which repository was scanned — the scan service writes every new CBOM there, which is why no analysis module had to change — and the current file comes from a CBOMKit scan of `pyca/cryptography` at commit `39138c6`. `data/pqc-algorithms.json` is the PQC registry.

**Scan runtime artifacts:** `data/ecdat-scan.json` and `data/ecdat-scan-history.json` are written by the scan service (§2.1.2), not by the pipeline. They are machine-generated per scan and git-ignored; no pipeline stage reads them.

**Removed (2026-09-18):** four `data/` files that no code read — verified by searching every reader in `backend/` and `frontend/src/` before deleting:
- `ecdat-contextual-risk-assets.json`, read only by the deprecated `score_contextual_cbom.py`, which is not in `PIPELINE` and is called by nothing
- `ecdat-risk-summary.json`, read only by `generate_summary.py`, likewise not in the pipeline and called by nothing
- `cbom_parser.py.json` and `cbomkit-test.json`, which had no reader at all

The two deprecated scripts themselves were **kept**: they still run standalone and regenerate their own output, so removing only the stale data costs nothing. A stray `h origin ecdat-1` file (a `less` help screen committed by accident in `d75a348`) was removed from the repository root at the same time.

`data-backup/` and `demo/` are manual snapshots.

The stages are deterministic for a given input: when stages 6–13 were re-run on unchanged inputs during development, they reproduced byte-identical outputs. Dependency lists are sorted so set ordering cannot vary between runs.

---

## 5. CBOM parsing and duplicate handling

`cbom_parser.py` reads the CycloneDX `components` and `dependencies`. For each component it extracts `bom_ref`, name, type, `assetType`, primitive, OID and evidence occurrences (location, line, offset, and the API context from `additionalContext`).

CBOMKit output can repeat the same component. The parser merges records **only when their `bom-ref` is identical**, unioning their occurrences. It never merges because two findings share an algorithm name. The current raw CBOM has 47 component entries for 25 unique `bom-ref`s; the repeats are byte-identical, and no occurrence is lost in the merge. The CBOM `dependencies` list, whose entries are also repeated, is carried through in `ecdat-assets.json` for the blast-radius stage.

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

`explain_cbom.py` is the **only** place risk is calculated. Every other risk figure in the system is read from its output or re-projected from it, and `check_risk_consistency.py` (50 figures on the current dataset) fails the pipeline on any disagreement.

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

`services/dependency_graph.py` builds a bidirectional graph from the CycloneDX `ref dependsOn X` relationships. In this CBOM, key material depends on its algorithm, and some algorithms depend on a hash (e.g. `Ed25519 → SHA512`, `Ed448 → SHAKE256`, `HKDF-SHA256 → SHA256`). The current dataset has 15 unique edges.

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

Dashboard **readiness** = the share of findings not at HIGH/CRITICAL priority. It is currently 88%: 3 of 25 findings are HIGH/CRITICAL (1 CRITICAL, 2 HIGH).

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

Each strategy records its confidence, reason code, rationale, decision factors and an eight-question explanation. On the current dataset the split is **KEEP 4, DIRECT_PQC 5, HYBRID 6, NEEDS_REVIEW 10**. The NEEDS_REVIEW findings are the three RSA algorithms (`RSA`, both `RSA-2048`) and seven key-material findings.

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

`has_selected_pqc_path()` defines **`assets_with_pqc_candidates`**, the dashboard's "PQC Candidates" count: DIRECT_PQC + HYBRID with a selected component. That is currently **11**. NEEDS_REVIEW and KEEP are never counted, even when the ranking model ranked candidates for them.

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
| Scanning | `POST /api/scan {repository, branch}` (400 `{reason_code, reason}` on an invalid target, 409 while a scan is running), `GET /api/scan/status` (real per-stage progress, §2.1.2), `GET /api/scan/capabilities` (supported targets with live availability + not-implemented targets), `GET /api/scan/history` (last 20 scans) |
| Analysis (aliases) | `POST /api/analyze {repository, branch}`, `GET /api/analyze/status` — the original routes, kept with their original response keys (`status`, `repository`, `branch`, `message`, `error`) and extended with the scan payload |
| AI | `POST /api/ai/advice {asset}`; legacy `POST /api/ai/advisor {asset_name}` |

---

## 18. Frontend architecture

- **Stack:** React 19 + Vite 8, Recharts (donuts), lucide-react (icons) and three.js for the shared 3D security space (lazily loaded, so the dashboard's first paint does not wait on it). One tokenized stylesheet (`App.css`) plus the spatial stylesheets. No router, no global state library, no frontend test runner.
- **Layout modes (`spatial/stage/useLayoutMode.js`):** the shared `SpatialStage` at ≥1025px (desktop) and 601–1024px (a simpler tablet stage); the scrolling layout at ≤600px, when WebGL is unavailable, and if the WebGL context is lost. All content stays in accessible HTML outside the canvas in every mode.
- **3D engine (`spatial/engine/`):** exactly **one** `WebGLRenderer`, canvas, camera and control set, rendered on demand. Environment, posture, landscape, investigation and simulation layers plug into it; nothing is drawn that is not backed by a record from the API.
- **`App.jsx`:** owns all dashboard state and effects:
  - initial load of summary, assets, report list and priority
  - loading the selected finding's detail by `bom_ref`
  - scan status polling, plus scan capabilities and history, and adoption of a scan already running when the page loads
  - backend health polling
  - AI request state, with a stale-response guard
- **`api.js`:** wraps every endpoint used.
- **Dashboard components:**
  - `Topbar`, `Sidebar`
  - `HeroOverview`: readiness plus stat cards, including "PQC Candidates — Direct PQC or hybrid path selected"
  - `RepositoryAnalysisPanel` — the **Scan a Repository** workflow (§2.1): the scanner-capability line including the not-implemented targets, the URL/branch form, `PipelineStepper` rendering the backend's **real** seven stages with their details and the live pipeline substage, the failure reason code, the completed scan's counts and source, validation warnings, an **Open in Security Space** action that focuses the freshly analysed dataset, and recent scan history. Every value shown comes from `/api/scan/status` or `/api/scan/capabilities`; none is simulated client-side.
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

- **Backend tests:** 36 `backend/test_*.py` scripts, each runnable as `python test_x.py` from `backend/` (no pytest dependency). No test needs a dev server or a particular scan: `test_api_validation.py` and `test_api_integration.py` start the real app themselves on a free port, over the fixture dataset.
- **The fixture dataset** (`backend/fixture_dataset.py`) is how the analysis tests stay true whatever ECDAT last scanned. It defines a small, hand-written CBOM whose findings cover the situations under test — a key agreement, two *different* findings that share the name "RSA-2048", a TLS-exposed signature with key material that inherits its strategy, a hash and a MAC — and runs it through the **real** 13-stage pipeline in an isolated copy of `backend/` under the system temp directory. Tests address findings by role (`fixture_dataset.ref("x25519")`) and derive counts from the fixture, never from a bom_ref or total copied from one scan; `data/` is neither read nor written. The dataset is cached and rebuilt automatically whenever the fixture or any production module changes.
  The suite covers:
  - scan targets and the scanner registry (`test_scan_targets.py`), CBOM freshness and provenance against a fake CBOMKit (`test_cbomkit_freshness.py`), CBOM validation and normalization against the CBOM currently in `data/` (`test_cbom_validation.py`), and the scan lifecycle, concurrency, stage timeout and atomic writes against fake scanners and a fake pipeline runner (`test_scan_service.py`)
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
- One CBOM at a time, in a fixed file (`data/keycloak-cbom.json`); each scan overwrites `data/`. The generated `ecdat-*.json` files don't record which repository they came from; the raw CBOM keeps CBOMKit's metadata and `data/ecdat-scan.json` records the target of the last scan.
- Discovery depends entirely on CBOMKit and the repository's source. No binary, library, container, hardware, cloud, network or runtime scanner exists; those targets are declared not implemented (§1).
- A scan needs a reachable CBOMKit instance. There is no bundled CBOMKit deployment in this repository, and the scan fails at the availability stage when none is running.
- Business criticality and data lifetime are UNKNOWN unless configured, so Mosca urgency is currently not computed for any finding.
- The risk context's criticality and exposure are heuristics from paths and API contexts; the specific matching signal is not recorded.
- The What-If model distinguishes PQC families, not parameter sets.
- There is no authentication, no persistence beyond JSON files, and no frontend unit tests.
- Legacy files remain in `backend/`: `main_backup*.py`, `cbom_parser_backup.py`, `score_contextual_cbom.py`, `generate_summary.py`, plus `data-backup/`. They are unreferenced but still runnable, so they were left in place; the stale `data/` outputs they once produced were removed (§4).

**Possible extensions (not implemented)**
- Additional discovery sources — binary, library, container, hardware or cloud KMS/TLS scanners — added behind the `Scanner` interface (§2.1.5).
- Multi-repository storage and history.
- An editor for organizational business context.
- Authentication, and parameter-set-aware risk modelling.

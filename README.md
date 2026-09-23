# ECDAT

**Cryptographic Discovery and Post-Quantum Migration Analysis**

Submitted for **SIH Problem Statement 26164**.

**QRYPTA** is the product; **ECDAT** is the engine inside it that does the cryptographic discovery and post-quantum migration analysis. This repository is that engine, and every name in the code, API and UI is ECDAT's.

ECDAT points at a public GitHub repository, discovers the cryptography it actually uses, and turns that into an explainable post-quantum migration analysis: what is at risk, why, what depends on it, what it should become, and what a developer has to change. Every figure it shows is computed from recorded evidence — ECDAT never guesses a value it cannot observe, and says so when it cannot.

ECDAT is a working **prototype**: one repository at a time, flat JSON files instead of a database, no authentication, and all services running locally.

---

## What it does

```
GitHub URL
  → target validation          canonicalise owner / repository / branch
  → scanner registry           select a scanner for the target kind
  → CBOMKit                    scan the source, return a CycloneDX CBOM
  → CBOM validation            reject an unusable CBOM before anything is overwritten
  → 13-stage ECDAT pipeline    classification → risk → impact → PQC → strategy → actions
  → FastAPI                    serve the results
  → React dashboard            explore them, in a shared 3D security space
```

### Key capabilities

| Capability | What it actually does |
|---|---|
| **Real CBOMKit integration** | A validated GitHub URL is sent to a separately running CBOMKit instance (`POST /api/v1/scan`), and ECDAT polls (`GET /api/v1/cbom/last/{n}`) for the CBOM **that scan** produced. A CBOM CBOMKit already held is never passed off as a new scan: it is accepted only if its record is demonstrably newer, and a genuinely cached result is labelled as cached in the status message and the UI. |
| **13-stage analysis pipeline** | CBOM parsing → classification → explainable risk → legacy risk view → blast radius → migration complexity → migration priority → PQC mapping → PQC ranking → migration plan → migration actions → unified report → risk-consistency check. Every stage is a separate script, reported individually while a scan runs. |
| **Quantum-risk analysis** | One risk calculation (`explain_cbom.py`), weighting base quantum risk, a path-derived criticality proxy, data lifetime, exposure, migration time and evidence quality. Factors ECDAT cannot observe are **excluded and the weights rescaled**, never scored as zero, and each contribution is recorded. A pipeline gate fails the build if any risk figure disagrees anywhere. |
| **Migration strategies** | One authoritative decision per finding: `KEEP`, `DIRECT_PQC`, `HYBRID` or `NEEDS_REVIEW`, derived from the finding's resolved purpose — never from its algorithm name. Key material inherits the strategy of the algorithm it depends on. |
| **PQC migration analysis** | Seven registry algorithms (ML-KEM-512/768/1024, ML-DSA-44/65/87, SLH-DSA; FIPS 203/204/205) scored on purpose compatibility, parameter suitability, risk, blast radius and complexity. A ranked candidate is **not** a recommendation: a `NEEDS_REVIEW` finding still gets ranked candidates, and ECDAT labels them "Ranking-model candidate — not selected". |
| **Evidence Explorer** | A read-only "why": the raw CycloneDX component, purpose evidence and confidence, source occurrences, risk contributions with unknowns kept explicit, and a seven-step evidence→decision chain. Nothing is recomputed — it rearranges what the pipeline recorded. |
| **Blast Radius** | Direct dependencies, direct dependents and transitive dependents built **only** from recorded CycloneDX `dependsOn` relationships, with a 0–100 impact score. Sharing a source file does not create an edge, and findings with no relationships say so. |
| **What-If simulator** | Re-runs the real risk and priority engines on a deep copy to answer "what if this migrated to PQC option X", showing before/after/delta plus portfolio readiness. It is labelled a simulation and **cannot** change the dataset; a test checksums `data/` around every simulation. |
| **3D Security Space** | The findings as a navigable spatial landscape — one WebGL renderer, one canvas, rendered on demand — with docked HTML panels. All content stays in accessible HTML outside the canvas, and the layout falls back to a scrolling dashboard on small screens or without WebGL. |
| **AI Advisor** | Sends one finding's already-computed results to a locally hosted Ollama model (`qwen3:14b`) for a plain-language explanation. It explains ECDAT's decision rather than making one: a `NEEDS_REVIEW` finding's ranking output is passed in marked "NOT A RECOMMENDATION". |

### `bom_ref` is the only identity

Algorithm names repeat — the current dataset holds two distinct `RSA-2048` findings in different files. Every join, API route, UI selection, What-If run, Evidence lookup and blast-radius query is keyed by the CycloneDX `bom-ref`, so two findings that share a name never contaminate each other.

---

## Scanning scope

| Target | Status |
|---|---|
| **Git / GitHub source repositories** | **Implemented** — via the CBOMKit adapter, while a CBOMKit instance is reachable |
| Compiled binaries and firmware | **Not implemented** — declared as a planned target; no scanner exists |
| Dependency / library inventories | **Not implemented** — declared as a planned target; no scanner exists |
| Container images | **Not implemented** — declared as a planned target; no scanner exists |
| Hardware, cloud infrastructure, cloud KMS/TLS | **Not implemented**, and not declared as a planned target |
| Live network traffic, TLS endpoints, running processes | **Not implemented** |

`GET /api/scan/capabilities` returns the planned targets with `status: "not-implemented"`, and the UI prints them. No scanner is stubbed and no capability is simulated — a target with no scanner is rejected. Adding one means implementing a single `Scanner` interface (`check_availability`, `scan`) and registering it; the service, API and UI need no change.

---

## Setup

**Prerequisites:** Python 3.14, Node.js (Vite 8 / React 19), Docker (for CBOMKit), and optionally Ollama for the AI Advisor.

### Ports

| Service | Port | Required for |
|---|---|---|
| ECDAT backend (FastAPI) | `8000` | everything |
| ECDAT frontend (Vite dev server) | `5173` | the dashboard |
| CBOMKit | `8081` | scanning a repository |
| Ollama (`qwen3:14b`) | `11434` | the AI Advisor |

The backend accepts browser requests only from the local dev origins (`5173`, `5174`, `5199`, `4173` on `localhost`/`127.0.0.1`); add more with `ECDAT_ALLOWED_ORIGINS` (comma-separated).

### 1. Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate            # Windows;  source venv/bin/activate on POSIX
pip install -r requirements.txt
uvicorn main:app --reload        # http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### 3. CBOMKit (needed only to scan)

CBOMKit is a separate service and is **not** bundled with this repository. Run it with Docker so its API is reachable on `localhost:8081` — the backend and frontend both work without it, using the committed dataset, and the scan panel states plainly when it is unreachable. Point ECDAT at a different instance with `ECDAT_CBOMKIT_URL`.

```bash
curl http://localhost:8081/api/v1/cbom/last/1     # 200 = CBOMKit is up
```

### 4. Ollama (needed only for AI Analysis)

```bash
ollama pull qwen3:14b
ollama serve                     # http://localhost:11434
```

---

## Scanning a repository

**From the dashboard:** open the **Operations** dock, enter a GitHub URL and branch, and press **Scan Repository**. The panel reports the seven real stages as they happen — target, scanner, availability, scan, validation, pipeline (with its 13 substages), publish — then the findings, components, dependency entries and duration, and **Open in Security Space** takes you into the analysed dataset.

**From the CLI:**

```bash
cd backend
python analyze_repository.py https://github.com/owner/repository main
python cbomkit_client.py https://github.com/owner/repository main   # fetch + validate a CBOM only
python run_pipeline.py                                              # re-run the 13 stages on data/
```

A scan takes as long as CBOMKit takes (seconds to ~10 minutes depending on the repository). One scan runs at a time: a second request gets `409`, and a second process is refused by name.

### Scan API

| Route | Purpose |
|---|---|
| `POST /api/scan {repository, branch}` | Start a scan (`400 {reason_code, reason}` on a bad target, `409` while one runs) |
| `GET /api/scan/status` | Real per-stage progress, validation result, counts and provenance |
| `GET /api/scan/capabilities` | Supported targets with live availability, plus not-implemented targets |
| `GET /api/scan/history` | The last 20 scans |

`POST /api/analyze` and `GET /api/analyze/status` remain as aliases.

---

## Testing

```bash
cd backend
python test_<name>.py            # each of the 37 test scripts runs standalone
python check_risk_consistency.py # the pipeline's own risk-agreement gate
```

No test needs the dev server or any particular scan. Analysis tests read a **fixture dataset** (`backend/fixture_dataset.py`): a small purpose-built CBOM run through the real 13-stage pipeline in an isolated copy of `backend/`, so results stay true whatever ECDAT last scanned. The two API tests start their own FastAPI server on a free port over that fixture.

```bash
cd frontend
npm test                         # Vitest: theme system, ECDAT AI panel, 3D palette
npm run lint
npm run build
```

---

## Current demo dataset

`data/keycloak-cbom.json` (the filename is fixed and historical) holds a CBOMKit scan of **`keycloak/keycloak`, branch `main`, commit `b4242ba`**:

- **59 findings** from 59 raw component entries — 30 algorithms, 28 related-crypto-material, 1 protocol
- **37 recorded dependency entries**, giving **37 unique dependency edges**; 10 findings have none (`AES`, `ECDH`, `MD5` and others)
- **Risk severity:** 1 CRITICAL, 15 HIGH, 41 MEDIUM, 2 LOW
- **Strategies:** NEEDS_REVIEW 29, KEEP 18, DIRECT_PQC 6, HYBRID 6
- **PQC candidates** (selected paths): 12 · **388** generated migration actions
- **Key material:** 28 findings inherit the strategy of the algorithm they depend on
- **Priority:** 3 findings HIGH/CRITICAL (1 CRITICAL, 2 HIGH) → **95% readiness**
- **Mosca / business criticality:** UNKNOWN — no `data/business-context.json` is configured, so those factors are excluded from priority rather than guessed

The identity guarantee that two findings sharing an algorithm name stay
separate is asserted against the deterministic fixture
(`backend/fixture_dataset.py`), not against this dataset, so it holds whatever
repository is scanned.

---

## Known limitations

- **One repository at a time.** Each scan overwrites `data/`; there is no multi-repository history. The generated files do not record their source repository — the raw CBOM and `data/ecdat-scan.json` do.
- **Discovery is only as good as CBOMKit**, and only for source repositories. Binary, library, container, hardware, cloud, network and runtime scanning are not implemented.
- **Private repositories are not supported.** CBOMKit accepts credentials and a subfolder; ECDAT sends neither.
- **Business criticality and data lifetime are UNKNOWN** unless an organization supplies `data/business-context.json`, so Mosca-style urgency is not computed for the current dataset. The criticality and exposure inputs that *are* derived are path/API-context heuristics.
- **The What-If model distinguishes PQC families, not parameter sets**, so options within one family score identically.
- **The AI Advisor's text is generated.** ECDAT constrains the context but cannot guarantee the model's wording, and Ollama occasionally returns a transient error — the panel surfaces the failure with a Retry.
- **No authentication and no database.** Results are flat JSON files. The frontend suite (`npm test`) covers the theme system, the assistant panel and the 3D palette, not the whole UI — the 3D scene itself is verified in a browser, since jsdom has no WebGL.
- **Only the scan-state files are written atomically** (`data/ecdat-scan.json`, `data/ecdat-scan-history.json`, via `os.replace`). The pipeline's stage outputs are written non-atomically, so an interrupted pipeline is recovered by re-running it.

---

## Documentation

| Document | Contents |
|---|---|
| `docs/ARCHITECTURE.md` | The implementation traced through the code: scan workflow, pipeline stages, formulas, API, frontend |
| `docs/PROJECT_CONTEXT.md` | What the codebase does today, terminology, dataset snapshot, boundaries |
| `docs/AI_ADVISOR.md` | AI Advisor implementation detail |
| `docs/CHANGELOG.md` | Dated history, including bugs found and fixed |
| `docs/TODO.md` | Open issues |

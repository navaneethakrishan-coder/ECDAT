# ECDAT — AI Migration Advisor (current implementation)

Traced from these files, as of 2026-09-17:
- `backend/services/ai_advisor.py`, `backend/services/recommendation_state.py`, `backend/main.py`
- `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/src/components/AIAdvisorPanel.jsx`

The dated history of how the advisor reached this state is in `CHANGELOG.md`.

The AI Advisor produces an **AI Analysis**: a plain-language explanation of ECDAT's already-computed results for one finding. It does not make migration decisions and does not always produce a migration recommendation. The migration decision is the finding's **migration strategy** (`KEEP`, `DIRECT_PQC`, `HYBRID` or `NEEDS_REVIEW`), computed by the pipeline; the advisor is instructed to explain it, not replace it.

## Endpoint

- **Path:** `POST /api/ai/advice`
- **Defined in:** `backend/main.py`, the single FastAPI app. `backend/api/main.py` only re-exports the same `app`.
- **Legacy route:** the older `POST /api/ai/advisor` (body `{asset_name}`) still exists. The frontend doesn't use it, and it calls the same `generate_advice()`.
- **CORS:** open (`allow_origins=["*"]`).

### Request format

```json
{ "asset": "<finding bom_ref>" }
```

- **Model:** `AIAdviceRequest { asset: str }`. The field is named `asset` for backward compatibility, but its value is the finding's **`bom_ref`**, the canonical finding identity, not an algorithm or asset name.
- **Frontend:** always sends the selected finding's `bom_ref`, because findings are selected by `bom_ref` in `AssetExplorer` and `CriticalFindingsPanel`.
- **Why this matters:** the current dataset has two distinct `RSA-2048` findings, so a name would be ambiguous.

### Response format

```json
{
  "asset": "<echoed bom_ref, as sent>",
  "model": "qwen3:14b",
  "advice": "<raw text returned by Ollama, stripped of surrounding whitespace, otherwise unprocessed>"
}
```

### Errors

- **`/api/ai/advice`:** any exception (Ollama not running, `requests` timeout or HTTP error, a missing or corrupt report file) becomes **HTTP 500** with `detail: "AI advisor failed: <str(exc)>"`. Failure modes are not distinguished.
- **Unmatched `bom_ref`:** a `bom_ref` that matches no finding (including an algorithm name sent instead) is **not** an error. `build_context()` returns only `{"asset": "<value sent>"}`, and the model is still called with that minimal context.
- **`/api/ai/advisor` (legacy):** maps `FileNotFoundError`/`ValueError` to 404 and other exceptions to 500.

## Ollama integration

- **URL:** `http://localhost:11434/api/generate`, the hardcoded constant `OLLAMA_URL` in `services/ai_advisor.py`. It can't be set via environment or settings.
- **Model:** `qwen3:14b`, the hardcoded constant `MODEL`.
- **Call parameters:**
  ```json
  {
    "model": "qwen3:14b",
    "prompt": "<see below>",
    "stream": false,
    "think": false,
    "options": { "temperature": 0.2, "num_predict": 300 }
  }
  ```
- **Timeout:** 300 seconds.
- **Endpoint style:** Ollama's native `/api/generate`, non-streaming. The frontend sees nothing until the full completion finishes.

## Context assembled before prompting (`build_context`)

- **Data source:** the advisor reads exactly **one** file, `data/ecdat-migration-report.json`. That is the unified per-finding report the dashboard and `/api/asset/{bom_ref}` are built from, so the advisor's figures cannot diverge from the dashboard's.
- **Lookup:** `find_report_asset()` matches the requested value against each record's **`bom_ref`**, exactly (after trimming surrounding whitespace; not case-insensitive, and never by name).

For a matched finding, the context contains:

1. `asset` (the finding's name) and `bom_ref`.
2. `risk = { score, severity, quantum_status, category }`, from `current_risk` and `classification`.
3. `purpose = { resolved, usage, confidence, evidence_source, needs_review }`: how the finding's cryptographic purpose was resolved and how confident that is.
4. `priority = { priority_score, priority }`, `blast_radius = { score, severity }`, `complexity = { score, level }`, from `migration_impact`.
5. `pqc = { migration_type, pqc_applicable, confidence }`, plus the strategy-dependent fields described below.
6. `migration_strategy = { strategy, label, role, classical_component, pqc_component, confidence, rationale, harvest_now_decrypt_later, classical_hardening }`.
7. `source_impact = { impact_level, affected_file_count, affected_class_count, affected_function_count }`.
8. `actions`: the first 5 migration actions.

### Recommendation semantics (strategy-authoritative)

The PQC candidate-ranking model ranks candidates for every PQC-applicable finding, including findings whose migration decision is unresolved. A **ranking-model candidate is not automatically a migration recommendation**, so `build_context()` derives the PQC fields from the finding's **migration strategy** (using `selected_pqc_component()` and `strategy_name()` from `services/recommendation_state.py`):

| Strategy | `context.pqc.recommended_candidate` | `context.pqc.ranking_model_output` |
|---|---|---|
| `DIRECT_PQC` / `HYBRID` | **Present.** `candidate` is the strategy's **selected PQC component**, which is the migration recommendation. It also includes `strategy`, `family`, `confidence` and, when that component appears in the finding's ranked candidates, its `rank`, `score`, `compatibility` and `tradeoffs`. | Absent |
| `NEEDS_REVIEW` | **Absent.** No PQC component is selected until the cryptographic role is confirmed. | Present only if the ranking model ranked candidates: `{ top_ranked_candidate, family, score, status: "NOT A RECOMMENDATION", note }`, stating that it is ranking-model output only |
| `KEEP` | **Absent.** No PQC migration recommendation. | Absent |

So the model never receives contradictory context such as `strategy = NEEDS_REVIEW` alongside a `recommended_candidate`. On the current dataset the NEEDS_REVIEW findings (the RSA and both RSA-2048 findings, plus seven key-material findings) get no `recommended_candidate`. For example, DSA (HYBRID) gets `ML-DSA-65`, x25519 (DIRECT_PQC) gets `ML-KEM-768`, and SHA256 (KEEP) gets neither field.

**Legacy fallback:** a report record with **no** `migration_strategy` (a dataset generated before strategies existed) takes `recommended_candidate` from the record's `recommendation.candidate`, as before. Records generated by the current pipeline always have a strategy.

## Prompt template

```
You are the ECDAT AI Migration Advisor.

Use ONLY the supplied ECDAT results as factual
information.

Do not invent scores, assets, dependencies,
PQC algorithms, or migration decisions.

The supplied "purpose" field shows how this finding's cryptographic
purpose was resolved and how confident that resolution is. If its
confidence is LOW or needs_review is true, say so plainly rather than
stating the purpose as settled fact.

The supplied "migration_strategy" field is ECDAT's evidence-based
migration decision (KEEP, DIRECT_PQC, HYBRID or NEEDS_REVIEW). Explain
that decision; do not recommend a different strategy or PQC algorithm.
If it is NEEDS_REVIEW, say that the cryptographic role must be
confirmed before any replacement is chosen.

Asset:
<the value sent in the request, i.e. the bom_ref>

ECDAT results:
<compact single-line JSON dump of the context object>

Give a concise developer-oriented answer.

Use exactly these sections:

RISK:
Explain the current risk.

MIGRATION:
Explain the ECDAT migration decision.

PQC:
Explain the recommended PQC candidate only if "recommended_candidate"
is supplied. If only "ranking_model_output" is supplied, state that it
is ranking-model output, not a recommendation, and that no PQC
candidate is selected until the review is resolved.

ACTIONS:
Give the most important developer actions.

IMPACT:
Explain the expected source-code or architectural impact.

SUMMARY:
Give one short recommendation.
```

The prompt is a single f-string built per request. There is no separate system prompt, no conversation history and no retry or self-check step.

The output is generated text: ECDAT constrains the context and instructions but cannot guarantee the model's wording. In a live check for an RSA-2048 (NEEDS_REVIEW) finding, the PQC section described ML-DSA-65 as ranking-model output, "not a formal recommendation", with no candidate selected until the role is confirmed. `num_predict: 300` can truncate later sections, and nothing detects this.

## Frontend integration

- **API client:** `frontend/src/api.js` → `getAIAdvice(assetName)` sends `POST /api/ai/advice` with `{asset: assetName}`. `App.jsx` calls it with `selectedAsset`, which holds the selected finding's **`bom_ref`**. On a non-2xx response it throws `Error(detail)`, falling back to `"AI advice request failed: <status>"`.
- **Placement:** `AIAdvisorPanel.jsx` is rendered by `AssetDetailPanel.jsx` as the last, full-width panel of the asset investigation workspace, below the Blast Radius panel and Evidence Explorer.
- **Panel header:** "AI Migration Advisor", a static model badge ("Qwen3:14B · Ollama") and an availability label derived from the request state (Ready / Analyzing / Unavailable). The label is not an Ollama health check.
- **Context line:** "Analyzing ‹name› (‹primitive›) — ‹risk› risk, ‹priority› priority, PQC → ‹path›". The PQC path comes from the migration strategy through `strategyPqcPath()` in `migrationStrategy.js`:
  - the selected component for DIRECT_PQC/HYBRID
  - "Needs review" for NEEDS_REVIEW
  - "No PQC migration" for KEEP

  It never shows a ranking-model candidate as the path. (A fallback to `recommendation.candidate` applies only to legacy data without strategies.)
- **State machine:** `App.jsx` holds a single `aiStatus` (`"idle" | "loading" | "success" | "error"`).
  - **Idle:** the button reads **"Get AI Analysis"**.
  - **Loading:** the button reads "Generating..." and is disabled. A loading block shows "Qwen3:14b is analyzing this cryptographic asset..." with a note that this can take a few minutes.
  - **Success:** the answer is shown under the heading **"AI Analysis"**, with "Powered by ‹model›" (the API's echoed `model` value) and a **Regenerate** button.
  - **Error:** an **"AI analysis failed"** block with the error message and a **Retry** button.
- **Duplicate-request guard:** `handleGenerateAIAdvice` returns early while `aiStatus === "loading"`, in addition to the disabled button.
- **Stale-result guard:** `selectedAssetRef` tracks the currently selected `bom_ref`. A response for a finding that is no longer selected is discarded, and selecting a different finding resets the AI state to idle.
- **Rendering the answer:** `advice.advice` is split on newlines. Lines matching `/^(RISK|MIGRATION|PQC|ACTIONS|IMPACT|SUMMARY):$/i` become section headings with icons, blank lines become spacers, and everything else becomes paragraphs. This is a plain-text heuristic; no markdown library is used.

## Tests

- **Covered:** `backend/test_recommendation_state.py` tests `build_context()` against the real dataset:
  - no `recommended_candidate` for any NEEDS_REVIEW finding
  - labelled `ranking_model_output` for the RSA findings
  - `recommended_candidate` = the selected component for x25519 (DIRECT_PQC) and DSA (HYBRID)
  - neither field for SHA256 (KEEP)
  - per-`bom_ref` isolation of the two RSA-2048 findings
- **Not covered:** `generate_advice()` (the Ollama call) and `AIAdvisorPanel.jsx`. The frontend suite covers the assistant panel (`src/components/chat/chat.test.jsx`), not the advisor panel; the advisor's UI behavior has been verified with scripted browser sessions.

## Limitations (still open)

- The Ollama URL and model name are hardcoded, with no configuration option.
- There is no streaming, progress indication or cancellation. The full generation time is incurred before any result appears, and the backend allows up to 300 s.
- Truncation isn't flagged: only the first 5 migration actions are sent, and for NEEDS_REVIEW only the top ranking-model candidate appears in `ranking_model_output`. The model and the user aren't told.
- `num_predict: 300` can cut an answer off mid-section.
- `/api/ai/advice` collapses every failure into one HTTP 500 with a raw exception string.
- An unmatched `bom_ref` still triggers a model call with minimal context instead of returning 404.
- There is no caching; every click, including **Regenerate**, runs a full generation.
- The request field is still named `asset` (and the `api.js` parameter `assetName`) even though its value is a `bom_ref`.
- The model's wording is not guaranteed to follow the instructions exactly (see the prompt section).

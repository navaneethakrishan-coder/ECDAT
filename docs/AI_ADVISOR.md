# ECDAT — AI Migration Advisor (current implementation)

Traced from `backend/services/ai_advisor.py`, `backend/main.py`, `frontend/src/api.js`, and `frontend/src/App.jsx`.

> **Updated 2026-09-14 (backend round)** — see `CHANGELOG.md`. Two things changed: (1) the endpoint now lives in the canonical `backend/main.py` (the old `backend/api/main.py` two-backend split is resolved, see `ARCHITECTURE.md` §6), and (2) `build_context()` was rewritten to read the same authoritative dataset the dashboard uses, fixing a risk-score mismatch.
>
> **Updated 2026-09-14 (frontend round)** — the *backend contract described in this file did not change at all* in this round (same endpoint, same request/response shape, same prompt, same Ollama config). What changed is entirely on the frontend: the AI Advisor moved from a standalone bottom-of-page section into the asset-detail view, gained an explicit idle/loading/success/error+retry state machine, a duplicate-request guard, and a fix for a race condition where switching assets mid-request could show a stale result. See the "Frontend integration" section below and `CHANGELOG.md` for the verified test log.
>
> **Updated 2026-09-14 (risk-scoring unification round)** — `services/ai_advisor.py` itself was **not touched** in this round (it already read only `ecdat-migration-report.json`, per the backend round's fix above). What changed is that the *rest of the system* was unified to match: `explain_cbom.py` is now the only place risk is ever calculated, and `/api/risk` (previously an independent, if numerically-coincidental, calculation) now mechanically re-projects the same authoritative figure. This closes the last remaining gap in the guarantee that "the AI advisor can never disagree with the dashboard" — it was already true for the AI advisor specifically; now it's true for every risk-reporting surface in ECDAT, including the one the AI advisor doesn't use. See `docs/ARCHITECTURE.md` §5/§10.

## Endpoint

- **Path:** `POST /api/ai/advice`
- **Defined in:** `backend/main.py` (the single canonical FastAPI app). Also reachable via `backend/api/main.py`, which now just re-exports the same `app` object. The older `POST /api/ai/advisor` (body `{asset_name}`) still exists in `backend/main.py` too, unused by the frontend, kept only for backward compatibility.
- **CORS:** wide open (`allow_origins=["*"]`).

### Request format

```json
{ "asset": "<asset name, exact string match, case-sensitive at the model level>" }
```

Pydantic model: `AIAdviceRequest { asset: str }`.

### Response format

```json
{
  "asset": "<echoed asset name>",
  "model": "qwen3:14b",
  "advice": "<raw text returned by Ollama, .strip()'d, otherwise unprocessed>"
}
```

On any exception (including `requests.HTTPError`, `requests.Timeout`, Ollama not running, or the asset not existing in the underlying files) the route currently catches everything with a bare `except Exception` and returns **HTTP 500** with `detail: "AI advisor failed: <str(exc)>"` — there is no 404 for "asset not found" and no distinction between "Ollama unreachable" vs "asset has no data" vs any other failure.

## Ollama integration

- **URL:** `http://localhost:11434/api/generate` — hardcoded constant `OLLAMA_URL` in `services/ai_advisor.py`, not configurable via environment variable or settings file.
- **Model:** `qwen3:14b` — hardcoded constant `MODEL`.
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
- **Timeout:** 300 seconds (`requests.post(..., timeout=300)`).
- Uses Ollama's native `/api/generate` endpoint (not the OpenAI-compatible `/v1/chat/completions` path), non-streaming (`stream: false`) — the entire response is generated server-side before FastAPI gets anything back, so the frontend sees nothing until the full ~300-token completion finishes (or up to 5 minutes elapse).

## Context assembled before prompting (`build_context`)

**Fixed 2026-09-14.** The advisor now reads exactly **one** file: `data/ecdat-migration-report.json` — the same unified, authoritative dataset that `/api/asset/{name}`, `/api/migration-report/assets`, and the dashboard itself are built from (see `generate_migration_report.py`). It looks up the asset record (`find_report_asset`) and extracts:

1. `record.current_risk` + `record.classification` → `context.risk = { score, severity, quantum_status, category }`
2. `record.migration_impact` → `context.priority = { priority_score, priority }`, `context.blast_radius = { score, severity }`, `context.complexity = { score, level }`
3. `record.pqc_migration` + `record.recommendation` → `context.pqc = { migration_type, pqc_applicable, confidence }`, plus `context.pqc.recommended_candidate` (candidate/score/rank/confidence/reason from `recommendation`, plus `family`/`compatibility`/`tradeoffs` from the first entry of `record.ranked_candidates`) — only populated when `recommendation.candidate` is set
4. `record.source_impact` → `context.source_impact = { impact_level, affected_file_count, affected_class_count, affected_function_count }` — **new**: this was previously omitted entirely, even though the dashboard's AI advisor panel copy ("Reviewing ECDAT risk, migration, PQC and source-impact results...") already claimed it was used
5. `record.migration_actions` → `context.actions` = first 5 items (still truncated to 5; this specific limitation was not changed)

**Asset lookup is now case-insensitive** (`find_report_asset` lowercases both sides before comparing), matching every other asset-lookup endpoint in `backend/main.py` — verified: `build_context("DSA")` and `build_context("dsa")` resolve to the identical underlying record. If the asset is not found in the report at all, the context degrades to `{"asset": "<name>"}` exactly as before (no exception raised) — verified live: asking for a nonexistent asset returns HTTP 200 with the model correctly stating the asset is not recognized, rather than inventing data.

Because this is now the *same* file `/api/asset/{name}` reads, **the risk figure the AI advisor reports can no longer diverge from the dashboard's "current risk" for the same asset.** Verified live end-to-end against Ollama: for `DSA`, the dashboard's `current_risk` is `{score: 65.75, severity: "HIGH"}`, and the model's RISK section states "a high risk score of 65.75 and a high severity rating" — the same number, sourced from the same field.

## Prompt template

```
You are the ECDAT AI Migration Advisor.

Use ONLY the supplied ECDAT results as factual
information.

Do not invent scores, assets, dependencies,
PQC algorithms, or migration decisions.

Asset:
<asset_name>

ECDAT results:
<compact single-line JSON dump of the context object>

Give a concise developer-oriented answer.

Use exactly these sections:

RISK:
Explain the current risk.

MIGRATION:
Explain the ECDAT migration decision.

PQC:
Explain the recommended PQC candidate, if available.

ACTIONS:
Give the most important developer actions.

IMPACT:
Explain the expected source-code or architectural impact.

SUMMARY:
Give one short recommendation.
```

The prompt is a single static Python f-string built fresh per request; there is no system prompt separate from the user prompt, no conversation history, and no retry/self-check step. `num_predict: 300` caps the reply to roughly 300 tokens, which can truncate the SUMMARY (or even IMPACT/ACTIONS) section mid-sentence for verbose model output — the frontend does not detect or flag truncation.

## Frontend integration

- `frontend/src/api.js` → `getAIAdvice(assetName)`: `fetch(POST /api/ai/advice, {asset: assetName})`; throws `Error(detail)` on non-2xx response (reading `detail` from the JSON body if present, else a generic `"AI advice request failed: <status>"`). **Unchanged** in the 2026-09-14 frontend round.
- **Location (changed 2026-09-14):** the AI Advisor now renders via `frontend/src/components/AIAdvisorPanel.jsx`, mounted inside the asset-detail overlay in `App.jsx` immediately after the risk/priority/complexity/blast-radius summary cards — not as a separate section at the bottom of the page. It receives `assetDetail` (already fetched for the rest of the detail view — no extra network call) and renders a data snapshot above the AI content: **asset name, algorithm/primitive, risk, priority, complexity, blast radius, PQC recommendation, and source impact** — all eight fields the task required, sourced from the same `assetDetail` object the rest of the panel uses.
- **State machine (changed 2026-09-14):** `App.jsx` holds a single `aiStatus` value (`"idle" | "loading" | "success" | "error"`) instead of the previous independent `aiLoading`/`aiError`/`aiAdvice` trio.
  - **Idle:** button reads exactly **"Get AI Recommendation"**.
  - **Loading:** button reads "Generating..." and is `disabled`; a loading block shows **"Qwen3:14b is analyzing this cryptographic asset..."** plus a one-line description naming the asset. Verified live: the button's `disabled` attribute is `true` throughout the real ~33–49s Ollama call in this environment, and the rest of the dashboard (sidebar navigation, etc.) remains fully clickable during that time — the AI call does not block anything else.
  - **Success:** the model's answer is rendered (same section-heading heuristic as before — see below), plus a small **Regenerate** button.
  - **Error:** an error block with the failure message and an explicit **Retry** button (not just "click Generate again" — a dedicated, visually distinct retry action), per the requested UX.
  - **Duplicate-request guard:** `handleGenerateAIAdvice` returns immediately if `aiStatus === "loading"`, in addition to the button's `disabled` attribute — verified live that a second click while loading has no effect.
  - **Stale-result fix (new):** a `selectedAssetRef` captures which asset a request was made for; if the user switches assets before the response arrives, the result is discarded instead of being shown under the new asset's heading. Selecting a different asset also immediately resets `aiStatus` to `"idle"` so a previous asset's success/error block is never left showing. Verified live: after asset A's AI answer was displayed, switching to asset B showed a fresh idle state, not asset A's leftover result.
  - **Rendering the answer:** unchanged — `advice.advice` is split on `"\n"`; a line matching `/^(RISK|MIGRATION|PQC|ACTIONS|IMPACT|SUMMARY):$/i` becomes an `<h4>`; blank lines become spacers; everything else becomes a `<p>`. Still a plain-text heuristic with the same degradation mode described previously (no markdown library was added — out of scope, "no unnecessary dependencies").
  - The model badge ("Qwen3:14B · Ollama") and header copy are still hardcoded strings; the result panel's "Powered by {advice.model}" line still uses the API's actual echoed `model` value.

## Limitations (still open)

- Ollama URL and model name are hardcoded — no environment variable, config file, or UI setting to point at a different model/host.
- No streaming — full latency of the LLM call (measured ~33–49s across several real requests in this environment, but the backend allows up to 300s) is incurred before any UI update. The loading state now explicitly warns "This can take up to a few minutes," but there is still no progress percentage and no way to cancel an in-flight request early (the request will still complete server-side even if the user navigates away).
- Truncates migration actions to 5 and PQC candidates to 1 without telling the model or the user that truncation happened.
- No token/length safety margin against `num_predict: 300` — long answers can be cut off mid-section.
- Generic exception handling collapses all failure modes (Ollama down, network error, malformed JSON) into a single HTTP 500 with a raw exception string. (An asset simply not existing in the report is *not* an error case — see above — but a missing/corrupt `ecdat-migration-report.json` file, or Ollama being unreachable, still surfaces as a raw 500; the frontend's new error block will display whatever that raw string is, with a Retry button, but the message itself is still not curated for end users.)
- No caching — every click re-triggers a full LLM generation, even for the same asset with unchanged data (the new **Regenerate** button makes this more discoverable, not less frequent).
- No automated tests exist for `services/ai_advisor.py` or for `AIAdvisorPanel.jsx` (both were exercised manually — see `CHANGELOG.md` for the test logs from both rounds — but there is still no regression test that would catch either class of bug automatically in the future).

## Fixed 2026-09-14 (no longer limitations)

**Backend round:**
- ~~No fuzzy/case-insensitive asset lookup in `build_context`~~ — now case-insensitive, matching the rest of the API.
- ~~Reads a different risk source file than the dashboard/report~~ — now reads `ecdat-migration-report.json`, the same file the dashboard uses.
- ~~Endpoint only existed in the divergent `backend/api/main.py`~~ — now defined in the canonical `backend/main.py`.

**Frontend round:**
- ~~AI Advisor was a disconnected section at the bottom of the page~~ — now embedded in the asset-detail view with a full data snapshot.
- ~~No duplicate-request guard beyond the button's `disabled` attribute~~ — `handleGenerateAIAdvice` also short-circuits in code.
- ~~Switching assets mid-request could show a stale/mismatched AI result~~ — fixed via a synchronous `selectedAssetRef` check and an asset-change reset effect; verified live.
- ~~Error state had no explicit retry affordance~~ — now has a dedicated **Retry** button.
- ~~Idle button label and loading copy didn't match a specified UX~~ — now read exactly "Get AI Recommendation" and "Qwen3:14b is analyzing this cryptographic asset..." respectively.

import { Activity, Gauge, ListChecks, RefreshCw, Shield, Sparkles, Target } from "lucide-react";

import { SeverityBadge } from "./Badge";

const SECTION_ICONS = {
  RISK: Gauge,
  MIGRATION: Target,
  PQC: Shield,
  ACTIONS: ListChecks,
  IMPACT: Activity,
  SUMMARY: Sparkles,
};

/**
 * AI Migration Advisor — embedded in the asset detail experience as a
 * compact intelligence panel (workspace grid, bottom-right), not a
 * mega-card. Every fact it needs (risk / priority / PQC candidate) is
 * already visible in the Risk & Impact / Migration Path panels beside
 * it, so this panel only restates that context in a single line
 * before offering the AI-generated explanation via
 * POST /api/ai/advice. States: idle -> loading -> success | error.
 */
export function AIAdvisorPanel({
  assetName,
  assetDetail,
  status,
  advice,
  error,
  onGenerate,
}) {
  const isLoading = status === "loading";

  const primitive =
    assetDetail?.inventory?.primitive ||
    assetDetail?.classification?.category ||
    "Unknown";

  const riskSeverity =
    assetDetail?.current_risk?.severity ||
    assetDetail?.risk_assessment?.final_score?.severity ||
    "UNKNOWN";

  const priorityLevel =
    assetDetail?.priority?.level ||
    assetDetail?.migration_impact?.priority?.level ||
    "UNKNOWN";

  const pqcCandidate =
    assetDetail?.recommendation?.candidate || "No direct replacement";

  return (
    <section className="workspace-panel panel-ai" aria-labelledby="ai-advisor-heading">
      <div className="ai-advisor-header">
        <div className="ai-advisor-heading-group">
          <div className="ai-advisor-icon">
            <Sparkles size={16} />
          </div>

          <h3 id="ai-advisor-heading">AI Migration Advisor</h3>
        </div>

        <span className="ai-model-badge">Qwen3:14B · Ollama</span>
      </div>

      {/* One-line context strip: ties this panel back to the risk/
          migration data shown in the panels beside it, without
          repeating the full snapshot grid that used to live here. */}
      <p className="ai-context-line">
        Analyzing <strong>{assetName}</strong> ({primitive}) — <SeverityBadge value={riskSeverity} /> risk,{" "}
        <SeverityBadge value={priorityLevel} /> priority, PQC → <em>{pqcCandidate}</em>
      </p>

      {/* ---- Idle / call to action ---- */}
      {status !== "success" && (
        <button
          type="button"
          className="btn btn-primary ai-advice-button"
          onClick={onGenerate}
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? "Generating..." : "Get AI Recommendation"}
        </button>
      )}

      {/* ---- Loading ---- */}
      {isLoading && (
        <div className="ai-loading" role="status" aria-live="polite">
          <div className="loading-spinner" />
          <div>
            <strong>Qwen3:14b is analyzing this cryptographic asset...</strong>
            <p>Reviewing ECDAT risk, migration, PQC and source-impact results for {assetName}. This can take up to a few minutes.</p>
          </div>
        </div>
      )}

      {/* ---- Error ---- */}
      {status === "error" && (
        <div className="ai-error" role="alert">
          <strong>AI recommendation failed</strong>
          <p>{error || "The AI advisor could not be reached. Confirm Ollama is running and try again."}</p>
          <button type="button" className="btn btn-outline btn-sm" onClick={onGenerate}>
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* ---- Success ---- */}
      {status === "success" && advice?.advice && (
        <div className="ai-advice-result">
          <div className="ai-result-header">
            <span>AI Recommendation</span>
            <span className="ai-model-label">Powered by {advice.model}</span>
          </div>

          <div className="ai-advice-content">
            {advice.advice.split("\n").map((line, index) => {
              const trimmed = line.trim();

              if (!trimmed) {
                return <div key={index} className="ai-space" />;
              }

              const sectionMatch = trimmed.match(/^(RISK|MIGRATION|PQC|ACTIONS|IMPACT|SUMMARY):$/i);

              if (sectionMatch) {
                const sectionKey = sectionMatch[1].toUpperCase();
                const SectionIcon = SECTION_ICONS[sectionKey];

                return (
                  <h4 key={index} className="ai-section-heading">
                    {SectionIcon && <SectionIcon size={13} />}
                    {trimmed}
                  </h4>
                );
              }

              return <p key={index}>{trimmed}</p>;
            })}
          </div>

          <button type="button" className="btn btn-outline btn-sm ai-regenerate" onClick={onGenerate}>
            <RefreshCw size={14} />
            Regenerate
          </button>
        </div>
      )}
    </section>
  );
}

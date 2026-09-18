import { FlaskConical, GitCompareArrows, Gauge, Network, ScanSearch, Sparkles } from "lucide-react";

import { migrationDecisionDisplay } from "../migrationStrategy";

// The investigation workspace's analysis surfaces, in hub order.
export const INVESTIGATION_SURFACES = [
  { key: "evidence", label: "Evidence", icon: ScanSearch },
  { key: "risk", label: "Risk", icon: Gauge },
  { key: "blast", label: "Blast Radius", icon: Network },
  { key: "migration", label: "Migration", icon: GitCompareArrows },
  { key: "whatif", label: "What-If", icon: FlaskConical },
  { key: "ai", label: "AI Analysis", icon: Sparkles },
];

const SEVERITIES = new Set(["low", "medium", "high", "critical"]);

export function severityTone(value) {
  const normalized = String(value || "").toLowerCase();
  return SEVERITIES.has(normalized) ? normalized : "unknown";
}

function formatScore(value) {
  return typeof value === "number" ? (Number.isInteger(value) ? String(value) : value.toFixed(2)) : null;
}

const AI_STATUS = {
  idle: "Ready to run",
  loading: "Analyzing…",
  success: "Analysis available",
  error: "Unavailable",
};

/** One-line, real summary per branch -- read from the loaded record. */
export function branchSummaries(assetDetail, aiStatus) {
  const risk = assetDetail?.current_risk;
  const strategy = assetDetail?.migration_strategy;
  const decision = migrationDecisionDisplay(strategy?.strategy, strategy?.pqc_component);
  const blast = assetDetail?.blast_radius;
  const impact = assetDetail?.source_impact;
  const dependents = blast?.direct_dependents?.count;

  return {
    evidence: {
      value: typeof impact?.affected_file_count === "number" ? `${impact.affected_file_count} source file(s)` : "Source evidence",
      tone: "neutral",
    },
    risk: {
      value: risk ? [formatScore(risk.score), risk.severity].filter(Boolean).join(" · ") : "Not recorded",
      tone: severityTone(risk?.severity),
    },
    blast: {
      value: blast
        ? `${blast.severity || "—"}${typeof dependents === "number" ? ` · ${dependents} dependent(s)` : ""}`
        : "Not recorded",
      tone: severityTone(blast?.severity),
    },
    migration: {
      value: decision ? decision.text : "No strategy recorded",
      tone: decision?.state === "selected" ? "pqc" : decision?.state === "unresolved" ? "review" : "neutral",
    },
    whatif: { value: "Scenario engine", tone: "simulation" },
    ai: { value: AI_STATUS[aiStatus] || AI_STATUS.idle, tone: aiStatus === "error" ? "review" : "ai" },
  };
}


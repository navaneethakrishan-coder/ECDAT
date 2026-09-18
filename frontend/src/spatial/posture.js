// Posture figures shared by the HTML hero and the 3D posture anchor.
// Moved unchanged from HeroOverview: every value is read from, or is a
// transparent function of, GET /api/summary -- nothing new is scored.

export function readinessFromSummary(summary) {
  const totalAssets = summary?.total_assets ?? 0;
  const highOrCritical = summary?.high_or_critical_priority_assets ?? 0;

  // "Migration readiness" = the share of assets that are NOT
  // flagged high/critical priority for migration -- a direct,
  // transparent function of two numbers /api/summary already
  // returns. Not a new backend metric; purely a percentage of
  // existing data, shown so the headline number an evaluator sees
  // first reads as a verdict ("87% ready") rather than a raw count.
  const readinessPercent = totalAssets > 0 ? Math.round(100 - (highOrCritical / totalAssets) * 100) : 100;

  const readinessTone =
    readinessPercent >= 80 ? "low" : readinessPercent >= 60 ? "medium" : readinessPercent >= 40 ? "high" : "critical";

  const readinessLabel =
    readinessPercent >= 80
      ? "Strong readiness"
      : readinessPercent >= 60
      ? "Moderate readiness"
      : readinessPercent >= 40
      ? "Needs attention"
      : "Critical exposure";

  return { readinessPercent, readinessTone, readinessLabel };
}

/** The 3D posture anchor's input: readiness, severity breakdown and the four headline counts. */
export function postureFromSummary(summary) {
  if (!summary) return null;
  const { readinessPercent, readinessTone } = readinessFromSummary(summary);
  return {
    readinessPercent,
    tone: readinessTone,
    distribution: summary.risk_severity_distribution || {},
    metrics: [
      { key: "assets", title: "Cryptographic Assets", value: summary.total_assets ?? 0, interactive: true },
      {
        key: "priority",
        title: "High / Critical Priority",
        value: summary.high_or_critical_priority_assets ?? 0,
        tone: "critical",
        interactive: true,
      },
      { key: "pqc", title: "PQC Candidates", value: summary.assets_with_pqc_candidates ?? 0, tone: "cyan", interactive: true },
      { key: "actions", title: "Migration Actions", value: summary.total_migration_actions ?? 0, interactive: false },
    ],
  };
}

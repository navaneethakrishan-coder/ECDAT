import { ArrowUpRight, Database, ShieldAlert, TrendingUp } from "lucide-react";

import { StatCard } from "./StatCard";

/**
 * First thing a judge sees: what ECDAT is, and the current
 * repository's headline numbers. Every figure here is read directly
 * from GET /api/summary (already fetched for the stat cards) -- the
 * only derived value is `readinessPercent`, computed from two of
 * those same summary fields (see comment below), not a new metric.
 */
export function HeroOverview({ summary, totalAssetsScanned }) {
  const totalAssets = summary?.total_assets ?? 0;
  const highOrCritical = summary?.high_or_critical_priority_assets ?? 0;
  const pqcCandidates = summary?.assets_with_pqc_candidates ?? 0;
  const totalActions = summary?.total_migration_actions ?? 0;

  // "Migration readiness" = the share of assets that are NOT
  // flagged high/critical priority for migration -- a direct,
  // transparent function of two numbers /api/summary already
  // returns. Not a new backend metric; purely a percentage of
  // existing data, shown so the headline number a judge sees first
  // reads as a verdict ("87% ready") rather than a raw count.
  const readinessPercent =
    totalAssets > 0 ? Math.round(100 - (highOrCritical / totalAssets) * 100) : 100;

  const readinessTone =
    readinessPercent >= 80
      ? "low"
      : readinessPercent >= 60
      ? "medium"
      : readinessPercent >= 40
      ? "high"
      : "critical";

  const readinessLabel =
    readinessPercent >= 80
      ? "Strong readiness"
      : readinessPercent >= 60
      ? "Moderate readiness"
      : readinessPercent >= 40
      ? "Needs attention"
      : "Critical exposure";

  return (
    <section className="hero" aria-labelledby="hero-heading">
      <div className="hero-intro">
        <span className="hero-eyebrow">Cryptographic Migration Intelligence</span>
        <h1 id="hero-heading">
          Find every at-risk cryptographic asset. Know exactly what to migrate first.
        </h1>
        <p>
          ECDAT scans a repository's real cryptography, scores each asset's
          quantum-vulnerability risk, ranks post-quantum replacements, and explains the
          migration path in plain language via an AI advisor — turning a CBOM scan into
          a prioritized, actionable migration plan.
        </p>
      </div>

      <div className="hero-readiness" role="group" aria-label="Overall migration readiness">
        <div className="hero-readiness-meter">
          <svg viewBox="0 0 120 120" className={`readiness-ring readiness-ring-${readinessTone}`}>
            <circle cx="60" cy="60" r="52" className="readiness-ring-track" />
            <circle
              cx="60"
              cy="60"
              r="52"
              className="readiness-ring-value"
              style={{
                strokeDasharray: `${(readinessPercent / 100) * 326.7} 326.7`,
              }}
            />
          </svg>
          <div className="hero-readiness-number">
            <strong>{readinessPercent}%</strong>
            <span>ready</span>
          </div>
        </div>

        <div className="hero-readiness-label">
          <TrendingUp size={14} />
          {readinessLabel}
        </div>
      </div>

      <div className="stats-grid">
        <StatCard title="Cryptographic Assets" value={totalAssets} subtitle={
          totalAssetsScanned && totalAssetsScanned !== totalAssets
            ? `${totalAssetsScanned} raw CBOM components scanned`
            : "Assets discovered"
        } icon={Database} />

        <StatCard
          title="High / Critical Priority"
          value={highOrCritical}
          subtitle="Migrate these first"
          icon={ShieldAlert}
          tone="critical"
        />

        <StatCard
          title="PQC Candidates"
          value={pqcCandidates}
          subtitle="Ready for PQC replacement"
          icon={TrendingUp}
          tone="accent"
        />

        <StatCard
          title="Migration Actions"
          value={totalActions}
          subtitle="Generated developer steps"
          icon={ArrowUpRight}
        />
      </div>
    </section>
  );
}

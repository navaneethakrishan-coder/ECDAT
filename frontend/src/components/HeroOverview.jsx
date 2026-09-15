import {
  ArrowUpRight,
  Binary,
  Database,
  GitBranch,
  Radar,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";

import { StatCard } from "./StatCard";

// A purely explanatory chain (static, not a live status tracker --
// that's PipelineStepper's job further down, driven by real
// /api/analyze/status). This exists only so a first-time viewer
// understands ECDAT's end-to-end shape in one glance, before they've
// scrolled anywhere.
const WORKFLOW_CHAIN = [
  { key: "repo", label: "Repository", icon: GitBranch },
  { key: "discovery", label: "Cryptographic Discovery", icon: Binary },
  { key: "risk", label: "Risk Assessment", icon: ShieldAlert },
  { key: "pqc", label: "PQC Mapping", icon: Zap },
  { key: "migration", label: "Migration Planning", icon: TrendingUp },
  { key: "ai", label: "AI Guidance", icon: Sparkles },
];

function focusRepositoryForm() {
  document.querySelector(".repository-analysis-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  // Give the smooth-scroll a moment before stealing focus, so the
  // input doesn't jump the viewport a second time mid-scroll.
  window.setTimeout(() => document.getElementById("repo-url-input")?.focus(), 350);
}

/**
 * First thing an evaluator sees: what ECDAT is, and the current
 * repository's headline numbers. Every figure here is read directly
 * from GET /api/summary (already fetched for the stat cards) -- the
 * only derived value is `readinessPercent`, computed from two of
 * those same summary fields (see comment below), not a new metric.
 *
 * Deliberately asymmetric: one large "Quantum Readiness" panel
 * (risk is ECDAT's core signal, so it gets the most visual weight)
 * beside a tighter 2x2 grid of supporting counts, rather than five
 * equal-sized cards in a row.
 */
export function HeroOverview({ summary, totalAssetsScanned }) {
  const totalAssets = summary?.total_assets ?? 0;
  const highOrCritical = summary?.high_or_critical_priority_assets ?? 0;
  const pqcCandidates = summary?.assets_with_pqc_candidates ?? 0;
  const totalActions = summary?.total_migration_actions ?? 0;
  // Risk-severity count (same source as the risk donut) -- distinct from the priority count above.
  const highRiskCount =
    (summary?.risk_severity_distribution?.HIGH ?? 0) + (summary?.risk_severity_distribution?.CRITICAL ?? 0);

  // "Migration readiness" = the share of assets that are NOT
  // flagged high/critical priority for migration -- a direct,
  // transparent function of two numbers /api/summary already
  // returns. Not a new backend metric; purely a percentage of
  // existing data, shown so the headline number an evaluator sees
  // first reads as a verdict ("87% ready") rather than a raw count.
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
      <div className="hero-top">
        <div className="hero-intro">
          <span className="hero-eyebrow">Post-Quantum Cryptography Migration Intelligence</span>
          <h1 id="hero-heading">
            From Code to a <span className="hero-gradient-text">Quantum-Ready Future.</span>
          </h1>
          <p>
            ECDAT scans a repository to discover every cryptographic asset in use, assesses
            each one&rsquo;s quantum-vulnerability risk, maps a post-quantum replacement path,
            prioritizes what to migrate first, and explains the reasoning in plain language
            through an AI migration advisor — turning a raw CBOM scan into a decision-ready
            migration plan.
          </p>

          <ol className="hero-workflow-chain" aria-label="ECDAT's end-to-end workflow">
            {WORKFLOW_CHAIN.map((stage, index) => (
              <li key={stage.key}>
                <stage.icon size={12} aria-hidden="true" />
                <span>{stage.label}</span>
                {index < WORKFLOW_CHAIN.length - 1 && (
                  <span className="hero-workflow-arrow" aria-hidden="true">→</span>
                )}
              </li>
            ))}
          </ol>

          <div className="hero-cta-row">
            <button type="button" className="btn btn-primary btn-lg hero-cta" onClick={focusRepositoryForm}>
              <Radar size={16} />
              Analyze a Repository
            </button>
            <span className="hero-cta-hint">Point it at any public GitHub repository — results in seconds.</span>
          </div>
        </div>

        {/* Lightweight, dependency-free visual: an inline SVG built
            from plain shapes/lines (no image asset, no chart library)
            suggesting a scanned codebase collapsing into a hardened,
            quantum-safe key -- purely decorative, aria-hidden. */}
        <svg
          className="hero-visual"
          viewBox="0 0 320 320"
          fill="none"
          aria-hidden="true"
          role="presentation"
        >
          <defs>
            <radialGradient id="hero-core-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(34, 211, 238, 0.3)" />
              <stop offset="55%" stopColor="rgba(139, 92, 246, 0.1)" />
              <stop offset="100%" stopColor="rgba(139, 92, 246, 0)" />
            </radialGradient>
          </defs>

          <circle cx="160" cy="160" r="100" fill="url(#hero-core-glow)" />
          <circle cx="160" cy="160" r="140" className="hero-visual-ring hero-visual-ring-outer" />

          {/* Two counter-rotating orbits carrying small "key" nodes -- the
              only motion in the hero, slow enough to read as ambient. */}
          <g className="hero-visual-orbit">
            <circle cx="160" cy="160" r="104" className="hero-visual-ring hero-visual-ring-mid" />
            <circle cx="264" cy="160" r="4" className="hero-visual-node hero-visual-node-violet" />
            <circle cx="56" cy="160" r="3" className="hero-visual-node hero-visual-node-cyan" />
          </g>
          <g className="hero-visual-orbit hero-visual-orbit-reverse">
            <circle cx="160" cy="160" r="68" className="hero-visual-ring hero-visual-ring-inner" />
            <circle cx="160" cy="92" r="3" className="hero-visual-node hero-visual-node-magenta" />
          </g>
          <circle cx="160" cy="20" r="3" className="hero-visual-node hero-visual-node-cyan" />
          <circle cx="281" cy="230" r="2.5" className="hero-visual-node hero-visual-node-violet" />

          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i / 12) * Math.PI * 2;
            const x1 = 160 + Math.cos(angle) * 140;
            const y1 = 160 + Math.sin(angle) * 140;
            const x2 = 160 + Math.cos(angle) * 152;
            const y2 = 160 + Math.sin(angle) * 152;
            return (
              <line
                key={i}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                className={i % 3 === 0 ? "hero-visual-tick hero-visual-tick-strong" : "hero-visual-tick"}
              />
            );
          })}

          {/* A simple hardened-lock glyph at the center, standing in
              for "quantum-safe cryptography" without needing an icon
              font or external asset. */}
          <rect x="132" y="150" width="56" height="46" rx="8" className="hero-visual-lock-body" />
          <path d="M144 150 V132 a16 16 0 0 1 32 0 V150" className="hero-visual-lock-shackle" />
          <circle cx="160" cy="172" r="6" className="hero-visual-lock-dot" />
        </svg>
      </div>

      <div className="hero-metrics-grid">
        <div className={`hero-readiness-card readiness-tone-${readinessTone}`} role="group" aria-label="Overall quantum readiness">
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

          <div className="hero-readiness-copy">
            <span className="hero-readiness-eyebrow">Quantum Readiness</span>
            <div className="hero-readiness-label">
              <TrendingUp size={14} />
              {readinessLabel}
            </div>
            <p>
              {highOrCritical === 0
                ? "No assets currently require immediate attention."
                : `${highOrCritical} high-priority asset${highOrCritical === 1 ? "" : "s"} require${
                    highOrCritical === 1 ? "s" : ""
                  } immediate attention.`}
            </p>
          </div>
        </div>

        <div className="hero-stat-tiles">
          <StatCard
            title="Cryptographic Assets"
            value={totalAssets}
            subtitle={
              totalAssetsScanned && totalAssetsScanned !== totalAssets
                ? `${totalAssetsScanned} raw CBOM components scanned`
                : "Assets discovered"
            }
            icon={Database}
          />

          <StatCard
            title="High / Critical Priority"
            value={highOrCritical}
            subtitle={`${highRiskCount} at high/critical quantum risk`}
            icon={ShieldAlert}
            tone="critical"
          />

          <StatCard
            title="PQC Candidates"
            value={pqcCandidates}
            subtitle="Ready for PQC replacement"
            icon={TrendingUp}
            tone="cyan"
          />

          <StatCard
            title="Migration Actions"
            value={totalActions}
            subtitle="Generated developer steps"
            icon={ArrowUpRight}
          />
        </div>
      </div>
    </section>
  );
}

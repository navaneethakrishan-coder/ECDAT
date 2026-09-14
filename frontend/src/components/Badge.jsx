const KNOWN_TONES = new Set(["low", "medium", "high", "critical"]);

/**
 * Shared severity/status badge used for risk, priority, complexity,
 * blast radius and source-impact levels. Consolidates what used to be
 * two near-identical implementations (risk-badge + impact-badge).
 */
export function SeverityBadge({ value, fallback = "UNKNOWN" }) {
  const normalized = String(value || "").trim().toLowerCase();
  const tone = KNOWN_TONES.has(normalized) ? normalized : "unknown";

  return (
    <span className={`badge badge-${tone}`}>
      {value || fallback}
    </span>
  );
}

/** Small pill used for boolean/enum facts (e.g. "PQC Applicable"). */
export function TagBadge({ children, tone = "neutral" }) {
  return (
    <span className={`badge badge-tag badge-tag-${tone}`}>
      {children}
    </span>
  );
}

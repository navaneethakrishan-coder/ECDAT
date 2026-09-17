// Display wording for the backend's purpose-aware migration strategy
// (backend/services/migration_strategy.py). The backend makes the
// decision; nothing here re-derives a strategy or a candidate.

export const STRATEGY_LABELS = {
  KEEP: "No PQC migration",
  DIRECT_PQC: "Direct PQC",
  HYBRID: "Hybrid",
  NEEDS_REVIEW: "Needs review",
};

/**
 * A finding's PQC path as dictated by its strategy: the strategy's own
 * PQC component for DIRECT_PQC / HYBRID, and an explicit non-candidate
 * state for KEEP / NEEDS_REVIEW -- never the ranking model's top
 * candidate for a finding whose evidence leaves its role unresolved.
 * Returns null when no strategy is present, so callers keep their
 * existing fallback for datasets generated before strategies existed.
 */
export function strategyPqcPath(strategy, pqcComponent) {
  if (!strategy) {
    return null;
  }

  if (strategy === "DIRECT_PQC" || strategy === "HYBRID") {
    return {
      text: pqcComponent || "No suitable PQC candidate",
      label: STRATEGY_LABELS[strategy],
      none: !pqcComponent,
    };
  }

  return {
    text: STRATEGY_LABELS[strategy] || strategy,
    label: null,
    none: true,
  };
}

/**
 * The migration decision as a headline fact, derived from the strategy
 * only. A PQC recommendation exists solely for DIRECT_PQC / HYBRID with a
 * selected component; NEEDS_REVIEW is shown as unresolved and KEEP as no
 * PQC migration -- never the ranking model's top candidate. Returns null
 * when no strategy is present (legacy datasets).
 */
export function migrationDecisionDisplay(strategy, pqcComponent) {
  if (!strategy) {
    return null;
  }

  if ((strategy === "DIRECT_PQC" || strategy === "HYBRID") && pqcComponent) {
    return {
      label: `PQC Recommendation · ${STRATEGY_LABELS[strategy]}`,
      text: pqcComponent,
      state: "selected",
    };
  }

  if (strategy === "NEEDS_REVIEW") {
    return { label: "Migration Decision", text: "Needs review", state: "unresolved" };
  }

  if (strategy === "KEEP") {
    return { label: "Migration Decision", text: STRATEGY_LABELS.KEEP, state: "none" };
  }

  return { label: "Migration Decision", text: "No suitable PQC candidate", state: "none" };
}

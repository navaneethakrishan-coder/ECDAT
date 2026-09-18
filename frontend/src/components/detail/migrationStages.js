// Migration stages as dictated by the migration strategy (read-only):
//
//   DIRECT_PQC    Current → PQC target
//   HYBRID        Current → Hybrid path → Target state
//   KEEP          Current → Retain
//   NEEDS_REVIEW  Current → Review required
//
// NEEDS_REVIEW never has a target; a ranking-model candidate is only ever
// described as "Ranking-model candidate — not selected". Shared by the
// HTML MigrationTransition and the 3D migration path so both say the same.

export function migrationStages(strategy, topRanked) {
  if (!strategy?.strategy) return [];

  const current = {
    key: "current",
    tone: "current",
    label: "Current",
    // "private-key@<bom-ref>" names repeat the identity; show the kind.
    value: String(strategy.current_algorithm || "Current algorithm").split("@")[0],
    note: strategy.purpose_class_label || null,
  };

  let stages;
  switch (strategy.strategy) {
    case "DIRECT_PQC":
      stages = [
        current,
        {
          key: "target",
          tone: "pqc",
          label: "PQC target",
          value: strategy.pqc_component || "No suitable PQC component",
          note: strategy.pqc_component ? "Selected by the migration strategy" : null,
        },
      ];
      break;
    case "HYBRID":
      stages = [
        current,
        {
          key: "hybrid",
          tone: "hybrid",
          label: "Hybrid path",
          value: strategy.pqc_component || "No suitable PQC component",
          note: strategy.classical_component ? `Run alongside ${strategy.classical_component}` : null,
        },
        {
          key: "target",
          tone: "pqc",
          label: "Target state",
          value:
            strategy.classical_component && strategy.pqc_component
              ? `${strategy.classical_component} + ${strategy.pqc_component}`
              : strategy.pqc_component || "Not recorded",
          note: "Hybrid construction",
        },
      ];
      break;
    case "KEEP":
      stages = [current, { key: "retain", tone: "retain", label: "Retain", value: "No PQC migration", note: null }];
      break;
    case "NEEDS_REVIEW":
      stages = [
        current,
        {
          key: "review",
          tone: "review",
          label: "Review required",
          value: "No PQC component selected",
          note: topRanked?.candidate ? `Ranking-model candidate — not selected: ${topRanked.candidate}` : null,
        },
      ];
      break;
    default:
      stages = [current];
  }

  return stages;
}

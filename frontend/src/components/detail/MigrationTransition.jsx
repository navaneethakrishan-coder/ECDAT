import { ArrowRight } from "lucide-react";

import { migrationStages } from "./migrationStages";

/**
 * The migration decision as a spatial transition from today's
 * cryptography to the state the migration strategy selected. Stages are
 * read from assetDetail.migration_strategy only:
 *
 *   DIRECT_PQC    Current → PQC target
 *   HYBRID        Current → Hybrid path → Target state
 *   KEEP          Current → Retain
 *   NEEDS_REVIEW  Current → Review required
 *
 * NEEDS_REVIEW never shows a target; a ranking-model candidate is shown
 * only as "Ranking-model candidate — not selected".
 */
export function MigrationTransition({ strategy, topRanked }) {
  const stages = migrationStages(strategy, topRanked);
  if (!stages.length) return null;

  return (
    <ol
      className={`migration-transition migration-transition-${String(strategy.strategy).toLowerCase()}`}
      aria-label={`Migration transition: ${stages.map((stage) => `${stage.label} ${stage.value}`).join(", then ")}`}
      data-strategy={strategy.strategy}
    >
      {stages.map((stage, index) => (
        <li key={stage.key} className={`transition-stage transition-${stage.tone}`} style={{ "--stage-index": index }}>
          {index > 0 && <ArrowRight className="transition-arrow" size={16} aria-hidden="true" />}
          <div className="transition-card">
            <span className="transition-label">{stage.label}</span>
            <strong>{stage.value}</strong>
            {stage.note && <span className="transition-note">{stage.note}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}

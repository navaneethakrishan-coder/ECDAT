import {
  Brain,
  CheckCircle2,
  CircleDashed,
  Database,
  GitBranch,
  Loader2,
  ScanLine,
  ShieldCheck,
  Workflow,
  XCircle,
} from "lucide-react";

// The backend now reports the scan's real stages (GET /api/scan/status →
// `stages`), so this renders exactly what the scan service did: each stage's
// own status and its own detail line. Nothing is inferred or animated ahead
// of the backend -- a stage only shows as running once it is running.
const STAGE_ICONS = {
  target: GitBranch,
  scanner: ScanLine,
  availability: ShieldCheck,
  scan: ScanLine,
  validation: Database,
  pipeline: Workflow,
  publish: Brain,
};

const STATE_ICONS = {
  done: CheckCircle2,
  failed: XCircle,
  running: Loader2,
  skipped: CircleDashed,
};

export function PipelineStepper({ status, stages = [], pipelineStages = [], currentStage = null }) {
  if (!stages.length) {
    return null;
  }

  const pipelineDone = pipelineStages.filter((stage) => stage.status === "done").length;
  const pipelineFailed = pipelineStages.find((stage) => stage.status === "failed");

  return (
    <div className={`pipeline-stepper pipeline-${status}`} role="list" aria-label="Repository scan stages">
      {stages.map((stage) => {
        const state = stage.status === "pending" ? "pending" : stage.status;
        const Icon = STATE_ICONS[state] || STAGE_ICONS[stage.key] || CircleDashed;
        const isPipeline = stage.key === "pipeline";
        const detail = isPipeline && pipelineStages.length
          ? pipelineFailed
            ? `Failed at ${pipelineFailed.label}`
            : `${pipelineDone} / ${pipelineStages.length} stages`
          : stage.detail;

        return (
          <div
            className={`pipeline-step pipeline-step-${state} pipeline-stage-${stage.key}`}
            key={stage.key}
            role="listitem"
            data-stage={stage.key}
            data-status={state}
            title={stage.detail || stage.label}
          >
            <div className="pipeline-step-icon">
              <Icon size={15} className={state === "running" ? "spin-icon" : undefined} />
            </div>
            <span className="pipeline-step-label">{stage.label}</span>
            {detail && <span className="pipeline-step-detail">{detail}</span>}
          </div>
        );
      })}

      {currentStage && (
        <p className="pipeline-current" aria-live="polite">
          {currentStage}
        </p>
      )}
    </div>
  );
}

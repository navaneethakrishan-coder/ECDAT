import {
  Binary,
  Brain,
  CheckCircle2,
  Gauge,
  GitBranch,
  ListChecks,
  ScanLine,
  ShieldAlert,
  XCircle,
} from "lucide-react";

// The real backend runs 13 granular pipeline stages (see
// docs/ARCHITECTURE.md), but /api/analyze/status only ever reports
// one of idle/starting/running/completed/failed with a free-text
// message -- there is no per-stage telemetry to display honestly.
// This illustrates the conceptual pipeline shape rather than claiming
// to track real-time progress through it. While the analysis is
// running, every stage after "Repository" is shown as in-progress
// together -- never a specific one -- so nothing here overstates
// what the backend actually knows.
const STAGES = [
  { key: "repository", label: "Repository", icon: GitBranch },
  { key: "scan", label: "CBOMKit Scan", icon: ScanLine },
  { key: "discovery", label: "Crypto Discovery", icon: Binary },
  { key: "risk", label: "Risk Assessment", icon: ShieldAlert },
  { key: "pqc", label: "PQC Mapping", icon: Gauge },
  { key: "plan", label: "Migration Plan", icon: ListChecks },
  // "AI Ready", not "AI Guidance": the pipeline only prepares data for the on-demand advisor; it never runs the model.
  { key: "ai", label: "AI Ready", icon: Brain },
];

export function PipelineStepper({ status }) {
  // status: "idle" | "starting" | "running" | "completed" | "failed"
  return (
    <div className={`pipeline-stepper pipeline-${status}`} role="list" aria-label="Repository analysis pipeline">
      {STAGES.map((stage, index) => {
        const isFirst = index === 0;

        let state = "pending";

        if (status === "completed") {
          state = "done";
        } else if (status === "failed") {
          state = isFirst ? "done" : index === 1 ? "failed" : "pending";
        } else if (status === "starting") {
          state = isFirst ? "done" : index === 1 ? "active" : "pending";
        } else if (status === "running") {
          state = isFirst ? "done" : "active";
        }

        const Icon =
          state === "done" ? CheckCircle2 : state === "failed" ? XCircle : stage.icon;

        return (
          <div className={`pipeline-step pipeline-step-${state} pipeline-stage-${stage.key}`} key={stage.key} role="listitem">
            <div className="pipeline-step-icon">
              <Icon size={15} />
            </div>
            <span className="pipeline-step-label">{stage.label}</span>
          </div>
        );
      })}
    </div>
  );
}

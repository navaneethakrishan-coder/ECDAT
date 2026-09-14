import { AlertTriangle, CheckCircle2, Radar, RefreshCw } from "lucide-react";

import { PipelineStepper } from "./PipelineStepper";

/**
 * Repository analysis, as a first-class product feature rather than
 * a small form tucked under the page title. Same backend contract as
 * before (POST /api/analyze, GET /api/analyze/status, unchanged
 * payload/response shapes) -- only the presentation changed.
 */
export function RepositoryAnalysisPanel({
  repository,
  branch,
  status,
  message,
  error,
  running,
  onRepositoryChange,
  onBranchChange,
  onSubmit,
}) {
  return (
    <section className="repository-analysis-panel" aria-labelledby="repo-analysis-heading">
      <div className="repository-analysis-header">
        <div className="repository-analysis-icon">
          <Radar size={20} />
        </div>

        <div>
          <h2 id="repo-analysis-heading">Analyze a Repository</h2>
          <p>
            Point ECDAT at any public GitHub repository. CBOMKit scans the source for
            cryptographic usage, and the ECDAT pipeline turns that into risk-scored,
            PQC-mapped migration intelligence.
          </p>
        </div>
      </div>

      <PipelineStepper status={status} />

      <form
        className="repository-analysis-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="repository-input-group">
          <label htmlFor="repo-url-input">GitHub Repository URL</label>
          <input
            id="repo-url-input"
            type="text"
            value={repository}
            onChange={(event) => onRepositoryChange(event.target.value)}
            placeholder="https://github.com/owner/repository"
            disabled={running}
          />
        </div>

        <div className="repository-input-group branch-input">
          <label htmlFor="repo-branch-input">Branch</label>
          <input
            id="repo-branch-input"
            type="text"
            value={branch}
            onChange={(event) => onBranchChange(event.target.value)}
            placeholder="main"
            disabled={running}
          />
        </div>

        <button type="submit" className="btn btn-primary analyze-repository-button" disabled={running}>
          {running ? (
            <>
              <RefreshCw size={15} className="spin-icon" />
              Analyzing...
            </>
          ) : (
            "Analyze Repository"
          )}
        </button>
      </form>

      {status !== "idle" && (
        <div className={`analysis-status analysis-${status}`} role="status">
          {status === "completed" ? (
            <CheckCircle2 size={18} />
          ) : status === "failed" ? (
            <AlertTriangle size={18} />
          ) : (
            <span className="analysis-status-dot" />
          )}

          <div>
            <strong>
              {status === "completed"
                ? "Analysis complete"
                : status === "failed"
                ? "Analysis failed"
                : "Analysis in progress"}
            </strong>
            <p>{error || message || "Processing repository..."}</p>
          </div>
        </div>
      )}
    </section>
  );
}

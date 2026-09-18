import { AlertTriangle, ArrowUpRight, CheckCircle2, History, Info, Radar, RefreshCw } from "lucide-react";

import { PipelineStepper } from "./PipelineStepper";

function formatDuration(seconds) {
  if (typeof seconds !== "number") return null;
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds - minutes * 60)}s`;
}

function formatTime(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/**
 * Scan a GitHub repository: the entry point of the ECDAT workflow
 * (repository → CBOMKit → CBOM validation → ECDAT pipeline → security
 * space). Everything shown here is reported by the backend's scan service:
 * the real stages, the real validation result, the real counts, and the
 * real reason when a scan fails. Target kinds ECDAT cannot scan are named
 * as not implemented rather than left implied.
 */
export function RepositoryAnalysisPanel({
  repository,
  branch,
  status,
  message,
  error,
  errorCode,
  running,
  stages = [],
  pipelineStages = [],
  currentStage,
  validation,
  result,
  duration,
  capabilities,
  history = [],
  onRepositoryChange,
  onBranchChange,
  onSubmit,
  onViewResults,
}) {
  const repositoryScanner = capabilities?.supported_targets?.[0]?.scanners?.[0] || null;
  const planned = capabilities?.planned_targets || [];
  const warnings = validation?.warnings || [];
  const source = result?.source;

  return (
    <section className="repository-analysis-panel" aria-labelledby="repo-analysis-heading">
      <div className="repository-analysis-header">
        <div className="repository-analysis-icon">
          <Radar size={20} />
        </div>

        <div>
          <h2 id="repo-analysis-heading">Scan a Repository</h2>
          <p>
            Point ECDAT at a public GitHub repository. CBOMKit scans the source for cryptographic
            usage, ECDAT validates the CBOM, and the analysis pipeline turns it into the findings you
            explore in the security space.
          </p>
        </div>
      </div>

      {repositoryScanner && (
        <p className={`scan-capability scan-capability-${repositoryScanner.available ? "ready" : "unavailable"}`}>
          <Info size={13} aria-hidden="true" />
          <span>
            <strong>{repositoryScanner.title}</strong> — {repositoryScanner.detail}
            {planned.length > 0 && (
              <>
                {" "}
                Not implemented: {planned.map((entry) => entry.title.toLowerCase()).join(", ")}.
              </>
            )}
          </span>
        </p>
      )}

      <PipelineStepper
        status={status}
        stages={stages}
        pipelineStages={pipelineStages}
        currentStage={running ? currentStage : null}
      />

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
            name="repo-url"
            type="text"
            value={repository}
            onChange={(event) => onRepositoryChange(event.target.value)}
            placeholder="https://github.com/owner/repository"
            disabled={running}
            aria-invalid={status === "failed" && errorCode === "malformed-url" ? "true" : undefined}
          />
        </div>

        <div className="repository-input-group branch-input">
          <label htmlFor="repo-branch-input">Branch</label>
          <input
            id="repo-branch-input"
            name="repo-branch"
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
              Scanning...
            </>
          ) : (
            "Scan Repository"
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
                ? "Scan complete"
                : status === "failed"
                ? "Scan failed"
                : "Scan in progress"}
            </strong>
            <p>{error || message || "Scanning repository..."}</p>
            {status === "failed" && errorCode && <code className="analysis-error-code">{errorCode}</code>}
          </div>
        </div>
      )}

      {status === "completed" && result && (
        <div className="scan-result">
          <dl className="scan-result-facts">
            <div>
              <dt>Cryptographic findings</dt>
              <dd>{result.findings ?? result.crypto_components}</dd>
            </div>
            <div>
              <dt>CBOM components</dt>
              <dd>{result.components}</dd>
            </div>
            <div>
              <dt>Recorded dependencies</dt>
              <dd>{result.dependency_edges}</dd>
            </div>
            {formatDuration(duration) && (
              <div>
                <dt>Duration</dt>
                <dd>{formatDuration(duration)}</dd>
              </div>
            )}
          </dl>

          {source && (
            <p className="scan-result-source">
              {source.git_url} · {source.branch}
              {source.commit ? ` · ${String(source.commit).slice(0, 10)}` : ""}
            </p>
          )}

          {warnings.length > 0 && (
            <ul className="scan-warnings">
              {warnings.map((warning) => (
                <li key={warning.code}>{warning.message}</li>
              ))}
            </ul>
          )}

          {onViewResults && (
            <button type="button" className="btn btn-outline btn-sm scan-view-results" onClick={onViewResults}>
              <ArrowUpRight size={14} aria-hidden="true" />
              Open in Security Space
            </button>
          )}
        </div>
      )}

      {history.length > 0 && (
        <details className="scan-history">
          <summary>
            <History size={13} aria-hidden="true" />
            Recent scans ({history.length})
          </summary>
          <ul>
            {history.slice(0, 5).map((entry) => (
              <li key={entry.scan_id} data-status={entry.status}>
                <span className="scan-history-target">{entry.target?.slug || "unknown"}</span>
                <span className="scan-history-branch">{entry.target?.branch}</span>
                <span className="scan-history-status">
                  {entry.status === "completed"
                    ? `${entry.result?.findings ?? entry.result?.crypto_components ?? 0} findings`
                    : entry.error_code || entry.status}
                </span>
                <span className="scan-history-time">{formatTime(entry.finished_at || entry.started_at)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

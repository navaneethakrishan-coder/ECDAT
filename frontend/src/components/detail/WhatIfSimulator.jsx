import { useEffect, useState } from "react";
import { ArrowRight, FlaskConical, Lock } from "lucide-react";

import { getWhatIfFinding, simulateWhatIf } from "../../api";
import { useSpatial } from "../../spatial/SpatialContext";
import { SeverityBadge, TagBadge } from "../Badge";

function formatScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "—";
}

function formatDelta(value, suffix = "") {
  if (typeof value !== "number") {
    return "—";
  }

  if (value === 0) {
    return `±0${suffix}`;
  }

  const magnitude = Number.isInteger(value) ? Math.abs(value) : Math.abs(value).toFixed(2);
  return `${value < 0 ? "−" : "+"}${magnitude}${suffix}`;
}

// A lower risk/priority score is an improvement; higher readiness is.
function deltaTone(value, higherIsBetter = false) {
  if (typeof value !== "number" || value === 0) {
    return "neutral";
  }

  return value < 0 !== higherIsBetter ? "better" : "worse";
}

/**
 * Current vs simulated comparison for one what-if result. Every number
 * comes from POST /api/what-if/simulate, which runs the real risk and
 * priority engines on an in-memory copy of the finding.
 */
function WhatIfResult({ result }) {
  const finding = result.finding;
  const readiness = result.portfolio?.readiness_percent;
  const vulnerable = result.portfolio?.remaining_quantum_vulnerable;
  const priority = finding.priority;

  const rows = [
    {
      key: "risk",
      label: "Quantum risk",
      before: finding.risk.before,
      after: finding.risk.after,
      delta: finding.risk.delta,
      level: "severity",
    },
    {
      key: "priority",
      label: "Migration priority",
      before: priority.before,
      after: priority.after,
      delta: priority.delta,
      level: "level",
    },
  ];

  return (
    <div className="what-if-result" role="region" aria-label="What-if simulation result">
      <div className="what-if-result-banner">
        <TagBadge tone="simulation">Simulation result</TagBadge>
        <span>{result.notice}</span>
      </div>

      {/* Before / after as two separated states. Every value is the
          backend's own before/after figure from the same result. */}
      <div className="simulation-split" aria-label="Current state compared with simulated state">
        <div className="simulation-state simulation-state-real">
          <span className="simulation-state-label">
            <Lock size={12} aria-hidden="true" /> Current state · real
          </span>
          {readiness && (
            <div className="simulation-state-metric">
              <strong>{readiness.before}%</strong>
              <span>portfolio readiness</span>
            </div>
          )}
          <div className="simulation-state-metric">
            <strong>{formatScore(finding.risk.before.score)}</strong>
            <span>
              quantum risk <SeverityBadge value={finding.risk.before.severity} />
            </span>
          </div>
          <span className="simulation-state-algo">{finding.current_algorithm}</span>
        </div>

        <div className="simulation-bridge" aria-hidden="true">
          <ArrowRight size={18} />
          <span>simulate</span>
        </div>

        <div className="simulation-state simulation-state-simulated">
          <span className="simulation-state-label">
            <FlaskConical size={12} aria-hidden="true" /> Simulated state · hypothetical
          </span>
          {readiness && (
            <div className="simulation-state-metric">
              <strong>{readiness.after}%</strong>
              <span>
                portfolio readiness{" "}
                <em className={`what-if-delta what-if-delta-${deltaTone(readiness.delta, true)}`}>
                  {formatDelta(readiness.delta, " pts")}
                </em>
              </span>
            </div>
          )}
          <div className="simulation-state-metric">
            <strong>{formatScore(finding.risk.after.score)}</strong>
            <span>
              quantum risk <SeverityBadge value={finding.risk.after.severity} />{" "}
              <em className={`what-if-delta what-if-delta-${deltaTone(finding.risk.delta)}`}>{formatDelta(finding.risk.delta)}</em>
            </span>
          </div>
          <span className="simulation-state-algo">{finding.pqc_component}</span>
        </div>
      </div>

      <p className="what-if-scenario">
        <strong>{finding.current_algorithm}</strong> → <strong className="what-if-option">{finding.pqc_component}</strong>
        <span>
          {finding.strategy === "HYBRID"
            ? `Hybrid: ${finding.classical_component} + ${finding.pqc_component}`
            : "Direct PQC replacement"}
          {" · "}quantum status {finding.quantum_status.before || "unknown"} → {finding.quantum_status.after}
        </span>
      </p>

      <div className="what-if-table-wrap">
        <table className="what-if-table">
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">Current (real)</th>
              <th scope="col">Simulated</th>
              <th scope="col">Change</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} data-metric={row.key}>
                <th scope="row">{row.label}</th>
                <td data-value="before">
                  <strong>{formatScore(row.before.score)}</strong>
                  <SeverityBadge value={row.before[row.level]} />
                </td>
                <td data-value="after">
                  <strong>{formatScore(row.after.score)}</strong>
                  <SeverityBadge value={row.after[row.level]} />
                </td>
                <td data-value="delta" className={`what-if-delta what-if-delta-${deltaTone(row.delta)}`}>
                  {formatDelta(row.delta)}
                </td>
              </tr>
            ))}
            {readiness && (
              <tr data-metric="readiness">
                <th scope="row">Portfolio readiness</th>
                <td data-value="before">
                  <strong>{readiness.before}%</strong>
                </td>
                <td data-value="after">
                  <strong>{readiness.after}%</strong>
                </td>
                <td data-value="delta" className={`what-if-delta what-if-delta-${deltaTone(readiness.delta, true)}`}>
                  {formatDelta(readiness.delta, " pts")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ul className="what-if-notes">
        {readiness && readiness.delta === 0 && (
          <li>
            Readiness counts findings at HIGH/CRITICAL migration priority.{" "}
            {priority.before.level === priority.after.level
              ? `This finding stays at ${priority.after.level} priority`
              : `This finding moves from ${priority.before.level} to ${priority.after.level} priority`}
            , so readiness does not change.
          </li>
        )}
        {vulnerable && (
          <li>
            Quantum-vulnerable findings across the portfolio: {vulnerable.before} → {vulnerable.after}.
          </li>
        )}
        <li>
          Blast radius ({formatScore(finding.carried_forward.blast_radius.score)}) and migration complexity (
          {formatScore(finding.carried_forward.migration_complexity.score)}) are carried forward unchanged: choosing a
          PQC option does not change them.
        </li>
        <li>
          The risk model scores the post-migration quantum status, not the parameter set, so options in the same family
          produce the same scores.
        </li>
      </ul>
    </div>
  );
}

/**
 * What-If Migration Simulator for one finding, addressed by bom_ref.
 * Options, eligibility (KEEP / NEEDS_REVIEW are not simulatable) and
 * every result come from the backend's scenario engine
 * (backend/services/migration_scenario.py); nothing is recomputed or
 * guessed here, and the real finding is never changed.
 *
 * Mounted with key={bomRef}, so switching findings starts fresh.
 */
export function WhatIfSimulator({ bomRef }) {
  const [finding, setFinding] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [runError, setRunError] = useState("");
  const { publishSimulation } = useSpatial();

  // Tell the spatial environment which simulation result is on screen.
  // Every value is copied from the backend response; nothing is computed.
  useEffect(() => {
    if (!result) {
      publishSimulation(bomRef, null);
      return undefined;
    }
    const simulated = result.finding;
    publishSimulation(bomRef, {
      bomRef,
      currentAlgorithm: simulated.current_algorithm,
      pqcComponent: simulated.pqc_component,
      strategy: simulated.strategy,
      risk: simulated.risk,
      priority: simulated.priority,
      readiness: result.portfolio?.readiness_percent || null,
    });
    return () => publishSimulation(bomRef, null);
  }, [result, bomRef, publishSimulation]);

  useEffect(() => {
    let cancelled = false;

    getWhatIfFinding(bomRef)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setFinding(data);
        const preferred = data.options.find((option) => option.recommended) || data.options[0];
        setSelected(preferred?.name || "");
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(error.message || "Unable to load what-if options.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [bomRef]);

  function chooseOption(name) {
    setSelected(name);
    setResult(null);
    setRunError("");
    setStatus("idle");
  }

  async function runSimulation() {
    const option = selected;
    setStatus("loading");
    setRunError("");
    setResult(null);

    try {
      const data = await simulateWhatIf(bomRef, option);
      setResult(data);
      setStatus("success");
    } catch (error) {
      setRunError(error.message || "Simulation failed.");
      setStatus("error");
    }
  }

  const strategy = finding?.strategy;

  return (
    <div className={`what-if${result ? " is-simulating" : ""}`} data-bom-ref={bomRef}>
      <div className="what-if-head">
        <FlaskConical size={14} aria-hidden="true" />
        <span>What-If Simulator</span>
        <TagBadge tone="simulation">Simulation</TagBadge>
      </div>
      <p className="what-if-intro">
        Explore migrating this finding to a PQC option. Results are hypothetical — the real finding, its scores and the
        dataset are not changed.
      </p>

      {!finding && !loadError && <p className="workspace-empty-note">Loading what-if options…</p>}
      {loadError && <p className="what-if-error" role="alert">{loadError}</p>}

      {finding && (
        <>
          {result && (
            <p className="what-if-frozen">
              <Lock size={12} aria-hidden="true" /> Real finding frozen — the simulation below does not change it.
            </p>
          )}
          <dl className="migration-strategy-grid what-if-current">
            <div>
              <dt>Finding</dt>
              <dd>{finding.name}</dd>
            </div>
            <div>
              <dt>bom-ref</dt>
              <dd className="what-if-ref" title={finding.bom_ref}>
                {finding.bom_ref}
              </dd>
            </div>
            <div>
              <dt>Current strategy</dt>
              <dd>{strategy?.label || strategy?.strategy || "Unknown"}</dd>
            </div>
            <div>
              <dt>Current risk</dt>
              <dd>
                {formatScore(finding.current.risk.score)} {finding.current.risk.severity}
              </dd>
            </div>
            <div>
              <dt>Current priority</dt>
              <dd>
                {formatScore(finding.current.priority.score)} {finding.current.priority.level}
              </dd>
            </div>
          </dl>

          {!finding.simulatable ? (
            <div className="what-if-blocked" data-reason={finding.reason_code}>
              <strong>
                {strategy?.strategy === "KEEP"
                  ? "Not simulatable — no PQC migration applies"
                  : strategy?.strategy === "NEEDS_REVIEW"
                  ? "Not simulatable — strategy needs review"
                  : "Not simulatable"}
              </strong>
              <p>{finding.reason}</p>
              {strategy?.strategy === "NEEDS_REVIEW" && (
                <p>
                  Resolve how this finding is used first; a simulation would have to guess its cryptographic role, so
                  no PQC option is offered.
                </p>
              )}
            </div>
          ) : (
            <>
              <fieldset className="what-if-options">
                <legend>
                  Valid {finding.target_family} options for this role
                  {finding.ranking_source_bom_ref && finding.ranking_source_bom_ref !== finding.bom_ref && (
                    <span> · ranking inherited from governing finding</span>
                  )}
                </legend>
                {finding.options.map((option) => (
                  <label
                    key={option.name}
                    className={`what-if-option-row${selected === option.name ? " what-if-option-row-selected" : ""}`}
                  >
                    <input
                      type="radio"
                      name={`what-if-option-${bomRef}`}
                      value={option.name}
                      checked={selected === option.name}
                      onChange={() => chooseOption(option.name)}
                    />
                    <span className="candidate-rank">{option.ranked ? `#${option.rank}` : "—"}</span>
                    <span className="what-if-option-name">
                      <strong>{option.name}</strong>
                      {option.recommended && <TagBadge>Strategy's choice</TagBadge>}
                      {!option.ranked && <TagBadge>Unranked</TagBadge>}
                    </span>
                    <span className="what-if-option-score">
                      {option.ranked ? <strong>{formatScore(option.score)}</strong> : <span>No score</span>}
                    </span>
                  </label>
                ))}
              </fieldset>

              <button
                type="button"
                className="btn btn-outline btn-sm what-if-run"
                onClick={runSimulation}
                disabled={!selected || status === "loading"}
              >
                {status === "loading" ? "Simulating…" : `Run what-if with ${selected}`}
              </button>

              {runError && <p className="what-if-error" role="alert">{runError}</p>}
              {result && <WhatIfResult result={result} />}
            </>
          )}
        </>
      )}
    </div>
  );
}

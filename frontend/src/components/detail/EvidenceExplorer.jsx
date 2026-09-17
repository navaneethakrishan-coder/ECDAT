import { useEffect, useState } from "react";
import { ScanSearch } from "lucide-react";

import { getFindingEvidence } from "../../api";
import { SeverityBadge, TagBadge } from "../Badge";

// Display-only helpers. Nothing here derives, scores or infers evidence:
// a missing value is shown as missing.

function isMissing(value) {
  return value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
}

function Unknown({ children = "Unknown" }) {
  return <span className="evidence-unknown">{children}</span>;
}

function Value({ value, missing = "Unknown", format }) {
  if (isMissing(value)) {
    return <Unknown>{missing}</Unknown>;
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  return format ? format(value) : String(value);
}

function Field({ label, children, mono = false }) {
  return (
    <div className={mono ? "evidence-field evidence-field-mono" : "evidence-field"}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function humanize(key) {
  return String(key).replaceAll("_", " ");
}

function shortRef(bomRef) {
  return bomRef ? `${bomRef.slice(0, 8)}…` : "";
}

function FindingRef({ finding }) {
  return (
    <span className="evidence-finding-ref" title={finding.bom_ref}>
      {finding.name || <Unknown>Unnamed finding</Unknown>} <code>{shortRef(finding.bom_ref)}</code>
    </span>
  );
}

const CHAIN_STATUS = {
  established: "Established",
  "low-confidence": "Low confidence",
  unresolved: "Unresolved",
  unknown: "Unknown",
  "not-applicable": "Not applicable",
};

function EvidenceChain({ steps }) {
  return (
    <ol className="evidence-chain" aria-label="Evidence to decision chain">
      {steps.map((step) => (
        <li key={step.key} className={`evidence-chain-step evidence-status-${step.status}`} data-step={step.key}>
          <div className="evidence-chain-head">
            <strong>{step.label}</strong>
            <span className="evidence-status-chip">{CHAIN_STATUS[step.status] || step.status}</span>
          </div>
          <p>{step.statement}</p>
        </li>
      ))}
    </ol>
  );
}

function Section({ id, title, summary, children }) {
  return (
    <details className="workspace-disclosure evidence-section" data-section={id}>
      <summary>
        <span className="evidence-section-title">{title}</span>
        <span className="evidence-section-summary">{summary}</span>
      </summary>
      <div className="evidence-section-body">{children}</div>
    </details>
  );
}

function IdentitySection({ identity }) {
  const crypto = identity.cbom_crypto_properties || {};
  const properties = Object.entries(crypto).flatMap(([key, value]) =>
    value && typeof value === "object" && !Array.isArray(value)
      ? Object.entries(value).map(([inner, innerValue]) => [`${key}.${inner}`, innerValue])
      : [[key, value]],
  );
  const scan = identity.scan || {};

  return (
    <Section
      id="identity"
      title="Identity"
      summary={
        <>
          {identity.name || "Unknown"} · {identity.asset_type || "unknown type"}
        </>
      }
    >
      <dl className="evidence-grid">
        <Field label="bom-ref" mono>
          {identity.bom_ref}
        </Field>
        <Field label="Algorithm / name">
          <Value value={identity.name} />
        </Field>
        <Field label="Asset type">
          <Value value={identity.asset_type} />
        </Field>
        <Field label="Category">
          <Value value={identity.category} />
        </Field>
        <Field label="Primitive">
          <Value value={identity.primitive} missing="Not recorded" />
        </Field>
        <Field label="OID" mono>
          <Value value={identity.oid} missing="Not recorded" />
        </Field>
      </dl>

      <h4 className="evidence-subheading">Original CycloneDX component</h4>
      {identity.in_raw_cbom ? (
        <dl className="evidence-grid">
          {properties.map(([key, value]) => (
            <Field key={key} label={key} mono>
              <Value value={value} missing="Not recorded" />
            </Field>
          ))}
        </dl>
      ) : (
        <p className="evidence-note">
          <Unknown>Not available</Unknown> — this bom-ref is not present in the raw CBOM file.
        </p>
      )}

      <p className="evidence-note">
        Scan: <Value value={scan.tools} missing="unknown tool" /> · <Value value={scan.format} /> {scan.spec_version} ·{" "}
        <Value value={scan.repository} missing="repository not recorded" /> @ <Value value={scan.commit} missing="commit not recorded" /> ·{" "}
        <Value value={scan.timestamp} missing="time not recorded" />
      </p>
    </Section>
  );
}

function PurposeSection({ purpose }) {
  const supporting = purpose.supporting_evidence || {};

  return (
    <Section
      id="purpose"
      title="Why this purpose?"
      summary={
        <>
          <Value value={purpose.resolved_purposes} missing="Unresolved" /> <TagBadge>{purpose.confidence || "Unknown"} confidence</TagBadge>
          {purpose.repository_evidence === false && <TagBadge>Not repository evidence</TagBadge>}
          {purpose.needs_review && <span className="badge badge-critical">Needs review</span>}
        </>
      }
    >
      <dl className="evidence-grid">
        <Field label="Resolved purpose">
          <Value value={purpose.resolved_purposes} missing="Unresolved" />
        </Field>
        <Field label="Confidence">
          <Value value={purpose.confidence} />
        </Field>
        <Field label="Evidence source">
          <Value value={purpose.evidence_source_label || purpose.evidence_source} />
        </Field>
        <Field label="Repository evidence">
          <Value value={purpose.repository_evidence} />
        </Field>
        <Field label="Usage">
          <Value value={purpose.usage} missing="Not identified" />
        </Field>
        <Field label="Conflicting evidence">
          <Value value={purpose.needs_review} />
        </Field>
      </dl>

      <p className="evidence-reason">
        <Value value={purpose.evidence_reason} missing="No reason recorded" />
      </p>

      <h4 className="evidence-subheading">Supporting context</h4>
      <dl className="evidence-grid">
        <Field label="CBOM primitive" mono>
          <Value value={supporting.cbom_primitive} missing="Not recorded" />
        </Field>
        <Field label="Family fallback purpose">
          <Value value={supporting.family_fallback_purpose} missing="Not used" />
        </Field>
      </dl>
      {isMissing(supporting.source_contexts) ? (
        <p className="evidence-note">
          Source API contexts: <Unknown>None recorded</Unknown>
        </p>
      ) : (
        <ul className="evidence-code-list">
          {supporting.source_contexts.map((context, index) => (
            <li key={`${context}-${index}`}>
              <code>{context}</code>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function SourceSection({ source }) {
  const files = new Set(source.occurrences.map((occurrence) => occurrence.location).filter(Boolean));
  const quality = source.evidence_quality;
  const confidence = source.evidence_confidence;
  const dependencies = source.dependencies;

  return (
    <Section
      id="source"
      title="Where was it found?"
      summary={
        source.occurrence_count ? (
          <>
            {source.occurrence_count} occurrence(s) in {files.size} file(s)
          </>
        ) : (
          <Unknown>No source occurrence recorded</Unknown>
        )
      }
    >
      {source.occurrence_count ? (
        <ul className="evidence-occurrences">
          {source.occurrences.map((occurrence, index) => (
            <li key={`${occurrence.location}-${occurrence.line}-${index}`}>
              <div className="evidence-location">
                <code>{occurrence.location || "Unknown location"}</code>
                <span>
                  line <Value value={occurrence.line} /> · offset <Value value={occurrence.offset} />
                </span>
              </div>
              <div className="evidence-context">
                <Value value={occurrence.context} missing="No API context recorded" format={(value) => <code>{value}</code>} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="evidence-note">
          <Unknown>Not available</Unknown> — the CBOM records no source occurrence for this finding.
        </p>
      )}

      <dl className="evidence-grid">
        <Field label="Evidence quality">
          {quality ? (
            <>
              {quality.score}/100 <TagBadge>{quality.quality || "Unknown"}</TagBadge>
            </>
          ) : (
            <Unknown />
          )}
        </Field>
        <Field label="Evidence confidence">
          {confidence ? (
            <>
              {confidence.score}/100 <TagBadge>{confidence.confidence || "Unknown"}</TagBadge>
            </>
          ) : (
            <Unknown />
          )}
        </Field>
      </dl>
      {confidence?.reasons?.length > 0 && (
        <ul className="evidence-reasons">
          {confidence.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      <h4 className="evidence-subheading">CBOM dependency graph</h4>
      {dependencies ? (
        <dl className="evidence-grid">
          {[
            ["Depends on", dependencies.depends_on],
            ["Direct dependents", dependencies.direct_dependents],
            ["Transitive dependents", dependencies.transitive_dependents],
          ].map(([label, refs]) => (
            <Field key={label} label={label}>
              {refs.length ? (
                <span className="evidence-ref-list">
                  {refs.map((finding) => (
                    <FindingRef key={finding.bom_ref} finding={finding} />
                  ))}
                </span>
              ) : (
                <Unknown>None</Unknown>
              )}
            </Field>
          ))}
        </dl>
      ) : (
        <p className="evidence-note">
          <Unknown>Not available</Unknown> — no dependency-graph record for this finding.
        </p>
      )}
    </Section>
  );
}

function RiskSection({ risk, quantum }) {
  const known = risk.contributions.filter((item) => item.known);

  return (
    <Section
      id="risk"
      title="Why this risk?"
      summary={
        risk.final_score !== null && risk.final_score !== undefined ? (
          <>
            {risk.final_score} <SeverityBadge value={risk.severity} />
            {risk.unknown_factors.length > 0 && <TagBadge>{risk.unknown_factors.length} unknown factor(s)</TagBadge>}
          </>
        ) : (
          <Unknown />
        )
      }
    >
      <dl className="evidence-grid">
        <Field label="Quantum status">
          <Value value={quantum.quantum_status} />
        </Field>
        <Field label="Base quantum risk">
          {quantum.base_risk ? (
            <>
              {quantum.base_risk.score} <SeverityBadge value={quantum.base_risk.severity} />
            </>
          ) : (
            <Unknown />
          )}
        </Field>
      </dl>
      <p className="evidence-reason">
        <Value value={quantum.reason} missing="No quantum-status reason recorded" />
      </p>

      <h4 className="evidence-subheading">Factor contributions</h4>
      <div className="evidence-table-wrap">
        <table className="evidence-table">
          <thead>
            <tr>
              <th scope="col">Factor</th>
              <th scope="col">Input</th>
              <th scope="col">Raw</th>
              <th scope="col">Weight</th>
              <th scope="col">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {risk.contributions.map((item) =>
              item.known ? (
                <tr key={item.factor} data-factor={item.factor}>
                  <th scope="row">{item.label || humanize(item.factor)}</th>
                  <td>
                    <Value value={item.input} />
                  </td>
                  <td>{item.raw_score}</td>
                  <td>{item.weight}</td>
                  <td>
                    <strong>{item.weighted_score}</strong>
                  </td>
                </tr>
              ) : (
                <tr key={item.factor} data-factor={item.factor} className="evidence-row-unknown">
                  <th scope="row">{item.label || humanize(item.factor)}</th>
                  <td colSpan={4}>
                    <Unknown>Unknown — excluded, not guessed</Unknown>
                    {item.reason && <span className="evidence-row-reason">{item.reason}</span>}
                  </td>
                </tr>
              ),
            )}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Total</th>
              <td colSpan={3}>
                {known.length} known factor(s); weights rescaled over known factors
              </td>
              <td>
                <strong>{risk.contribution_total ?? "—"}</strong> = {risk.final_score ?? "—"}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <h4 className="evidence-subheading">Risk context</h4>
      <dl className="evidence-context-list">
        {risk.context.map((factor) => (
          <div key={factor.factor} data-factor={factor.factor}>
            <dt>
              {factor.factor === "business_criticality" ? "business criticality (path-derived proxy)" : humanize(factor.factor)}
            </dt>
            <dd>
              {factor.known ? <strong>{String(factor.value)}</strong> : <Unknown />}
              <span>{factor.source}</span>
            </dd>
          </div>
        ))}
      </dl>

      <p className="evidence-note">
        Mosca timeline:{" "}
        {risk.mosca.performed ? (
          <>
            urgency <SeverityBadge value={risk.mosca.analysis?.migration_urgency} />
          </>
        ) : (
          <Unknown>{risk.mosca.reason || "Not available"}</Unknown>
        )}
      </p>
    </Section>
  );
}

function MigrationSection({ bomRef, migration }) {
  const { blast_radius: blast, complexity, priority, strategy, pqc } = migration;
  const unresolved = strategy && !strategy.resolved;

  return (
    <Section
      id="migration"
      title="Why this migration decision?"
      summary={
        strategy ? (
          <>
            {strategy.label || strategy.strategy} <TagBadge>{strategy.confidence || "Unknown"} confidence</TagBadge>
            {unresolved && <span className="badge badge-critical">Unresolved</span>}
          </>
        ) : (
          <Unknown>No strategy recorded</Unknown>
        )
      }
    >
      {strategy ? (
        <div className={`evidence-decision${unresolved ? " evidence-decision-unresolved" : ""}`}>
          <dl className="evidence-grid">
            <Field label="Strategy">
              {strategy.label || strategy.strategy}
            </Field>
            <Field label="Confidence">
              <Value value={strategy.confidence} />
            </Field>
            <Field label="Role">
              <Value value={strategy.purpose_class_label} />
            </Field>
            <Field label="PQC family">
              <Value value={strategy.pqc_family} missing={unresolved ? "Unresolved" : "Not applicable"} />
            </Field>
            <Field label="Selected PQC component">
              <Value
                value={pqc.selected_component}
                missing={unresolved ? "None — review required" : pqc.status === "not-applicable" ? "Not applicable" : "None"}
              />
            </Field>
            {strategy.classical_component && (
              <Field label="Classical component">{strategy.classical_component}</Field>
            )}
            {strategy.governing_finding && (
              <Field label="Inherited from">
                <FindingRef finding={strategy.governing_finding} />
              </Field>
            )}
            <Field label="Reason code" mono>
              <Value value={strategy.reason_code} />
            </Field>
          </dl>
          <p className="evidence-reason">
            <Value value={strategy.rationale} missing="No rationale recorded" />
          </p>
          {strategy.decision_factors?.length > 0 && (
            <ul className="evidence-reasons">
              {strategy.decision_factors.map((factor) => (
                <li key={factor.signal}>
                  <strong>{humanize(factor.signal)}</strong>: <Value value={factor.value} /> — {factor.effect} ({factor.source})
                </li>
              ))}
            </ul>
          )}
          {strategy.review_options?.length > 0 && (
            <ul className="evidence-reasons">
              {strategy.review_options.map((option) => (
                <li key={option.purpose_class}>
                  If the usage is <strong>{option.purpose_class_label}</strong>: evaluate{" "}
                  <Value value={option.top_candidate} missing="no available candidate" /> (
                  <Value value={option.pqc_family} missing="no PQC family" />)
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="evidence-note">
          <Unknown>Not available</Unknown> — no migration strategy is recorded for this finding.
        </p>
      )}

      <h4 className="evidence-subheading">Impact inputs</h4>
      <dl className="evidence-grid">
        <Field label="Blast radius">
          {blast ? (
            <>
              {blast.score} <SeverityBadge value={blast.severity} />
            </>
          ) : (
            <Unknown>Not available</Unknown>
          )}
        </Field>
        <Field label="Migration complexity">
          {complexity ? (
            <>
              {complexity.score} <SeverityBadge value={complexity.level} />
            </>
          ) : (
            <Unknown>Not available</Unknown>
          )}
        </Field>
        <Field label="Migration priority">
          {priority ? (
            <>
              {priority.score} <SeverityBadge value={priority.level} />
            </>
          ) : (
            <Unknown>Not available</Unknown>
          )}
        </Field>
      </dl>
      {complexity?.factors && (
        <p className="evidence-note">
          Complexity factors:{" "}
          {Object.entries(complexity.factors)
            .map(([key, value]) => `${humanize(key)} ${value}`)
            .join(" · ")}
        </p>
      )}
      {priority && (
        <ul className="evidence-reasons">
          {priority.contributions.map((item) => (
            <li key={item.factor} data-factor={item.factor}>
              <strong>{humanize(item.factor)}</strong>:{" "}
              {item.known ? (
                <>
                  {item.raw_score} × {item.weight} = {item.weighted_score}
                </>
              ) : (
                <Unknown>Unknown — excluded, not guessed</Unknown>
              )}
            </li>
          ))}
        </ul>
      )}

      <h4 className="evidence-subheading">
        {pqc.status === "unresolved" ? "Ranking-model candidates (not a recommendation)" : "Ranked PQC candidates"}
      </h4>
      {pqc.note && <p className={`evidence-note evidence-pqc-note evidence-pqc-${pqc.status}`}>{pqc.note}</p>}
      {pqc.ranking_source_bom_ref && pqc.ranking_source_bom_ref !== bomRef && (
        <p className="evidence-note">
          This finding is not ranked itself; candidates are the ranking of its governing finding (bom-ref{" "}
          <code>{shortRef(pqc.ranking_source_bom_ref)}</code>).
        </p>
      )}
      {pqc.ranked_candidates.length > 0 ? (
        <div className="evidence-table-wrap">
          <table className={`evidence-table${pqc.status === "unresolved" ? " evidence-table-unconfirmed" : ""}`}>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Candidate</th>
                <th scope="col">Family</th>
                <th scope="col">Score</th>
                <th scope="col">Fits role</th>
              </tr>
            </thead>
            <tbody>
              {pqc.ranked_candidates.map((candidate) => (
                <tr
                  key={`${candidate.rank}-${candidate.candidate}`}
                  className={candidate.candidate === pqc.selected_component ? "evidence-row-selected" : undefined}
                >
                  <td>#{candidate.rank}</td>
                  <th scope="row">
                    {candidate.candidate}
                    {candidate.candidate === pqc.selected_component && <TagBadge>Selected</TagBadge>}
                  </th>
                  <td>
                    <Value value={candidate.family} />
                  </td>
                  <td>
                    <Value value={candidate.score} />
                  </td>
                  <td>
                    {candidate.fits_role === null ? (
                      <Unknown>{pqc.status === "unresolved" ? "Role unresolved" : "n/a"}</Unknown>
                    ) : candidate.fits_role ? (
                      "Yes"
                    ) : (
                      "No"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="evidence-note">
          <Unknown>None ranked</Unknown>
        </p>
      )}
      {pqc.mapping && (
        <p className="evidence-note">
          PQC mapping: <Value value={pqc.mapping.migration_type} /> · confidence <Value value={pqc.mapping.confidence} /> —{" "}
          <Value value={pqc.mapping.reason} missing="no reason recorded" />
        </p>
      )}
    </Section>
  );
}

/**
 * Evidence Explorer: "why did ECDAT classify, score and recommend this
 * migration path?" for one finding, addressed by bom_ref. Everything is
 * read from GET /api/evidence/{bom_ref}, which only re-arranges existing
 * pipeline outputs. Mounted with key={bomRef}, so switching findings
 * never shows the previous finding's evidence.
 */
export function EvidenceExplorer({ bomRef }) {
  const [evidence, setEvidence] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    getFindingEvidence(bomRef)
      .then((data) => {
        if (!cancelled) {
          setEvidence(data);
        }
      })
      .catch((failure) => {
        if (!cancelled) {
          setError(failure.message || "Unable to load evidence.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [bomRef]);

  return (
    <section
      className="workspace-panel panel-evidence-explorer"
      aria-labelledby="evidence-explorer-heading"
      data-bom-ref={bomRef}
    >
      <h3 id="evidence-explorer-heading">
        <ScanSearch size={15} aria-hidden="true" />
        Evidence Explorer
        <span className="evidence-explorer-question">Why did ECDAT classify, score and recommend this path?</span>
      </h3>

      {!evidence && !error && <p className="workspace-empty-note">Loading evidence…</p>}
      {error && (
        <p className="evidence-error" role="alert">
          {error}
        </p>
      )}

      {evidence && evidence.bom_ref === bomRef && (
        <>
          <EvidenceChain steps={evidence.chain} />
          <div className="evidence-sections">
            <IdentitySection identity={evidence.identity} />
            <PurposeSection purpose={evidence.purpose} />
            <SourceSection source={evidence.source} />
            <RiskSection risk={evidence.risk} quantum={evidence.quantum} />
            <MigrationSection bomRef={evidence.bom_ref} migration={evidence.migration} />
          </div>
        </>
      )}
    </section>
  );
}

import { Activity, Database, FileSearch, FileWarning } from "lucide-react";
import { SeverityBadge, TagBadge } from "../Badge";

function EvidenceList({ title, icon: Icon, items }) {
  return (
    <div className="impact-list">
      <div className="impact-list-title">{title}</div>

      {items.length > 0 ? (
        items.map((item, index) => (
          <div className="impact-list-item" key={`${item}-${index}`}>
            <Icon size={14} />
            <span>{item}</span>
          </div>
        ))
      ) : (
        <div className="impact-empty">None affected</div>
      )}
    </div>
  );
}

/**
 * Left column, row 2. The raw evidence backing every score above --
 * kept quiet and tertiary by default (three counters), with the
 * actual file/class/function lists behind a disclosure toggle rather
 * than always-expanded, so a first-time viewer isn't forced to scroll
 * past a wall of file paths to reach the AI Advisor.
 */
export function EvidencePanel({ assetDetail }) {
  const sourceImpact = assetDetail?.source_impact || {};
  const fileCount = sourceImpact.affected_file_count ?? 0;
  const classCount = sourceImpact.affected_class_count ?? 0;
  const functionCount = sourceImpact.affected_function_count ?? 0;

  const hasEvidence = fileCount + classCount + functionCount > 0;

  const classification = assetDetail?.classification || {};
  const purposeReason = classification.purpose_evidence_reason;

  return (
    <section className="workspace-panel panel-evidence" aria-labelledby="evidence-heading">
      <h3 id="evidence-heading">
        <FileSearch size={15} aria-hidden="true" />
        Source &amp; Evidence
      </h3>

      <div className="evidence-stats">
        <div className="evidence-stat">
          <strong>{fileCount}</strong>
          <span>Files</span>
        </div>
        <div className="evidence-stat">
          <strong>{classCount}</strong>
          <span>Classes</span>
        </div>
        <div className="evidence-stat">
          <strong>{functionCount}</strong>
          <span>Functions</span>
        </div>
      </div>

      {purposeReason && (
        <details className="workspace-disclosure" id="asset-purpose-evidence-section">
          <summary>
            Why this classification?
            {classification.purpose_needs_review && (
              <span className="badge badge-critical">Needs review</span>
            )}
          </summary>
          <div className="purpose-evidence-body">
            <div className="purpose-evidence-row">
              <span>Confidence</span>
              <SeverityBadge value={classification.purpose_confidence} />
            </div>
            <div className="purpose-evidence-row">
              <span>Evidence source</span>
              <TagBadge>{classification.purpose_evidence_source || "unknown"}</TagBadge>
            </div>
            <p className="workspace-empty-note">{purposeReason}</p>
          </div>
        </details>
      )}

      {hasEvidence ? (
        <details className="workspace-disclosure" id="asset-source-impact-section">
          <summary>View affected files &amp; usage context</summary>
          <div className="source-impact-lists">
            <EvidenceList title="Affected Files" icon={FileWarning} items={sourceImpact.affected_files || []} />
            <EvidenceList title="Affected Classes" icon={Database} items={sourceImpact.affected_classes || []} />
            <EvidenceList
              title="Affected Functions"
              icon={Activity}
              items={sourceImpact.affected_functions || []}
            />
          </div>
        </details>
      ) : (
        <p className="workspace-empty-note">No source-code evidence recorded for this asset.</p>
      )}
    </section>
  );
}

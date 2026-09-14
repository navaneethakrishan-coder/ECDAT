import { AIAdvisorPanel } from "./AIAdvisorPanel";
import { ErrorState } from "./States";
import { AssetHeaderBand } from "./detail/AssetHeaderBand";
import { EvidencePanel } from "./detail/EvidencePanel";
import { MigrationFlow } from "./detail/MigrationFlow";
import { RiskImpactPanel } from "./detail/RiskImpactPanel";

/**
 * The asset-detail experience: an investigation workspace, not a
 * scroll of stacked cards. A full-width header band leads with
 * identity and a large risk readout, then a 2x2 grid groups related
 * information into visual regions the way the task brief specified:
 *
 *   [ Risk & Impact ]      [ Migration Path ]
 *   [ Source & Evidence ]  [ AI Advisor ]
 *
 * All data comes from the single GET /api/asset/{name} call already
 * made by App.jsx -- no new requests, no invented fields.
 */
export function AssetDetailPanel({
  assetName,
  assetDetail,
  loading,
  error,
  onRetry,
  onClose,
  aiStatus,
  aiAdvice,
  aiError,
  onGenerateAdvice,
}) {
  return (
    <div className="asset-workspace" role="dialog" aria-modal="true" aria-label={`${assetName} investigation`}>
      <div className="asset-workspace-topbar">
        <div className="breadcrumb">Asset Investigation / {assetName}</div>
        <button type="button" className="asset-detail-close" onClick={onClose}>
          Close
        </button>
      </div>

      {loading ? (
        <div className="asset-detail-loading" role="status">
          <div className="loading-spinner" />
          <p>Loading asset analysis...</p>
        </div>
      ) : assetDetail ? (
        <>
          <AssetHeaderBand assetName={assetName} assetDetail={assetDetail} />

          <div className="asset-workspace-grid">
            <RiskImpactPanel assetDetail={assetDetail} />
            <MigrationFlow assetDetail={assetDetail} />
            <EvidencePanel assetDetail={assetDetail} />

            <AIAdvisorPanel
              assetName={assetName}
              assetDetail={assetDetail}
              status={aiStatus}
              advice={aiAdvice}
              error={aiError}
              onGenerate={onGenerateAdvice}
            />
          </div>
        </>
      ) : (
        <div className="asset-detail-loading">
          <ErrorState message={error || "Unable to load asset analysis."} onRetry={onRetry} />
        </div>
      )}
    </div>
  );
}

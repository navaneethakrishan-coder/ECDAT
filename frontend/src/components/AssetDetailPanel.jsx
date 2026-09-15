import { AIAdvisorPanel } from "./AIAdvisorPanel";
import { ErrorState } from "./States";
import { AssetHeaderBand } from "./detail/AssetHeaderBand";
import { EvidencePanel } from "./detail/EvidencePanel";
import { MigrationFlow } from "./detail/MigrationFlow";
import { RiskImpactPanel } from "./detail/RiskImpactPanel";

/**
 * The asset-detail experience: an investigation workspace. A header
 * band leads with identity, the risk score, priority and the PQC
 * recommendation; then Evidence and Risk Intelligence stack on the
 * left beside the Migration Path decision flow, and the AI Advisor
 * spans below to explain all of it:
 *
 *   [ Source & Evidence ]  [ Migration Path    ]
 *   [ Risk Intelligence ]  [ (vertical flow)   ]
 *   [               AI Advisor                 ]
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
            <div className="workspace-column">
              <EvidencePanel assetDetail={assetDetail} />
              <RiskImpactPanel assetDetail={assetDetail} />
            </div>

            <MigrationFlow assetDetail={assetDetail} />
          </div>

          <AIAdvisorPanel
            assetName={assetName}
            assetDetail={assetDetail}
            status={aiStatus}
            advice={aiAdvice}
            error={aiError}
            onGenerate={onGenerateAdvice}
          />
        </>
      ) : (
        <div className="asset-detail-loading">
          <ErrorState message={error || "Unable to load asset analysis."} onRetry={onRetry} />
        </div>
      )}
    </div>
  );
}

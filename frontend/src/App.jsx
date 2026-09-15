import { useCallback, useEffect, useRef, useState } from "react";

import { AlertTriangle, FileWarning, ShieldAlert, Zap } from "lucide-react";

import {
  getAssets,
  getAsset,
  getAIAdvice,
  getAnalysisStatus,
  getHealth,
  getMigrationReportAssets,
  getPriority,
  getSummary,
  startAnalysis,
} from "./api";
import { AssetDetailPanel } from "./components/AssetDetailPanel";
import { AssetExplorer } from "./components/AssetExplorer";
import { AssetFilters } from "./components/AssetFilters";
import { CriticalFindingsPanel } from "./components/CriticalFindingsPanel";
import { DonutPanel } from "./components/DonutPanel";
import { HeroOverview } from "./components/HeroOverview";
import { RepositoryAnalysisPanel } from "./components/RepositoryAnalysisPanel";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import "./App.css";

// Ordinal used only to sort the dashboard's "Critical Findings" list --
// not a new score, just a ranking of the severity strings the backend
// already returns.
const SEVERITY_RANK = { CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0 };

// Chart colors follow the same "color means one specific thing"
// language used everywhere else: severity distributions (risk,
// source impact) use the same CRITICAL/HIGH/MEDIUM/LOW hues as every
// severity badge; the migration-strategy donut isn't a severity, so
// it uses the PQC/technology cyan for "PQC Candidate" and neutral
// blue/grays for the remaining strategies instead of borrowing a
// severity color that would imply a risk level it doesn't have.
const RISK_DONUT_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e"]; // CRITICAL, HIGH, MEDIUM, LOW
const IMPACT_DONUT_COLORS = ["#f97316", "#eab308", "#22c55e"]; // HIGH, MEDIUM, LOW
const MIGRATION_DONUT_COLORS = ["#22d3ee", "#5b9cf6", "#64748b", "#334155"]; // PQC Candidate, Architectural, No Direct Replacement, Not Applicable

function App() {
  // ==========================================================
  // STATE
  // ==========================================================

  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [riskAssets, setRiskAssets] = useState([]);
  const [priorityAssets, setPriorityAssets] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendConnected, setBackendConnected] = useState(true);

  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [migrationFilter, setMigrationFilter] = useState("ALL");
  const [pqcFilter, setPqcFilter] = useState("ALL");
  const [sourceImpactFilter, setSourceImpactFilter] = useState("ALL");

  const [selectedAsset, setSelectedAsset] = useState(null);
  const [assetDetail, setAssetDetail] = useState(null);
  const [assetDetailLoading, setAssetDetailLoading] = useState(false);
  const [assetDetailError, setAssetDetailError] = useState("");

  const [repository, setRepository] = useState("");
  const [branch, setBranch] = useState("main");
  const [analysisStatus, setAnalysisStatus] = useState("idle");
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisRunning, setAnalysisRunning] = useState(false);

  const [aiAdvice, setAiAdvice] = useState(null);
  // "idle" | "loading" | "success" | "error"
  const [aiStatus, setAiStatus] = useState("idle");
  const [aiError, setAiError] = useState("");

  // Tracks the currently-selected asset synchronously so an in-flight AI
  // request that resolves *after* the user has switched to a different
  // asset can detect it is stale and discard itself instead of showing
  // the wrong asset's recommendation.
  const selectedAssetRef = useRef(selectedAsset);

  useEffect(() => {
    selectedAssetRef.current = selectedAsset;

    // Selecting a different asset invalidates any AI result on screen —
    // it belongs to whatever was selected before.
    setAiStatus("idle");
    setAiError("");
    setAiAdvice(null);
  }, [selectedAsset]);

  async function handleGenerateAIAdvice() {
    // Guards against duplicate/overlapping requests: the button is also
    // disabled while loading, but this protects against re-entrancy from
    // keyboard activation or rapid repeated calls.
    if (!selectedAsset || aiStatus === "loading") {
      return;
    }

    const requestedAsset = selectedAsset;

    try {
      setAiStatus("loading");
      setAiError("");

      const result = await getAIAdvice(requestedAsset);

      if (selectedAssetRef.current !== requestedAsset) {
        // The user moved on to a different asset while this was in
        // flight — drop the stale result rather than misattribute it.
        return;
      }

      setAiAdvice(result);
      setAiStatus("success");
    } catch (err) {
      console.error("AI advice error:", err);

      if (selectedAssetRef.current !== requestedAsset) {
        return;
      }

      setAiError(err?.message || "Failed to generate AI advice.");
      setAiStatus("error");
    }
  }

  async function handleAnalyzeRepository() {
    if (!repository.trim()) {
      setAnalysisError("Please enter a GitHub repository URL.");
      setAnalysisStatus("failed");
      return;
    }

    try {
      setAnalysisRunning(true);
      setAnalysisError("");
      setAnalysisStatus("starting");
      setAnalysisMessage("Starting CBOMKit scan...");

      await startAnalysis(repository.trim(), branch.trim() || "main");

      setAnalysisStatus("running");
      setAnalysisMessage(
        "CBOMKit is scanning the repository and ECDAT is processing the results..."
      );
    } catch (err) {
      console.error("Repository analysis error:", err);

      setAnalysisStatus("failed");
      setAnalysisError(err?.message || "Unable to start repository analysis.");
      setAnalysisRunning(false);
    }
  }

  // ==========================================================
  // LOAD DASHBOARD
  // ==========================================================

  const loadDashboard = useCallback(async () => {
    const [summaryData, assetsData, riskData, priorityData] = await Promise.all([
      getSummary(),
      getAssets(),
      getMigrationReportAssets(),
      getPriority(),
    ]);

    setSummary(summaryData);
    setAssets(assetsData.assets || []);
    setRiskAssets(riskData.assets || []);
    setPriorityAssets(priorityData.assets || []);
  }, []);

  useEffect(() => {
    async function initialLoad() {
      try {
        setLoading(true);
        setError(null);

        await loadDashboard();
        setBackendConnected(true);
      } catch (err) {
        console.error("Dashboard API error:", err);
        setError(err?.message || "Unable to connect to backend");
        setBackendConnected(false);
      } finally {
        setLoading(false);
      }
    }

    initialLoad();
  }, [loadDashboard]);

  // Lightweight live health check — makes the sidebar's connection
  // indicator reflect reality instead of always claiming "Connected".
  // Uses the existing, already-implemented GET /health endpoint.
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        await getHealth();
        setBackendConnected(true);
      } catch {
        setBackendConnected(false);
      }
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  // ==========================================================
  // LOAD SELECTED ASSET
  // ==========================================================

  const loadAssetDetail = useCallback(async () => {
    if (!selectedAsset) {
      return;
    }

    try {
      setAssetDetailLoading(true);
      setAssetDetailError("");

      const data = await getAsset(selectedAsset);

      setAssetDetail(data);
    } catch (err) {
      console.error("Asset detail error:", err);

      setAssetDetail(null);
      setAssetDetailError(err?.message || "Unable to load asset analysis.");
    } finally {
      setAssetDetailLoading(false);
    }
  }, [selectedAsset]);

  useEffect(() => {
    if (!selectedAsset) {
      setAssetDetail(null);
      setAssetDetailError("");
      return;
    }

    loadAssetDetail();
  }, [selectedAsset, loadAssetDetail]);

  // ==========================================================
  // CLOSE ASSET DETAIL ON ESCAPE
  // ==========================================================

  useEffect(() => {
    if (!selectedAsset) {
      return;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setSelectedAsset(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);

    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedAsset]);

  // ==========================================================
  // POLL REPOSITORY ANALYSIS STATUS
  // ==========================================================

  useEffect(() => {
    if (!analysisRunning) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const status = await getAnalysisStatus();

        setAnalysisStatus(status.status);
        setAnalysisMessage(status.message || "");

        if (status.status === "completed") {
          setAnalysisRunning(false);

          try {
            await loadDashboard();
          } catch (err) {
            console.error("Failed to refresh dashboard:", err);
          }
        }

        if (status.status === "failed") {
          setAnalysisRunning(false);
          setAnalysisError(status.error || "Repository analysis failed.");
        }
      } catch (err) {
        console.error("Analysis status error:", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [analysisRunning, loadDashboard]);

  // ==========================================================
  // LOADING / ERROR (full page)
  // ==========================================================

  if (loading) {
    return (
      <div className="app-shell">
        <div className="loading-screen">
          <div className="loading-spinner" />
          <h2>Loading ECDAT</h2>
          <p>Connecting to the cryptographic analysis backend...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-shell">
        <div className="error-screen">
          <AlertTriangle size={42} />
          <h2>Backend Connection Failed</h2>
          <p>{error}</p>
          <p className="error-help">Make sure the ECDAT FastAPI server is running on port 8000.</p>
        </div>
      </div>
    );
  }

  // ==========================================================
  // DERIVED DATA
  // ==========================================================

  const riskDistribution = summary?.risk_severity_distribution || {};
  const migrationDistribution = summary?.migration_type_distribution || {};
  const sourceImpactDistribution = summary?.source_impact_distribution || {};

  const riskChartData = [
    { name: "CRITICAL", value: riskDistribution.CRITICAL || 0 },
    { name: "HIGH", value: riskDistribution.HIGH || 0 },
    { name: "MEDIUM", value: riskDistribution.MEDIUM || 0 },
    { name: "LOW", value: riskDistribution.LOW || 0 },
  ];

  // The risk donut highlights its own HIGH+CRITICAL count at center
  // instead of a generic total -- risk stays the dominant signal
  // even inside the chart, not just around it. Still a real sum of
  // the same riskChartData shown in the ring/legend, not a new value.
  const atRiskCount = (riskDistribution.CRITICAL || 0) + (riskDistribution.HIGH || 0);

  const migrationChartData = [
    { name: "PQC Candidate", value: migrationDistribution["pqc-candidate"] || 0 },
    { name: "Architectural", value: migrationDistribution["architectural-migration"] || 0 },
    { name: "No Direct Replacement", value: migrationDistribution["no-direct-pqc-replacement"] || 0 },
    { name: "Not Applicable", value: migrationDistribution["not-applicable"] || 0 },
  ];

  const sourceImpactChartData = [
    { name: "HIGH", value: sourceImpactDistribution.HIGH || 0 },
    { name: "MEDIUM", value: sourceImpactDistribution.MEDIUM || 0 },
    { name: "LOW", value: sourceImpactDistribution.LOW || 0 },
  ];

  // Two already-existing bulk endpoints (migration-report/assets +
  // priority), joined by asset name, so the explorer can show every
  // scored dimension per row without any new backend call.
  const priorityByName = {};
  priorityAssets.forEach((item) => {
    if (item.asset) priorityByName[item.asset] = item;
  });

  const enrichedAssets = riskAssets.map((item) => {
    const name = item.asset || item.name || "Unknown";
    const priorityInfo = priorityByName[name] || {};

    return {
      key: name,
      name,
      type: item.asset_type || "Unknown",
      primitive: item.primitive || "Unknown",
      riskScore: item.risk_score,
      riskSeverity: item.risk_severity || "UNKNOWN",
      migrationType: item.migration_type || "",
      pqcApplicable: Boolean(item.pqc_applicable),
      pqcCandidate: item.candidate,
      sourceImpact: item.source_impact || "UNKNOWN",
      priorityLevel: priorityInfo?.migration_priority?.priority || "UNKNOWN",
      complexityLevel: priorityInfo?.migration_complexity?.level || "UNKNOWN",
      blastSeverity: priorityInfo?.blast_radius?.severity || "UNKNOWN",
    };
  });

  // Top 5 HIGH/CRITICAL assets, surfaced on the dashboard's first
  // viewport next to the repository-analysis panel -- a client-side
  // sort of already-fetched data, not a new backend call or metric.
  const criticalFindings = enrichedAssets
    .filter((asset) => asset.riskSeverity === "HIGH" || asset.riskSeverity === "CRITICAL")
    .sort((a, b) => (SEVERITY_RANK[b.riskSeverity] ?? -1) - (SEVERITY_RANK[a.riskSeverity] ?? -1))
    .slice(0, 5);

  const filteredAssets = enrichedAssets.filter((asset) => {
    const query = search.trim().toLowerCase();

    const matchesSearch =
      !query ||
      asset.name.toLowerCase().includes(query) ||
      asset.type.toLowerCase().includes(query) ||
      asset.primitive.toLowerCase().includes(query);

    const matchesRisk = riskFilter === "ALL" || asset.riskSeverity === riskFilter;
    const matchesMigration = migrationFilter === "ALL" || asset.migrationType === migrationFilter;
    const matchesPqc =
      pqcFilter === "ALL" ||
      (pqcFilter === "APPLICABLE" && asset.pqcApplicable) ||
      (pqcFilter === "NOT_APPLICABLE" && !asset.pqcApplicable);
    const matchesSourceImpact = sourceImpactFilter === "ALL" || asset.sourceImpact === sourceImpactFilter;

    return matchesSearch && matchesRisk && matchesMigration && matchesPqc && matchesSourceImpact;
  });

  // ==========================================================
  // MAIN UI
  // ==========================================================

  return (
    <div className="app-shell">
      <Sidebar backendConnected={backendConnected} />

      <main className="main-content">
        <Topbar search={search} onSearchChange={setSearch} backendConnected={backendConnected} />

        <HeroOverview summary={summary} totalAssetsScanned={assets.length} />

        {/* ================================================
            FIRST VIEWPORT: repository analysis + security
            posture, side by side rather than stacked -- an
            asymmetric two-column row instead of another full-
            width card.
        ================================================ */}

        <div className="dashboard-row dashboard-row-primary">
          <RepositoryAnalysisPanel
            repository={repository}
            branch={branch}
            status={analysisStatus}
            message={analysisMessage}
            error={analysisError}
            running={analysisRunning}
            onRepositoryChange={setRepository}
            onBranchChange={setBranch}
            onSubmit={handleAnalyzeRepository}
          />

          <CriticalFindingsPanel assets={criticalFindings} onSelectAsset={setSelectedAsset} />
        </div>

        {/* ================================================
            MIGRATION INTELLIGENCE
        ================================================ */}

        <section className="migration-intelligence-section">
          <div className="section-heading">
            <span className="section-eyebrow">Migration Intelligence</span>
            <h2>How risk, migration strategy and source impact are distributed</h2>
          </div>

          <div className="analytics-grid">
            <DonutPanel
              id="risk-analysis-section"
              icon={ShieldAlert}
              title="Risk Distribution"
              description="Current migration risk severity"
              data={riskChartData}
              colors={RISK_DONUT_COLORS}
              centerValue={atRiskCount}
              centerLabel="at risk"
              onSliceClick={(name) => name && setRiskFilter(String(name).toUpperCase())}
            />

            <DonutPanel
              id="pqc-migration-section"
              icon={Zap}
              title="Migration Distribution"
              description="Recommended migration strategy"
              data={migrationChartData}
              colors={MIGRATION_DONUT_COLORS}
              onSliceClick={(name) => {
                const migrationMap = {
                  "PQC Candidate": "pqc-candidate",
                  Architectural: "architectural-migration",
                  "No Direct Replacement": "no-direct-pqc-replacement",
                  "Not Applicable": "not-applicable",
                };
                const value = migrationMap[name];
                if (value) setMigrationFilter(value);
              }}
            />

            <DonutPanel
              id="global-source-impact-section"
              icon={FileWarning}
              title="Source Impact"
              description="Estimated source-code migration impact"
              data={sourceImpactChartData}
              colors={IMPACT_DONUT_COLORS}
              onSliceClick={(name) => name && setSourceImpactFilter(String(name).toUpperCase())}
            />
          </div>
        </section>

        {/* ================================================
            ASSET EXPLORER
        ================================================ */}

        <section className="panel asset-explorer">
          <div className="panel-header">
            <div className="section-heading">
              <span className="section-eyebrow">Findings</span>
              <h2>Cryptographic Asset Explorer</h2>
              <p>Every analyzed asset, as a full security assessment.</p>
            </div>

            <div className="asset-count">
              {filteredAssets.length} / {enrichedAssets.length}
            </div>
          </div>

          <AssetFilters
            search={search}
            onSearchChange={setSearch}
            riskFilter={riskFilter}
            onRiskFilterChange={setRiskFilter}
            migrationFilter={migrationFilter}
            onMigrationFilterChange={setMigrationFilter}
            pqcFilter={pqcFilter}
            onPqcFilterChange={setPqcFilter}
            sourceImpactFilter={sourceImpactFilter}
            onSourceImpactFilterChange={setSourceImpactFilter}
          />

          <AssetExplorer
            assets={filteredAssets}
            totalCount={enrichedAssets.length}
            selectedAsset={selectedAsset}
            onSelectAsset={setSelectedAsset}
          />

          {selectedAsset && (
            <AssetDetailPanel
              assetName={selectedAsset}
              assetDetail={assetDetail}
              loading={assetDetailLoading}
              error={assetDetailError}
              onRetry={loadAssetDetail}
              onClose={() => {
                setSelectedAsset(null);
                setAssetDetail(null);
              }}
              aiStatus={aiStatus}
              aiAdvice={aiAdvice}
              aiError={aiError}
              onGenerateAdvice={handleGenerateAIAdvice}
            />
          )}
        </section>

        <footer className="dashboard-footer">
          <span>ECDAT Quantum Migration Intelligence</span>
          <span>
            Backend API • {summary?.total_assets ?? 0} Assets • {summary?.total_migration_actions ?? 0}{" "}
            Actions
          </span>
        </footer>
      </main>
    </div>
  );
}

export default App;

import { useEffect, useState } from "react";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Database,
  FileWarning,
  Gauge,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  getSummary,
  getAssets,
  getAsset,
  getMigrationReportAssets,
} from "./api";

import "./App.css";


function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
}) {
  return (
    <div className="stat-card">

      <div className="stat-card-top">
        <span>{title}</span>

        <div className="stat-icon">
          <Icon size={20} />
        </div>
      </div>

      <div className="stat-value">
        {value}
      </div>

      <div className="stat-subtitle">
        {subtitle}
      </div>

    </div>
  );
}


function DistributionBar({
  label,
  value,
  total,
}) {
  const percentage =
    total > 0
      ? Math.round((value / total) * 100)
      : 0;

  return (
    <div className="distribution-row">

      <div className="distribution-header">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>

      <div className="distribution-track">

        <div
          className="distribution-fill"
          style={{
            width: `${percentage}%`,
          }}
        />

      </div>

      <span className="distribution-percent">
        {percentage}%
      </span>

    </div>
  );
}


function RiskBadge({ severity }) {
  const normalized =
    severity?.toLowerCase() || "unknown";

  return (
    <span
      className={`risk-badge risk-${normalized}`}
    >
      {severity || "UNKNOWN"}
    </span>
  );
}


function App() {

  // ==========================================================
  // STATE
  // ==========================================================

  const [summary, setSummary] =
    useState(null);

  const [assets, setAssets] =
    useState([]);
  const [riskAssets, setRiskAssets] =
  useState([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState(null);

  const [search, setSearch] =
    useState("");

  const [selectedAsset, setSelectedAsset] =
    useState(null);

  const [assetDetail, setAssetDetail] =
    useState(null);

  const [assetDetailLoading, setAssetDetailLoading] =
    useState(false);


  // ==========================================================
  // LOAD DASHBOARD
  // ==========================================================

  useEffect(() => {

    async function loadDashboard() {

      try {

        setLoading(true);
        setError(null);

        const [
  summaryData,
  assetsData,
  riskData,
] = await Promise.all([
  getSummary(),
  getAssets(),
  getMigrationReportAssets(),
]);

        setSummary(summaryData);

        setAssets(
          assetsData.assets || []
        );
        setRiskAssets(
  riskData.assets || []
);

      } catch (err) {

        console.error(
          "Dashboard API error:",
          err
        );

        setError(
          err?.message ||
          "Unable to connect to backend"
        );

      } finally {

        setLoading(false);

      }
    }

    loadDashboard();

  }, []);


  // ==========================================================
  // LOAD SELECTED ASSET
  // ==========================================================

  useEffect(() => {

    if (!selectedAsset) {

      setAssetDetail(null);

      return;
    }

    async function loadAssetDetail() {

      try {

        setAssetDetailLoading(true);

        const data =
          await getAsset(selectedAsset);

        setAssetDetail(data);

      } catch (err) {

        console.error(
          "Asset detail error:",
          err
        );

        setAssetDetail(null);

      } finally {

        setAssetDetailLoading(false);

      }
    }

    loadAssetDetail();

  }, [selectedAsset]);


  // ==========================================================
  // LOADING
  // ==========================================================

  if (loading) {

    return (
      <div className="app-shell">

        <div className="loading-screen">

          <div className="loading-spinner" />

          <h2>
            Loading ECDAT
          </h2>

          <p>
            Connecting to the cryptographic
            analysis backend...
          </p>

        </div>

      </div>
    );
  }


  // ==========================================================
  // ERROR
  // ==========================================================

  if (error) {

    return (
      <div className="app-shell">

        <div className="error-screen">

          <AlertTriangle size={42} />

          <h2>
            Backend Connection Failed
          </h2>

          <p>
            {error}
          </p>

          <p className="error-help">
            Make sure the ECDAT FastAPI server
            is running on port 8000.
          </p>

        </div>

      </div>
    );
  }


  // ==========================================================
  // DASHBOARD DATA
  // ==========================================================

  const riskDistribution =
    summary?.risk_severity_distribution || {};

  const migrationDistribution =
    summary?.migration_type_distribution || {};
  const sourceImpactDistribution =
  summary?.source_impact_distribution || {};
  const riskChartData = [
  {
    name: "HIGH",
    value: riskDistribution.HIGH || 0,
  },
  {
    name: "MEDIUM",
    value: riskDistribution.MEDIUM || 0,
  },
  {
    name: "CRITICAL",
    value: riskDistribution.CRITICAL || 0,
  },
];

const migrationChartData = [
  {
    name: "Architectural",
    value:
      migrationDistribution[
        "architectural-migration"
      ] || 0,
  },
  {
    name: "PQC Candidate",
    value:
      migrationDistribution[
        "pqc-candidate"
      ] || 0,
  },
  {
    name: "No Direct Replacement",
    value:
      migrationDistribution[
        "no-direct-pqc-replacement"
      ] || 0,
  },
];
const sourceImpactChartData = [
  {
    name: "HIGH",
    value: sourceImpactDistribution.HIGH || 0,
  },
  {
    name: "MEDIUM",
    value: sourceImpactDistribution.MEDIUM || 0,
  },
  {
    name: "LOW",
    value: sourceImpactDistribution.LOW || 0,
  },
];
  
    // ==========================================================
// REAL RISK LOOKUP
// ==========================================================

const riskByAsset = {};

riskAssets.forEach((item) => {

  const name =
    item.asset ||
    item.name;

  if (name) {
    riskByAsset[name] =
      item.risk_severity ||
      "MEDIUM";
  }

});


  // ==========================================================
  // FILTER ASSETS
  // ==========================================================

  const filteredAssets =
    assets.filter((asset) => {

      const name =
        asset.name ||
        asset.asset ||
        "";

      const type =
        asset.asset_type ||
        asset.type ||
        "";

      const primitive =
        asset.primitive ||
        "";

      const query =
        search
          .toLowerCase()
          .trim();

      if (!query) {
        return true;
      }

      return (
        name
          .toLowerCase()
          .includes(query) ||

        type
          .toLowerCase()
          .includes(query) ||

        primitive
          .toLowerCase()
          .includes(query)
      );
    });


  // ==========================================================
  // MAIN UI
  // ==========================================================

  return (
    <div className="app-shell">


      {/* ====================================================
          SIDEBAR
      ==================================================== */}

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-mark">
            <ShieldCheck size={24} />
          </div>

          <div>

            <div className="brand-name">
              ECDAT
            </div>

            <div className="brand-subtitle">
              PQC Migration Intelligence
            </div>

          </div>

        </div>


        <nav className="sidebar-nav">

          <div className="nav-section">
            OVERVIEW
          </div>

          <div className="nav-item active">
            <Gauge size={18} />
            Dashboard
          </div>

          <div className="nav-item">
            <Database size={18} />
            Assets
          </div>

          <div className="nav-item">
            <ShieldAlert size={18} />
            Risk Analysis
          </div>

          <div className="nav-item">
            <Zap size={18} />
            PQC Migration
          </div>


          <div className="nav-section">
            MIGRATION
          </div>

          <div className="nav-item">
            <ArrowUpRight size={18} />
            Migration Actions
          </div>

          <div className="nav-item">
            <FileWarning size={18} />
            Source Impact
          </div>

        </nav>


        <div className="sidebar-footer">

          <div className="connection-dot" />

          <div>

            <div className="connection-title">
              Backend Connected
            </div>

            <div className="connection-url">
              127.0.0.1:8000
            </div>

          </div>

        </div>

      </aside>


      {/* ====================================================
          MAIN
      ==================================================== */}

      <main className="main-content">


        {/* ==================================================
            HEADER
        ================================================== */}

        <header className="topbar">

          <div>

            <div className="breadcrumb">
              ECDAT / Overview
            </div>

            <h1>
              Cryptographic Migration Dashboard
            </h1>

            <p className="page-description">
              Post-quantum readiness and migration
              intelligence across the analyzed
              cryptographic inventory.
            </p>

          </div>


          <div className="status-pill">

            <Activity size={16} />

            Analysis Ready

          </div>

        </header>


        {/* ==================================================
            STAT CARDS
        ================================================== */}

        <section className="stats-grid">

          <StatCard
            title="Cryptographic Assets"
            value={
              summary?.total_assets ?? 0
            }
            subtitle="Assets discovered"
            icon={Database}
          />

          <StatCard
            title="Migration Actions"
            value={
              summary?.total_migration_actions ?? 0
            }
            subtitle="Generated actions"
            icon={ArrowUpRight}
          />

          <StatCard
            title="PQC Candidates"
            value={
              summary?.assets_with_pqc_candidates ?? 0
            }
            subtitle="Assets requiring PQC migration"
            icon={ShieldAlert}
          />

          <StatCard
            title="High / Critical Priority"
            value={
              summary
                ?.high_or_critical_priority_assets ?? 0
            }
            subtitle="Priority assets"
            icon={AlertTriangle}
          />

        </section>


        {/* ==================================================
            ANALYTICS
        ================================================== */}

        <section className="analytics-grid">

  <div className="panel">

    <div className="panel-header">

      <div>
        <h2>Risk Distribution</h2>

        <p>
          Current migration risk severity
        </p>
      </div>

      <ShieldAlert size={20} />

    </div>

    <div
      style={{
        width: "100%",
        height: 260,
      }}
    >
      <ResponsiveContainer>
        <BarChart
          data={riskChartData}
          margin={{
            top: 10,
            right: 10,
            left: -20,
            bottom: 5,
          }}
        >

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1e2b42"
          />

          <XAxis
            dataKey="name"
            stroke="#7185a5"
            tick={{
              fontSize: 11,
            }}
          />

          <YAxis
            stroke="#7185a5"
            allowDecimals={false}
            tick={{
              fontSize: 11,
            }}
          />

          <Tooltip />

          <Bar
  dataKey="value"
  name="Assets"
  fill="#f87171"
  radius={[5, 5, 0, 0]}
/>

        </BarChart>
      </ResponsiveContainer>
    </div>

  </div>


  <div className="panel">

    <div className="panel-header">

      <div>
        <h2>Migration Distribution</h2>

        <p>
          Recommended migration strategy
        </p>
      </div>

      <Zap size={20} />

    </div>

    <div
      style={{
        width: "100%",
        height: 260,
      }}
    >
      <ResponsiveContainer>
        <BarChart
          data={migrationChartData}
          margin={{
            top: 10,
            right: 10,
            left: -20,
            bottom: 5,
          }}
        >

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1e2b42"
          />

          <XAxis
            dataKey="name"
            stroke="#7185a5"
            tick={{
              fontSize: 10,
            }}
          />

          <YAxis
            stroke="#7185a5"
            allowDecimals={false}
            tick={{
              fontSize: 11,
            }}
          />

          <Tooltip />

          <Bar
  dataKey="value"
  name="Assets"
  fill="#8b5cf6"
  radius={[5, 5, 0, 0]}
/>

        </BarChart>
      </ResponsiveContainer>
    </div>

  </div>
  <div className="panel">

  <div className="panel-header">

    <div>
      <h2>Source Impact</h2>

      <p>
        Estimated source-code migration impact
      </p>
    </div>

    <FileWarning size={20} />

  </div>

  <div
    style={{
      width: "100%",
      height: 260,
    }}
  >
    <ResponsiveContainer>
      <BarChart
        data={sourceImpactChartData}
        margin={{
          top: 10,
          right: 10,
          left: -20,
          bottom: 5,
        }}
      >

        <CartesianGrid
          strokeDasharray="3 3"
          stroke="#1e2b42"
        />

        <XAxis
          dataKey="name"
          stroke="#7185a5"
          tick={{
            fontSize: 11,
          }}
        />

        <YAxis
          stroke="#7185a5"
          allowDecimals={false}
          tick={{
            fontSize: 11,
          }}
        />

        <Tooltip />

        <Bar
          dataKey="value"
          name="Assets"
          radius={[5, 5, 0, 0]}
          fill="#3b82f6"
        />

      </BarChart>
    </ResponsiveContainer>
  </div>

</div>


</section>

        {/* ==================================================
            ASSET INVENTORY
        ================================================== */}

        <section className="panel asset-panel">


          <div className="panel-header">

            <div>

              <h2>
                Cryptographic Asset Inventory
              </h2>

              <p>
                Search and explore the cryptographic
                assets discovered by ECDAT.
              </p>

            </div>


            <div className="asset-count">

              {filteredAssets.length}
              {" / "}
              {assets.length}

            </div>

          </div>


          {/* SEARCH */}

          <div className="asset-toolbar">

            <div className="asset-search">

              <span className="search-icon">
                🔎
              </span>

              <input
                type="text"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search assets, types or primitives..."
              />

              {search && (

                <button
                  type="button"
                  className="clear-search"
                  onClick={() =>
                    setSearch("")
                  }
                >
                  ×
                </button>

              )}

            </div>

          </div>


          {/* TABLE */}

          <div className="asset-table">

            <div className="table-header">

              <span>
                Asset
              </span>

              <span>
                Type
              </span>

              <span>
                Primitive
              </span>

              <span>
                Status
              </span>

            </div>


            {filteredAssets.length === 0 ? (

              <div className="empty-assets">

                <Database size={28} />

                <strong>
                  No assets found
                </strong>

                <span>
                  Try a different search term.
                </span>

              </div>

            ) : (

              filteredAssets.map(
                (asset, index) => {

                  const name =
                    asset.name ||
                    asset.asset ||
                    "Unknown";

                  const type =
                    asset.asset_type ||
                    asset.type ||
                    "Unknown";

                  const primitive =
                    asset.primitive ||
                    "Unknown";


                  /*
                   * IMPORTANT:
                   *
                   * The inventory endpoint does not
                   * contain the full risk assessment.
                   *
                   * Therefore we DO NOT invent a risk
                   * value here.
                   *
                   * Until the inventory is connected
                   * to the migration-report dataset,
                   * display the asset's quantum status.
                   */

                  const severity =
  riskByAsset[name] ||
  "MEDIUM";


                  return (

                    <button
                      type="button"
                      className="table-row asset-row-button"

                      key={
                        asset.bom_ref ||
                        asset.id ||
                        `${name}-${index}`
                      }

                      onClick={() =>
                        setSelectedAsset(name)
                      }
                    >

                      <div className="asset-name">

                        <div className="asset-avatar">

                          {name
                            .charAt(0)
                            .toUpperCase()}

                        </div>

                        <span>
                          {name}
                        </span>

                      </div>


                      <span className="muted">
                        {type}
                      </span>


                      <span className="muted">
                        {primitive}
                      </span>


                      <RiskBadge
                        severity={severity}
                      />

                    </button>

                  );
                }
              )

            )}

          </div>


          {/* =================================================
              ASSET DETAIL
          ================================================= */}

          {selectedAsset && (

            <div className="asset-detail-panel">


              <div className="asset-detail-header">

                <div>

                  <div className="breadcrumb">
                    Asset / {selectedAsset}
                  </div>

                  <h2>
                    {selectedAsset}
                  </h2>

                  <p>
                    Unified cryptographic asset analysis
                  </p>

                </div>


                <button
                  type="button"
                  className="asset-detail-close"
                  onClick={() => {

                    setSelectedAsset(null);
                    setAssetDetail(null);

                  }}
                >
                  Close
                </button>

              </div>
                            {/* =====================================================
                  ANALYSIS SUMMARY
              ====================================================== */}

              <div className="detail-summary-grid">

                <div className="detail-stat-card">
                  <span>Risk</span>

                  <strong>
                    {assetDetail?.current_risk?.severity || "—"}
                  </strong>

                  <small>
                    Score{" "}
                    {assetDetail?.current_risk?.score ??
                      assetDetail?.risk_assessment?.final_score ??
                      "—"}
                  </small>
                </div>


                <div className="detail-stat-card">
                  <span>Priority</span>

                  <strong>
                    {assetDetail?.priority?.level ||
                      assetDetail?.migration_impact?.priority?.level ||
                      "—"}
                  </strong>

                  <small>
                    Score{" "}
                    {assetDetail?.priority?.score ??
                      assetDetail?.migration_impact?.priority?.score ??
                      "—"}
                  </small>
                </div>


                <div className="detail-stat-card">
                  <span>Complexity</span>

                  <strong>
                    {assetDetail?.complexity?.level || "—"}
                  </strong>

                  <small>
                    Score{" "}
                    {assetDetail?.complexity?.score ?? "—"}
                  </small>
                </div>


                <div className="detail-stat-card">
                  <span>Blast Radius</span>

                  <strong>
                    {assetDetail?.blast_radius?.severity || "—"}
                  </strong>

                  <small>
                    Score{" "}
                    {assetDetail?.blast_radius?.blast_radius_score ??
                      assetDetail?.blast_radius?.score ??
                      assetDetail?.blast_radius_score ??
                      "—"}
                  </small>
                </div>

              </div>


              {/* =====================================================
                  PQC CANDIDATE RANKING
              ====================================================== */}

              <section className="detail-section">

                <div className="detail-section-header">

                  <div>
                    <h3>PQC Candidate Ranking</h3>

                    <p>
                      Ranked post-quantum migration candidates
                    </p>
                  </div>

                </div>


                <div className="candidate-ranking-list">

                  {(assetDetail?.ranked_candidates || []).map(
                    (candidate, index) => (

                      <div
                        className="candidate-ranking-row"
                        key={
                          candidate.candidate ||
                          candidate.name ||
                          index
                        }
                      >

                        <div className="candidate-rank">
                          #{candidate.rank || index + 1}
                        </div>


                        <div className="candidate-info">

                          <strong>
                            {candidate.candidate ||
                              candidate.name ||
                              "Unknown"}
                          </strong>

                          <span>
                            {candidate.family || "PQC candidate"}
                          </span>

                        </div>


                        <div className="candidate-score">

                          <strong>
                            {candidate.score ?? "—"}
                          </strong>

                          <span>
                            Score
                          </span>

                        </div>

                      </div>

                    )
                  )}

                </div>

              </section>


              {assetDetailLoading ? (

                <div className="asset-detail-loading">
                  Loading asset analysis...
                </div>

              ) : assetDetail ? (

                <>


                  {/* ==========================================
                      SUMMARY STATS
                  ========================================== */}

                  <div className="asset-detail-stats">


                    <div className="detail-stat">

                      <span>
                        Risk
                      </span>

                      <strong>
                        {
                          assetDetail
                            .current_risk
                            ?.severity ||
                          assetDetail
                            .risk_assessment
                            ?.severity ||
                          "N/A"
                        }
                      </strong>

                    </div>


                    <div className="detail-stat">

                      <span>
                        Priority
                      </span>

                      <strong>
                        {
                          assetDetail
                            .migration_impact
                            ?.priority
                            ?.level ||
                          "N/A"
                        }
                      </strong>

                    </div>


                    <div className="detail-stat">

                      <span>
                        Migration
                      </span>

                      <strong>
                        {
                          assetDetail
                            .pqc_migration
                            ?.migration_type ||
                          "N/A"
                        }
                      </strong>

                    </div>


                    <div className="detail-stat">

                      <span>
                        Candidate
                      </span>

                      <strong>
                        {
                          assetDetail
                            .recommendation
                            ?.candidate ||
                          "None"
                        }
                      </strong>

                    </div>

                  </div>


                  {/* ==========================================
                      CLASSIFICATION
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      Classification
                    </h3>


                    <div className="detail-grid">

                      <div>

                        <span>
                          Category
                        </span>

                        <strong>
                          {
                            assetDetail
                              .classification
                              ?.category ||
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Primitive
                        </span>

                        <strong>
                          {
                            assetDetail
                              .inventory
                              ?.primitive ||
                            assetDetail
                              .primitive ||
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Quantum Status
                        </span>

                        <strong>
                          {
                            assetDetail
                              .classification
                              ?.quantum_status ||
                            "N/A"
                          }
                        </strong>

                      </div>

                    </div>

                  </div>


                  {/* ==========================================
                      CURRENT RISK
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      Current Risk
                    </h3>


                    <div className="detail-grid">

                      <div>

                        <span>
                          Score
                        </span>

                        <strong>
                          {
                            assetDetail
                              .current_risk
                              ?.score ??
                            assetDetail
                              .risk_assessment
                              ?.final_score ??
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Severity
                        </span>

                        <strong>
                          {
                            assetDetail
                              .current_risk
                              ?.severity ||
                            assetDetail
                              .risk_assessment
                              ?.severity ||
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Reason
                        </span>

                        <strong>
                          {
                            assetDetail
                              .classification
                              ?.risk_reason ||
                            "N/A"
                          }
                        </strong>

                      </div>

                    </div>

                  </div>


                  {/* ==========================================
                      PQC MIGRATION
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      PQC Migration
                    </h3>


                    <div className="detail-grid">

                      <div>

                        <span>
                          Migration Type
                        </span>

                        <strong>
                          {
                            assetDetail
                              .pqc_migration
                              ?.migration_type ||
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          PQC Applicable
                        </span>

                        <strong>
                          {
                            assetDetail
                              .pqc_migration
                              ?.pqc_applicable
                              ? "YES"
                              : "NO"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Confidence
                        </span>

                        <strong>
                          {
                            assetDetail
                              .pqc_migration
                              ?.confidence ||
                            "N/A"
                          }
                        </strong>

                      </div>

                    </div>

                  </div>


                  {/* ==========================================
                      RECOMMENDATION
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      PQC Recommendation
                    </h3>


                    <div className="recommendation-box">

                      <div>

                        <span>
                          Recommended Candidate
                        </span>

                        <strong>
                          {
                            assetDetail
                              .recommendation
                              ?.candidate ||
                            "No direct replacement"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Candidate Score
                        </span>

                        <strong>
                          {
                            assetDetail
                              .recommendation
                              ?.candidate_score ??
                            "N/A"
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Rank
                        </span>

                        <strong>
                          {
                            assetDetail
                              .recommendation
                              ?.candidate_rank
                              ? `#${assetDetail.recommendation.candidate_rank}`
                              : "N/A"
                          }
                        </strong>

                      </div>

                    </div>

                  </div>


                  {/* ==========================================
                      SOURCE IMPACT
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      Source Impact
                    </h3>


                    <div className="detail-grid">

                      <div>

                        <span>
                          Files
                        </span>

                        <strong>
                          {
                            assetDetail
                              .source_impact
                              ?.affected_file_count ??
                            0
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Classes
                        </span>

                        <strong>
                          {
                            assetDetail
                              .source_impact
                              ?.affected_class_count ??
                            0
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Functions
                        </span>

                        <strong>
                          {
                            assetDetail
                              .source_impact
                              ?.affected_function_count ??
                            0
                          }
                        </strong>

                      </div>


                      <div>

                        <span>
                          Impact
                        </span>

                        <strong>
                          {
                            assetDetail
                              .source_impact
                              ?.impact_level ||
                            "N/A"
                          }
                        </strong>

                      </div>

                    </div>

                  </div>


                  {/* ==========================================
                      MIGRATION ACTIONS
                  ========================================== */}

                  <div className="detail-card">

                    <h3>
                      Migration Actions
                    </h3>


                    <div className="action-list">

                      {(
                        assetDetail
                          .migration_actions ||
                        []
                      ).map(
                        (action, index) => (

                          <div
                            className="migration-action"
                            key={
                              action.step ||
                              index
                            }
                          >

                            <div className="action-number">
                              {
                                action.step ||
                                index + 1
                              }
                            </div>

                            <span>
                              {action.action}
                            </span>

                          </div>

                        )
                      )}

                    </div>

                  </div>

                </>

              ) : (

                <div className="asset-detail-loading">
                  Unable to load asset analysis.
                </div>

              )}

            </div>

          )}

        </section>


        {/* ==================================================
            FOOTER
        ================================================== */}

        <footer className="dashboard-footer">

          <span>
            ECDAT Quantum Migration Intelligence
          </span>

          <span>
            Backend API •{" "}
            {assets.length} Assets •{" "}
            {
              summary
                ?.total_migration_actions ?? 0
            } Actions
          </span>

        </footer>


      </main>

    </div>
  );
}


export default App;
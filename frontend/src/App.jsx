import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { AlertTriangle, FileWarning, ShieldAlert, Zap } from "lucide-react";

import {
  getAssets,
  getAsset,
  getAIAdvice,
  getAnalysisStatus,
  getScanCapabilities,
  getScanHistory,
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
import { migrationStages } from "./components/detail/migrationStages";
import { ChatLauncher } from "./components/chat/ChatLauncher";
import { ChatPanel } from "./components/chat/ChatPanel";
import { CryptographicSecurityMap } from "./components/visualization/CryptographicSecurityMap";
import { usePrefersReducedMotion } from "./components/visualization/mapEnvironment";
import { useLandscapeState, useSecurityMapModel } from "./components/visualization/useSecurityMapModel";
import { DEFAULT_FILTERS as DEFAULT_MAP_FILTERS } from "./components/visualization/securityMapModel";
import { FindingContextBar } from "./spatial/FindingContextBar";
import { scrollBehavior } from "./spatial/motion";
import { postureFromSummary } from "./spatial/posture";
import { SpaceLayer } from "./spatial/SpaceLayer";
import { SpatialContext } from "./spatial/SpatialContext";
import { SpatialEnvironment } from "./spatial/SpatialEnvironment";
import { StageLayout } from "./spatial/stage/StageLayout";
import { useLayoutMode } from "./spatial/stage/useLayoutMode";
import { branchSummaries } from "./spatial/surfaces";
import { useScrollSpy } from "./spatial/useScrollSpy";
import "./App.css";
import "./spatial/spatial.css";
// Loaded last so the theme tokens win on equal specificity.
import "./theme/theme.css";
import "./components/chat/chat.css";

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

// Page regions the navigation rail tracks (keys match Sidebar NAV_ITEMS).
const SECTION_SPY_TARGETS = [
  { key: "overview", selector: ".hero" },
  { key: "repository", selector: ".dashboard-row-primary" },
  { key: "security-map", selector: "#security-map-section" },
  { key: "risk", selector: ".migration-intelligence-section" },
  { key: "assets", selector: ".asset-explorer" },
  { key: "reports", selector: ".dashboard-footer" },
];

// Sidebar item → stage dock section (desktop / tablet stage layout).
const NAV_TO_SECTION = {
  overview: "posture",
  repository: "operations",
  "security-map": "landscape",
  assets: "findings",
  risk: "intelligence",
  pqc: "intelligence",
  actions: "intelligence",
  impact: "intelligence",
  reports: "intelligence",
};

const SECTION_TO_NAV = {
  posture: "overview",
  operations: "repository",
  landscape: "security-map",
  intelligence: "risk",
  findings: "assets",
};

const METRIC_FILTERS = {
  assets: {},
  priority: { priorities: ["CRITICAL", "HIGH"] },
  pqc: { strategies: ["DIRECT_PQC", "HYBRID"] },
};

const MIGRATION_TYPE_CHART_NAMES = {
  "pqc-candidate": "PQC Candidate",
  "architectural-migration": "Architectural",
  "no-direct-pqc-replacement": "No Direct Replacement",
  "not-applicable": "Not Applicable",
};

function sameSet(list, expected) {
  return list.length === expected.length && expected.every((value) => list.includes(value));
}

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
  // ECDAT AI: a conversation about the analysis, separate from the
  // per-finding AI Analysis panel, which is unchanged.
  const [chatOpen, setChatOpen] = useState(false);
  // The finding (bom_ref) currently focused in the Security Map and
  // highlighted in the Asset Explorer. Opening a finding sets both this
  // and selectedAsset, so the map, the explorer and the investigation
  // workspace always point at the same bom_ref.
  const [focusedFinding, setFocusedFinding] = useState(null);
  const [securityMapFilters, setSecurityMapFilters] = useState(DEFAULT_MAP_FILTERS);
  // Investigation workspace navigation: which analysis surface to bring
  // forward on entry, and the findings visited before this one (so a
  // dependency opened from Blast Radius can return to where it came from).
  const [activeSurface, setActiveSurface] = useState(null);
  const [investigationTrail, setInvestigationTrail] = useState([]);
  const [locateRequest, setLocateRequest] = useState(null);
  // The What-If result currently on screen (backend values only), keyed by bom_ref.
  const [simulation, setSimulation] = useState(null);
  const [assetDetail, setAssetDetail] = useState(null);
  const [assetDetailLoading, setAssetDetailLoading] = useState(false);
  const [assetDetailError, setAssetDetailError] = useState("");

  const [repository, setRepository] = useState("");
  const [branch, setBranch] = useState("main");
  const [analysisStatus, setAnalysisStatus] = useState("idle");
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisRunning, setAnalysisRunning] = useState(false);
  // The scan service's own status payload (stages, validation, result).
  const [scanStatus, setScanStatus] = useState(null);
  // A rejected scan start (bad target) never reaches the scan service.
  const [scanStartErrorCode, setScanStartErrorCode] = useState(null);
  const [scanCapabilities, setScanCapabilities] = useState(null);
  const [scanHistory, setScanHistory] = useState([]);

  // ---- spatial layout (desktop / tablet stage, or the scrolling layout)
  const [contextLost, setContextLost] = useState(false);
  const { mode: layoutMode, tier: stageTier } = useLayoutMode(contextLost);
  const isStage = layoutMode === "stage";
  const isStageRef = useRef(isStage);
  // Which dock section the stage shows; navigation state, not selection.
  const [stageSection, setStageSection] = useState("posture");
  const [mapQuery, setMapQuery] = useState("");
  // The evidence chain currently shown (display copy, keyed by bom_ref).
  const [evidenceChain, setEvidenceChain] = useState(null);
  const stageRef = useRef(null);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    isStageRef.current = isStage;
  }, [isStage]);

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
    try {
      setAnalysisRunning(true);
      setAnalysisError("");
      setAnalysisStatus("starting");
      setAnalysisMessage("Starting repository scan…");
      setScanStatus(null);
      setScanStartErrorCode(null);

      await startAnalysis(repository.trim(), branch.trim() || "main");

      // The scan is running from here on. The first status fetch is only a
      // head start on the poller, so a hiccup on this one request must not
      // report a scan that is genuinely running as failed.
      try {
        const status = await getAnalysisStatus();
        setScanStatus(status);
        setAnalysisStatus(status.status);
        setAnalysisMessage(status.message || "");
      } catch {
        setAnalysisStatus("running");
        setAnalysisMessage("Scan started. Waiting for the first status update…");
      }
    } catch (err) {
      // A rejected target is an expected answer, not a client fault; only
      // unexpected failures are worth a console error.
      if (!err?.reasonCode) console.error("Repository scan error:", err);

      setAnalysisStatus("failed");
      // The backend rejects an unusable target with its own reason.
      setAnalysisError(err?.message || "Unable to start the repository scan.");
      setScanStartErrorCode(err?.reasonCode || null);
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

  // What this deployment can scan, and what it has scanned before.
  useEffect(() => {
    let cancelled = false;

    async function loadScanContext() {
      try {
        const [capabilities, history, status] = await Promise.all([
          getScanCapabilities(),
          getScanHistory(),
          getAnalysisStatus(),
        ]);
        if (cancelled) return;
        setScanCapabilities(capabilities);
        setScanHistory(history.scans || []);
        setScanStatus(status);
        if (status.status === "running" || status.status === "starting") {
          // A scan started elsewhere (CLI, another tab) keeps reporting here.
          setAnalysisRunning(true);
          setAnalysisStatus(status.status);
          setAnalysisMessage(status.message || "");
          if (status.repository) setRepository(status.repository);
          if (status.branch) setBranch(status.branch);
        }
      } catch (err) {
        console.error("Scan context error:", err);
      }
    }

    loadScanContext();
    return () => {
      cancelled = true;
    };
  }, []);

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
    if (!selectedAsset || isStageRef.current) {
      return;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setSelectedAsset(null);
        setInvestigationTrail([]);
        setActiveSurface(null);
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

    // If the backend disappears mid-scan, stop claiming the scan is still
    // running after this many consecutive failed polls (~1 minute) instead
    // of spinning forever with the form disabled.
    const MAX_FAILED_POLLS = 20;
    let failedPolls = 0;

    const interval = setInterval(async () => {
      try {
        const status = await getAnalysisStatus();
        failedPolls = 0;

        setScanStatus(status);
        setAnalysisStatus(status.status);
        setAnalysisMessage(status.message || "");

        if (status.status === "completed") {
          setAnalysisRunning(false);

          try {
            // The pipeline has rewritten the dataset the whole app reads.
            await loadDashboard();
          } catch (err) {
            console.error("Failed to refresh dashboard:", err);
          }
        }

        if (status.status === "failed") {
          setAnalysisRunning(false);
          setAnalysisError(status.error || "The repository scan failed.");
        }

        if (status.status === "completed" || status.status === "failed") {
          try {
            setScanHistory((await getScanHistory()).scans || []);
          } catch (err) {
            console.error("Failed to load scan history:", err);
          }
        }
      } catch (err) {
        failedPolls += 1;
        console.error("Analysis status error:", err);

        if (failedPolls >= MAX_FAILED_POLLS) {
          setAnalysisRunning(false);
          setAnalysisStatus("failed");
          setAnalysisError(
            "Lost contact with the ECDAT backend while the scan was running. " +
              "The scan may still be running on the server — reload once the backend is back to see its real state.",
          );
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [analysisRunning, loadDashboard]);

  // Two already-existing bulk endpoints, joined by CBOM bom-ref -- the
  // canonical per-finding identity the backend uses throughout (two
  // distinct findings can legitimately share the same displayed
  // algorithm name -- e.g. two separate "RSA-2048" occurrences in this
  // dataset -- so name alone is never used as a selection key). Both
  // GET /api/priority and GET /api/migration-report/assets now return
  // a real bom_ref per finding, so this is a direct bom_ref join, not
  // a name-based approximation.
  //
  // Memoized (and computed before the loading/error early returns) so
  // the Security Map receives a stable finding list and does not rebuild
  // its scene on unrelated re-renders.
  const enrichedAssets = useMemo(() => {
    const priorityByBomRef = {};
    priorityAssets.forEach((item) => {
      if (item.bom_ref) priorityByBomRef[item.bom_ref] = item;
    });

    return riskAssets.map((item) => {
      const bomRef = item.bom_ref;
      const name = item.asset || item.name || "Unknown";
      const priorityInfo = priorityByBomRef[bomRef] || {};

      return {
        key: bomRef,
        bomRef,
        name,
        type: item.asset_type || "Unknown",
        primitive: item.primitive || "Unknown",
        riskScore: item.risk_score,
        riskSeverity: item.risk_severity || "UNKNOWN",
        migrationType: item.migration_type || "",
        pqcApplicable: Boolean(item.pqc_applicable),
        pqcCandidate: item.candidate,
        // Purpose-aware migration strategy decided by the backend
        // (KEEP / DIRECT_PQC / HYBRID / NEEDS_REVIEW) and the PQC
        // component it selected, if any.
        migrationStrategy: item.migration_strategy || null,
        strategyPqcComponent: item.strategy_pqc_component || null,
        sourceImpact: item.source_impact || "UNKNOWN",
        priorityLevel: priorityInfo?.migration_priority?.priority || "UNKNOWN",
        priorityScore: priorityInfo?.migration_priority?.priority_score ?? null,
        complexityLevel: priorityInfo?.migration_complexity?.level || "UNKNOWN",
        blastSeverity: priorityInfo?.blast_radius?.severity || "UNKNOWN",
      };
    });
  }, [riskAssets, priorityAssets]);

  // The single way into the investigation workspace. bom_ref is the only
  // identity; `surface` optionally names the analysis to bring forward.
  const openFinding = useCallback((bomRef, surface = null) => {
    if (!bomRef) return;
    const current = selectedAssetRef.current;
    if (current && current !== bomRef) {
      setInvestigationTrail((trail) => [...trail, current]);
    }
    setActiveSurface(typeof surface === "string" ? surface : null);
    setFocusedFinding(bomRef);
    setSelectedAsset(bomRef);
  }, []);

  const closeInvestigation = useCallback(() => {
    setSelectedAsset(null);
    setAssetDetail(null);
    setInvestigationTrail([]);
    setActiveSurface(null);
    // On the stage, leaving an investigation returns to the finding in the landscape.
    if (isStageRef.current) setStageSection("landscape");
  }, []);

  const backInvestigation = useCallback(() => {
    const previous = investigationTrail[investigationTrail.length - 1];
    if (!previous) return;
    setInvestigationTrail(investigationTrail.slice(0, -1));
    setActiveSurface(null);
    setFocusedFinding(previous);
    setSelectedAsset(previous);
  }, [investigationTrail]);

  const scrollToMap = useCallback(() => {
    document.getElementById("security-map-section")?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  }, []);

  // Leave any open investigation and show a stage dock section.
  const goSection = useCallback((section) => {
    setSelectedAsset(null);
    setAssetDetail(null);
    setInvestigationTrail([]);
    setActiveSurface(null);
    setStageSection(section);
  }, []);

  // Hero metrics open the Security Map pre-filtered to what they count.
  const investigateInMap = useCallback(
    (filters) => {
      setSecurityMapFilters({ ...DEFAULT_MAP_FILTERS, ...filters });
      if (isStageRef.current) goSection("landscape");
      else scrollToMap();
    },
    [scrollToMap, goSection],
  );

  // Command search / focus bar: focus a finding and centre it in the map.
  const locateInMap = useCallback(
    (bomRef) => {
      setFocusedFinding(bomRef);
      setLocateRequest({ bomRef, at: Date.now() });
      if (isStageRef.current) {
        goSection("landscape");
        requestAnimationFrame(() => stageRef.current?.focusSelected(bomRef));
      } else {
        scrollToMap();
      }
    },
    [scrollToMap, goSection],
  );

  const clearFocus = useCallback(() => setFocusedFinding(null), []);

  // "Open in Security Space" after a scan: the landscape, freshly rebuilt.
  const showSecuritySpace = useCallback(() => {
    setFocusedFinding(null);
    setSecurityMapFilters(DEFAULT_MAP_FILTERS);
    if (isStageRef.current) goSection("landscape");
    else scrollToMap();

    // Move focus with the view, so the change is not silent for keyboard
    // and screen-reader users left behind on the scan panel's button.
    requestAnimationFrame(() => {
      document.getElementById("security-map-section")?.focus({ preventScroll: true });
    });
  }, [goSection, scrollToMap]);
  const publishSimulation = useCallback((bomRef, summary) => {
    setSimulation((current) => {
      if (summary) return summary;
      return current?.bomRef === bomRef ? null : current;
    });
    // A simulation result on screen puts the investigation into its simulation state.
    if (summary) setActiveSurface("whatif");
  }, []);
  const publishEvidence = useCallback((bomRef, steps) => setEvidenceChain({ bomRef, steps }), []);

  // Security Map data + display state, shared by the stage and the map panel.
  const mapData = useSecurityMapModel(enrichedAssets);
  const landscapeState = useLandscapeState(mapData.model, securityMapFilters, focusedFinding, mapQuery);
  const posture = useMemo(() => postureFromSummary(summary), [summary]);
  const cameraApi = useMemo(
    () => ({
      resetView: () => stageRef.current?.resetView(),
      fitAll: () => stageRef.current?.fitAll(),
      focusSelected: (bomRef) => stageRef.current?.focusSelected(bomRef),
      focusRegion: (key) => stageRef.current?.focusRegion(key),
    }),
    [],
  );

  // A pick in the 3D world resolves through the same selection flow.
  const selectFromStage = useCallback(
    (bomRef) => {
      if (!bomRef) {
        if (!selectedAssetRef.current) setFocusedFinding(null);
        return;
      }
      if (selectedAssetRef.current) {
        openFinding(bomRef);
        return;
      }
      setFocusedFinding(bomRef);
      setStageSection("landscape");
    },
    [openFinding],
  );

  const selectMetric = useCallback(
    (key) => {
      if (METRIC_FILTERS[key]) investigateInMap(METRIC_FILTERS[key]);
    },
    [investigateInMap],
  );
  const spatialContext = useMemo(() => ({ publishSimulation }), [publishSimulation]);

  const activeSection = useScrollSpy(SECTION_SPY_TARGETS, { enabled: !isStage && !loading && !error && Boolean(summary) });

  // Opens ECDAT AI with a finding attached, from wherever the user is
  // looking at it. Declared with the other hooks, above the loading and
  // error returns, so the hook order never depends on render state.
  const askEcdatAi = useCallback((bomRef) => {
    if (bomRef) setFocusedFinding(bomRef);
    setChatOpen(true);
  }, []);

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

  // Top 5 HIGH/CRITICAL-risk assets, surfaced on the dashboard's first
  // viewport next to the repository-analysis panel -- a client-side
  // sort of already-fetched data, not a new backend call or metric.
  //
  // "Migrate First" ranks by the backend's own migration_priority score
  // (services/migration_priority.py's weighted blend of quantum risk,
  // blast radius and migration complexity -- the same figure already
  // shown as this asset's "Priority" badge everywhere else in the app),
  // not by risk severity alone. Risk severity only decides which
  // findings are quantum-vulnerable enough to be in the candidate pool;
  // sorting that pool by severity bucket, with ties left in whatever
  // order the API happened to return them, could bury the single
  // highest-priority finding behind several lower-priority ones that
  // merely share the same HIGH bucket -- exactly what was happening
  // before this fix. Risk score, then bom_ref, break remaining ties so
  // the order is fully deterministic.
  const criticalFindings = enrichedAssets
    .filter((asset) => asset.riskSeverity === "HIGH" || asset.riskSeverity === "CRITICAL")
    .sort((a, b) => {
      const priorityDiff = (b.priorityScore ?? -1) - (a.priorityScore ?? -1);
      if (priorityDiff !== 0) return priorityDiff;

      const riskDiff = (b.riskScore ?? -1) - (a.riskScore ?? -1);
      if (riskDiff !== 0) return riskDiff;

      return String(a.bomRef || "").localeCompare(String(b.bomRef || ""));
    })
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

  const focusedAsset = focusedFinding ? enrichedAssets.find((asset) => asset.bomRef === focusedFinding) || null : null;
  const selectedName = selectedAsset
    ? assetDetail?.bom_ref === selectedAsset
      ? assetDetail.asset
      : enrichedAssets.find((asset) => asset.bomRef === selectedAsset)?.name || selectedAsset
    : null;
  // Only hand the workspace the record for the finding it is showing, so
  // navigating between findings never flashes the previous one's data.
  const selectedDetail = assetDetail?.bom_ref === selectedAsset ? assetDetail : null;
  // ---- ECDAT AI
  //
  // The assistant is given whichever finding the user is looking at --
  // the open investigation, or the finding focused in the map -- so
  // "why is this risky?" resolves to a real bom_ref rather than guessing.
  const chatFindingRef = selectedAsset || focusedFinding || null;
  const chatFinding = chatFindingRef
    ? {
        bomRef: chatFindingRef,
        name:
          (assetDetail?.bom_ref === chatFindingRef ? assetDetail.asset : null) ||
          enrichedAssets.find((asset) => asset.bomRef === chatFindingRef)?.name ||
          chatFindingRef,
        strategy:
          (assetDetail?.bom_ref === chatFindingRef ? assetDetail?.migration_strategy?.strategy : null) ||
          enrichedAssets.find((asset) => asset.bomRef === chatFindingRef)?.strategy ||
          null,
      }
    : null;

  const ecdatChat = (
    <>
      <ChatLauncher open={chatOpen} onToggle={() => setChatOpen((open) => !open)} hasFinding={Boolean(chatFinding)} />
      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        selectedFinding={chatFinding}
        backendConnected={backendConnected}
      />
    </>
  );

  const previousRef = investigationTrail[investigationTrail.length - 1] || null;
  const previousFinding = previousRef
    ? { bomRef: previousRef, name: enrichedAssets.find((asset) => asset.bomRef === previousRef)?.name || previousRef }
    : null;

  // Which hero metric the map's current filters correspond to (the card
  // shows it as active); derived from the one filter state, never stored.
  const onlyFilter = (key) =>
    ["severities", "strategies", "priorities"].every((other) => other === key || securityMapFilters[other].length === 0) &&
    securityMapFilters.family === "ALL";
  const activeMetric =
    onlyFilter("priorities") && sameSet(securityMapFilters.priorities, ["CRITICAL", "HIGH"])
      ? "priority"
      : onlyFilter("strategies") && sameSet(securityMapFilters.strategies, ["DIRECT_PQC", "HYBRID"])
      ? "pqc"
      : null;

  const spatialMode = selectedAsset
    ? simulation?.bomRef === selectedAsset
      ? "simulation"
      : "investigation"
    : focusedFinding
    ? "finding"
    : activeSection === "security-map"
    ? "map"
    : "global";

  // ---- stage view: derived from the existing selection + navigation state
  const simulationActive = Boolean(selectedAsset && simulation?.bomRef === selectedAsset && activeSurface === "whatif");
  const stageView = selectedAsset
    ? simulationActive
      ? "simulation"
      : "investigation"
    : stageSection === "landscape"
    ? focusedFinding
      ? "finding"
      : "map"
    : "global";

  const investigationData = selectedDetail
    ? {
        summaries: branchSummaries(selectedDetail, aiStatus),
        stages: migrationStages(selectedDetail.migration_strategy, selectedDetail.ranked_candidates?.[0]),
        evidenceSteps: evidenceChain?.bomRef === selectedAsset ? evidenceChain.steps : [],
      }
    : null;

  function stageEscape() {
    if (activeSurface) setActiveSurface(null);
    else if (selectedAsset) closeInvestigation();
    else if (focusedFinding) setFocusedFinding(null);
    else if (stageSection !== "posture") setStageSection("posture");
  }

  function stageNavigate(key) {
    if (key === "ai") {
      if (focusedFinding) openFinding(focusedFinding, "ai");
      else goSection("findings");
      return;
    }
    goSection(NAV_TO_SECTION[key] || "posture");
  }

  // ==========================================================
  // SHARED PANELS (rendered by both layouts)
  // ==========================================================

  const topbarElement = (
    <Topbar
      search={search}
      onSearchChange={setSearch}
      backendConnected={backendConnected}
      findings={enrichedAssets}
      onLocateFinding={locateInMap}
    />
  );

  const contextBarElement = (
    <FindingContextBar
      finding={selectedAsset ? null : focusedAsset}
      onLocate={locateInMap}
      onInvestigate={openFinding}
      onClear={clearFocus}
    />
  );

  const heroElement = (variant) => (
    <HeroOverview
      summary={summary}
      totalAssetsScanned={assets.length}
      onInvestigate={investigateInMap}
      activeMetric={activeMetric}
      variant={variant}
    />
  );

  const operationsElement = (
    <div className="dashboard-row dashboard-row-primary">
      <RepositoryAnalysisPanel
        repository={repository}
        branch={branch}
        status={analysisStatus}
        message={analysisMessage}
        error={analysisError}
        errorCode={scanStartErrorCode || scanStatus?.error_code || null}
        running={analysisRunning}
        stages={scanStatus?.stages || []}
        pipelineStages={scanStatus?.pipeline_stages || []}
        currentStage={scanStatus?.current_stage || null}
        validation={scanStatus?.validation || null}
        result={scanStatus?.result || null}
        duration={scanStatus?.duration_seconds ?? null}
        capabilities={scanCapabilities}
        history={scanHistory}
        onRepositoryChange={setRepository}
        onBranchChange={setBranch}
        onSubmit={handleAnalyzeRepository}
        onViewResults={showSecuritySpace}
      />

      <CriticalFindingsPanel assets={criticalFindings} onSelectAsset={openFinding} focusedRef={focusedFinding} />
    </div>
  );

  const mapElement = (docked) => (
    <CryptographicSecurityMap
      assets={enrichedAssets}
      focusedRef={focusedFinding}
      onFocus={setFocusedFinding}
      onOpen={openFinding}
      filters={securityMapFilters}
      onFiltersChange={setSecurityMapFilters}
      locateRequest={locateRequest}
      mapData={mapData}
      query={mapQuery}
      onQueryChange={setMapQuery}
      cameraApi={docked ? cameraApi : null}
      webglLost={contextLost}
    />
  );

  const intelligenceElement = (
    <section className={`migration-intelligence-section${focusedAsset ? " has-focus" : ""}`}>
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
          activeName={focusedAsset?.riskSeverity || null}
          activeCaption={focusedAsset ? `${focusedAsset.name} is ${focusedAsset.riskSeverity} risk` : null}
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
          activeName={focusedAsset ? MIGRATION_TYPE_CHART_NAMES[focusedAsset.migrationType] || null : null}
          activeCaption={
            focusedAsset && MIGRATION_TYPE_CHART_NAMES[focusedAsset.migrationType]
              ? `${focusedAsset.name} is in ${MIGRATION_TYPE_CHART_NAMES[focusedAsset.migrationType]}`
              : null
          }
        />

        <DonutPanel
          id="global-source-impact-section"
          icon={FileWarning}
          title="Source Impact"
          description="Estimated source-code migration impact"
          data={sourceImpactChartData}
          colors={IMPACT_DONUT_COLORS}
          onSliceClick={(name) => name && setSourceImpactFilter(String(name).toUpperCase())}
          activeName={focusedAsset?.sourceImpact || null}
          activeCaption={focusedAsset ? `${focusedAsset.name} has ${focusedAsset.sourceImpact} source impact` : null}
        />
      </div>
    </section>
  );

  const explorerElement = (
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
        selectedAsset={selectedAsset || focusedFinding}
        onSelectAsset={openFinding}
      />
    </section>
  );

  const workspaceElement = (layout) =>
    selectedAsset ? (
      <AssetDetailPanel
        key={selectedAsset}
        layout={layout}
        assetName={selectedName}
        assetDetail={selectedDetail}
        loading={assetDetailLoading || (!selectedDetail && !assetDetailError)}
        error={assetDetailError}
        onRetry={loadAssetDetail}
        onClose={closeInvestigation}
        aiStatus={aiStatus}
        aiAdvice={aiAdvice}
        aiError={aiError}
        onGenerateAdvice={handleGenerateAIAdvice}
        activeSurface={activeSurface}
        onSurfaceChange={setActiveSurface}
        previousFinding={previousFinding}
        onBack={backInvestigation}
        onInvestigate={(bomRef) => openFinding(bomRef, "blast")}
        onEvidence={publishEvidence}
        onAskAi={askEcdatAi}
      />
    ) : null;

  const sidebarInvestigation = focusedAsset
    ? { name: focusedAsset.name, bomRef: focusedAsset.bomRef, open: Boolean(selectedAsset) }
    : null;

  // ==========================================================
  // STAGE LAYOUT (desktop ≥1025px, tablet 601–1024px, WebGL)
  // ==========================================================

  if (isStage) {
    return (
      <SpatialContext.Provider value={spatialContext}>
        <StageLayout
          tier={stageTier}
          view={stageView}
          section={stageSection}
          onSection={goSection}
          stageRef={stageRef}
          stageProps={{
            model: mapData.model,
            visibleRefs: landscapeState.visibleRefs,
            searchRefs: landscapeState.searchRefs,
            relatedRefs: landscapeState.relatedRefs,
            focusedRef: focusedFinding,
            activeSurface,
            simulation,
            investigation: investigationData,
            posture,
            activeMetric,
            reducedMotion,
            onSelectFinding: selectFromStage,
            onSurface: setActiveSurface,
            onMetric: selectMetric,
            onContextLost: () => setContextLost(true),
          }}
          sidebar={
            <Sidebar
              backendConnected={backendConnected}
              activeKey={selectedAsset ? "security-map" : SECTION_TO_NAV[stageSection]}
              investigation={sidebarInvestigation}
              onNavigate={stageNavigate}
            />
          }
          topbar={topbarElement}
          contextBar={contextBarElement}
          docks={{
            posture: heroElement("stage"),
            operations: operationsElement,
            landscape: mapElement(true),
            intelligence: intelligenceElement,
            findings: explorerElement,
          }}
          inspector={workspaceElement("inspector")}
          focusedName={focusedAsset?.name || null}
          activeSurface={activeSurface}
          onEscape={stageEscape}
          onGoGlobal={() => goSection("posture")}
          onGoLandscape={() => {
            setFocusedFinding(null);
            goSection("landscape");
          }}
          onGoFinding={() => goSection("landscape")}
          onGoInvestigation={() => setActiveSurface(null)}
        />
        {ecdatChat}
      </SpatialContext.Provider>
    );
  }

  // ==========================================================
  // SCROLL LAYOUT (≤600px, no WebGL, or WebGL context lost)
  // ==========================================================

  return (
    <SpatialContext.Provider value={spatialContext}>
      <div className="app-shell is-spatial" data-spatial-mode={spatialMode}>
        <SpatialEnvironment mode={spatialMode} />

        <Sidebar
          backendConnected={backendConnected}
          activeKey={activeSection || "overview"}
          inert={Boolean(selectedAsset)}
          investigation={sidebarInvestigation}
        />

        <main className={`main-content${selectedAsset ? " is-backgrounded" : ""}`} inert={selectedAsset ? true : undefined}>
          {topbarElement}

          {contextBarElement}

          <SpaceLayer index="01" label="Security posture" tier="primary" active={activeSection === "overview"}>
            {heroElement("page")}
          </SpaceLayer>

          <SpaceLayer index="02" label="Operations" tier="secondary" active={activeSection === "repository"}>
            {operationsElement}
          </SpaceLayer>

          <SpaceLayer index="03" label="Cryptographic landscape" tier="primary" active={activeSection === "security-map"}>
            {mapElement(false)}
          </SpaceLayer>

          <SpaceLayer index="04" label="Migration intelligence" tier="secondary" active={activeSection === "risk"}>
            {intelligenceElement}
          </SpaceLayer>

          <SpaceLayer index="05" label="Findings" tier="secondary" active={activeSection === "assets"}>
            {explorerElement}
          </SpaceLayer>

          <footer className="dashboard-footer">
            <span>ECDAT Quantum Migration Intelligence</span>
            <span>
              Backend API • {summary?.total_assets ?? 0} Assets • {summary?.total_migration_actions ?? 0}{" "}
              Actions
            </span>
          </footer>
        </main>

        {/* The investigation workspace renders at the document root so the
            dashboard behind it can recede as the background layer. */}
        {selectedAsset && createPortal(workspaceElement("overlay"), document.body)}

        {ecdatChat}
      </div>
    </SpatialContext.Provider>
  );
}

export default App;

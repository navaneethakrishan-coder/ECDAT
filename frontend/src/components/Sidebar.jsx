import {
  ArrowUpRight,
  Database,
  FileWarning,
  Gauge,
  LayoutGrid,
  Network,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

import { scrollBehavior } from "../spatial/motion";

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
}

function scrollToSelector(selector) {
  document.querySelector(selector)?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
}

// The AI Advisor only exists in the DOM once an asset is selected
// (it lives inside the asset-detail workspace, not as a standalone
// page section) -- so this scrolls to it if it's open, or otherwise
// to the Asset Explorer as the honest next step ("pick an asset to
// reach the AI Advisor") rather than silently doing nothing.
function scrollToAIAdvisor() {
  const panel = document.querySelector(".panel-ai");

  if (panel) {
    panel.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  } else {
    scrollToSelector(".asset-explorer");
  }
}

const NAV_ITEMS = [
  { key: "overview", label: "Overview", icon: Gauge, action: () => window.scrollTo({ top: 0, behavior: scrollBehavior() }) },
  { key: "repository", label: "Repository Analysis", icon: Radar, action: () => scrollToSelector(".repository-analysis-panel") },
  { key: "security-map", label: "Security Map", icon: Network, action: () => scrollToId("security-map-section") },
  { key: "assets", label: "Cryptographic Assets", icon: Database, action: () => scrollToSelector(".asset-explorer") },
  { key: "risk", label: "Risk Analysis", icon: ShieldAlert, action: () => scrollToId("risk-analysis-section") },
  { key: "pqc", label: "PQC Migration", icon: Zap, action: () => scrollToId("pqc-migration-section") },
  { key: "actions", label: "Migration Actions", icon: ArrowUpRight, action: () => scrollToSelector(".migration-intelligence-section") },
  { key: "impact", label: "Source Impact", icon: FileWarning, action: () => scrollToId("global-source-impact-section") },
  { key: "ai", label: "AI Advisor", icon: Sparkles, action: scrollToAIAdvisor },
  { key: "reports", label: "Reports", icon: LayoutGrid, action: () => scrollToSelector(".dashboard-footer") },
];

/**
 * Spatial navigation rail. The active item follows the section being
 * read (scroll spy in App.jsx) and a single illuminated indicator slides
 * between items instead of each item lighting up independently.
 */
export function Sidebar({ backendConnected, activeKey = "overview", investigation = null, inert = false, onNavigate = null }) {
  const activeIndex = Math.max(
    NAV_ITEMS.findIndex((item) => item.key === activeKey),
    0,
  );

  return (
    <aside className="sidebar" inert={inert || undefined}>
      <div className="brand">
        <div className="brand-mark">
          <ShieldCheck size={24} />
        </div>

        <div>
          <div className="brand-name">ECDAT</div>
          <div className="brand-subtitle">PQC Migration Intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">Workspace</div>

        <div className="nav-rail" style={{ "--active-index": activeIndex }}>
          <span className="nav-rail-indicator" aria-hidden="true" />
          {NAV_ITEMS.map((item, index) => (
            <button
              type="button"
              key={item.key}
              className={`nav-item${index === activeIndex ? " active" : ""}`}
              onClick={onNavigate ? () => onNavigate(item.key) : item.action}
              aria-current={index === activeIndex ? "location" : undefined}
              title={item.label}
            >
              <item.icon size={18} />
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      {investigation && (
        <div className="sidebar-investigation" role="status">
          <span className="sidebar-investigation-beacon" aria-hidden="true" />
          <div>
            <span>{investigation.open ? "Investigating" : "Focused"}</span>
            <strong title={investigation.bomRef}>{investigation.name}</strong>
          </div>
        </div>
      )}

      <div className="sidebar-footer">
        <div className={`connection-dot${backendConnected ? "" : " connection-dot-down"}`} />
        <div>
          <div className="connection-title">
            {backendConnected ? "Backend Connected" : "Backend Unreachable"}
          </div>
          <div className="connection-url">127.0.0.1:8000</div>
        </div>
      </div>
    </aside>
  );
}

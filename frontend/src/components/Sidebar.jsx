import {
  ArrowUpRight,
  Database,
  FileWarning,
  Gauge,
  LayoutGrid,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToSelector(selector) {
  document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// The AI Advisor only exists in the DOM once an asset is selected
// (it lives inside the asset-detail workspace, not as a standalone
// page section) -- so this scrolls to it if it's open, or otherwise
// to the Asset Explorer as the honest next step ("pick an asset to
// reach the AI Advisor") rather than silently doing nothing.
function scrollToAIAdvisor() {
  const panel = document.querySelector(".panel-ai");

  if (panel) {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    scrollToSelector(".asset-explorer");
  }
}

const NAV_ITEMS = [
  { key: "overview", label: "Overview", icon: Gauge, action: () => window.scrollTo({ top: 0, behavior: "smooth" }) },
  { key: "repository", label: "Repository Analysis", icon: Radar, action: () => scrollToSelector(".repository-analysis-panel") },
  { key: "assets", label: "Cryptographic Assets", icon: Database, action: () => scrollToSelector(".asset-explorer") },
  { key: "risk", label: "Risk Analysis", icon: ShieldAlert, action: () => scrollToId("risk-analysis-section") },
  { key: "pqc", label: "PQC Migration", icon: Zap, action: () => scrollToId("pqc-migration-section") },
  { key: "actions", label: "Migration Actions", icon: ArrowUpRight, action: () => scrollToSelector(".migration-intelligence-section") },
  { key: "impact", label: "Source Impact", icon: FileWarning, action: () => scrollToId("global-source-impact-section") },
  { key: "ai", label: "AI Advisor", icon: Sparkles, action: scrollToAIAdvisor },
  { key: "reports", label: "Reports", icon: LayoutGrid, action: () => scrollToSelector(".dashboard-footer") },
];

export function Sidebar({ backendConnected }) {
  return (
    <aside className="sidebar">
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

        {NAV_ITEMS.map((item, index) => (
          <button
            type="button"
            key={item.key}
            className={`nav-item${index === 0 ? " active" : ""}`}
            onClick={item.action}
          >
            <item.icon size={18} />
            {item.label}
          </button>
        ))}
      </nav>

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

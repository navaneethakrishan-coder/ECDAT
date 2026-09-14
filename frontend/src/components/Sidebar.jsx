import {
  ArrowUpRight,
  Database,
  FileWarning,
  Gauge,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToSelector(selector) {
  document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: Gauge, action: () => window.scrollTo({ top: 0, behavior: "smooth" }) },
  { key: "assets", label: "Assets", icon: Database, action: () => scrollToSelector(".asset-explorer") },
  { key: "risk", label: "Risk Analysis", icon: ShieldAlert, action: () => scrollToId("risk-analysis-section") },
  { key: "pqc", label: "PQC Migration", icon: Zap, action: () => scrollToId("pqc-migration-section") },
  { key: "actions", label: "Migration Actions", icon: ArrowUpRight, action: () => scrollToSelector(".stats-grid") },
  { key: "impact", label: "Source Impact", icon: FileWarning, action: () => scrollToId("global-source-impact-section") },
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
        <div className="nav-section">Overview</div>

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

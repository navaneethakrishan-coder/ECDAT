import { useEffect, useRef } from "react";
import { Cpu, Search } from "lucide-react";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");

/**
 * A slim command console bar above the hero -- gives the dashboard a
 * "security console" top edge instead of the page just starting with
 * the hero. Wired to the SAME `search` state AssetFilters already
 * uses (lifted no higher than it already was, in App.jsx), so typing
 * here filters the Asset Explorer exactly like typing there does --
 * no new backend call, no second source of truth.
 *
 * The AI chip is intentionally a static description of the configured
 * model ("Qwen3:14B via Ollama"), not a live status claim -- Ollama
 * exposes no health-check endpoint this app calls (see
 * AIAdvisorPanel's own availability indicator, which is honest about
 * the same limitation), so a global "AI: Online" pill here would be
 * fabricated. The backend dot IS a live claim, because it's backed by
 * the real 15s GET /health poll already running in App.jsx.
 */
export function Topbar({ search, onSearchChange, backendConnected }) {
  const inputRef = useRef(null);

  useEffect(() => {
    function handleKeyDown(event) {
      const isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";

      const target = event.target;
      const isTyping =
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);

      const isSlash = event.key === "/" && !isTyping;

      if (isShortcut || isSlash) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="topbar" role="search">
      <div className="topbar-search">
        <Search size={15} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search cryptographic assets, algorithms, primitives..."
          aria-label="Search cryptographic assets, algorithms, primitives"
        />
        <kbd className="topbar-shortcut">{isMac ? "⌘" : "Ctrl"} K</kbd>
      </div>

      <div className="topbar-status">
        <div className="topbar-status-chip topbar-status-ai">
          <Cpu size={12} aria-hidden="true" />
          Qwen3:14B · Ollama
        </div>

        <div className="topbar-status-chip topbar-status-backend">
          <span className={`connection-dot${backendConnected ? "" : " connection-dot-down"}`} />
          {backendConnected ? "Backend Online" : "Backend Unreachable"}
        </div>
      </div>
    </div>
  );
}

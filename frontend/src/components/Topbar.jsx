import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Cpu, Search } from "lucide-react";

import { SeverityBadge } from "./Badge";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");

/**
 * A slim command console bar above the hero -- gives the dashboard a
 * "security console" top edge instead of the page just starting with
 * the hero. Wired to the SAME `search` state AssetFilters already
 * uses (lifted no higher than it already was, in App.jsx), so typing
 * here filters the Asset Explorer exactly like typing there does --
 * no new backend call, no second source of truth.
 *
 * Command search: while typing, the real findings that match (name,
 * bom_ref, type, primitive) are listed; choosing one focuses that
 * finding by bom_ref and locates it in the Security Map.
 *
 * The AI chip is intentionally a static description of the configured
 * model ("Qwen3:14B via Ollama"), not a live status claim -- Ollama
 * exposes no health-check endpoint this app calls (see
 * AIAdvisorPanel's own availability indicator, which is honest about
 * the same limitation), so a global "AI: Online" pill here would be
 * fabricated. The backend dot IS a live claim, because it's backed by
 * the real 15s GET /health poll already running in App.jsx.
 */
export function Topbar({ search, onSearchChange, backendConnected, findings = [], onLocateFinding }) {
  const inputRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

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

  const matches = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query || !onLocateFinding) return [];
    return findings
      .filter((finding) =>
        [finding.name, finding.bomRef, finding.type, finding.primitive].some((field) =>
          String(field || "").toLowerCase().includes(query),
        ),
      )
      .slice(0, 6);
  }, [findings, search, onLocateFinding]);

  function locate(finding) {
    setOpen(false);
    setActiveIndex(-1);
    onLocateFinding(finding.bomRef);
  }

  function handleInputKeyDown(event) {
    if (!matches.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) => Math.min(index + 1, matches.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, -1));
    } else if (event.key === "Enter" && open && activeIndex >= 0) {
      event.preventDefault();
      locate(matches[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  const showResults = open && matches.length > 0;

  return (
    <div className="topbar" role="search">
      <div className="topbar-search">
        <Search size={15} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          id="topbar-command-search"
          name="topbar-command-search"
          value={search}
          onChange={(event) => {
            onSearchChange(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={handleInputKeyDown}
          placeholder="Search cryptographic assets, algorithms, primitives..."
          aria-label="Search cryptographic assets, algorithms, primitives"
          role="combobox"
          aria-expanded={showResults}
          aria-controls="topbar-command-results"
          aria-autocomplete="list"
        />
        <kbd className="topbar-shortcut">{isMac ? "⌘" : "Ctrl"} K</kbd>

        {showResults && (
          <ul id="topbar-command-results" className="command-results" role="listbox" aria-label="Locate a finding">
            <li className="command-results-head" role="presentation">
              Locate finding · the explorer below is filtered too
            </li>
            {matches.map((finding, index) => (
              <li key={finding.bomRef} role="option" aria-selected={index === activeIndex}>
                <button
                  type="button"
                  className={index === activeIndex ? "is-active" : undefined}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => locate(finding)}
                >
                  <Crosshair size={13} aria-hidden="true" />
                  <span className="command-result-name">{finding.name}</span>
                  <code>{finding.bomRef.slice(0, 8)}…</code>
                  <SeverityBadge value={finding.riskSeverity} />
                </button>
              </li>
            ))}
          </ul>
        )}
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

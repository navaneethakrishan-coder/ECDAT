import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Crosshair,
  Layers,
  Maximize2,
  Minimize2,
  Network,
  RotateCcw,
  Scan,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { SeverityBadge } from "../Badge";
import { isWebGLAvailable, usePrefersReducedMotion } from "./mapEnvironment";
import { SecurityMap2D } from "./SecurityMap2D";
import { SecurityMapFocusPanel } from "./SecurityMapFocusPanel";
import { SecurityMapLegend, StrategyGlyph } from "./SecurityMapLegend";
import {
  DEFAULT_FILTERS,
  SEVERITIES,
  STRATEGIES,
  STRATEGY_META,
  displayName,
  matchesSearch,
  shortRef,
  summarize,
} from "./securityMapModel";
import "./SecurityMap.css";
import { useLandscapeState, useSecurityMapModel } from "./useSecurityMapModel";

const SecurityMap3D = lazy(() => import("./SecurityMap3D"));

const PRIORITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const EMPTY_ASSETS = [];

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function byPriority(a, b) {
  return (
    (b.priorityScore ?? -1) - (a.priorityScore ?? -1) ||
    (b.riskScore ?? -1) - (a.riskScore ?? -1) ||
    a.bomRef.localeCompare(b.bomRef)
  );
}

function FilterChip({ active, onClick, children, label }) {
  return (
    <button type="button" className={`map-chip${active ? " is-active" : ""}`} aria-pressed={active} onClick={onClick} aria-label={label}>
      {children}
    </button>
  );
}

/**
 * Cryptographic Security Map: every real ECDAT finding as a node, placed
 * by cryptographic role / risk / migration priority, shaped by migration
 * strategy, connected by recorded CBOM dependency edges.
 *
 * Selection is not a second system: `focusedRef` / `onFocus` are App's
 * focused bom_ref (shared with the Asset Explorer cards), and
 * `onOpen(bom_ref)` opens App's existing investigation workspace.
 */
export function CryptographicSecurityMap({
  assets,
  focusedRef,
  onFocus,
  onOpen,
  filters,
  onFiltersChange,
  locateRequest = null,
  mapData = null,
  query: controlledQuery,
  onQueryChange,
  cameraApi = null,
  webglLost = false,
}) {
  // Dock mode: rendered as a panel of the shared SpatialStage. There is no
  // canvas here -- the stage draws the landscape, and camera controls drive
  // the stage's camera through `cameraApi`.
  const dock = Boolean(cameraApi);
  const reducedMotion = usePrefersReducedMotion();
  const [webglAvailable] = useState(() => isWebGLAvailable());
  const [contextLost, setContextLost] = useState(false);
  // Phones start on the 2D map (readable at a narrow width); 3D stays one tap away.
  const [preferredView, setPreferredView] = useState(() =>
    isWebGLAvailable() && (typeof window === "undefined" || window.matchMedia("(min-width: 600px)").matches) ? "3d" : "2d",
  );
  const [expanded, setExpanded] = useState(false);
  const [legendOpen, setLegendOpen] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia("(min-width: 1600px)").matches,
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [localQuery, setLocalQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const sectionRef = useRef(null);
  const mapRef = useRef(null);

  // WebGL lost anywhere in the app (e.g. the shared stage) keeps this map on 2D.
  const activeView = webglAvailable && !contextLost && !webglLost ? preferredView : "2d";

  // ---- data: shared with the 3D stage when App provides it
  const ownData = useSecurityMapModel(mapData ? EMPTY_ASSETS : assets);
  const { model, loading, error: dataError } = mapData || ownData;
  const query = controlledQuery ?? localQuery;
  const setQuery = onQueryChange ?? setLocalQuery;
  const { visibleRefs, searchRefs, focusedNode, relatedRefs } = useLandscapeState(model, filters, focusedRef, query);

  const stats = useMemo(() => (model ? summarize(model.nodes, model.edges) : null), [model]);
  const families = useMemo(
    () => [...new Set((model?.nodes || []).map((node) => node.family).filter(Boolean))].sort(),
    [model],
  );

  const searchResults = useMemo(() => {
    if (!model || !query.trim()) return [];
    return model.nodes.filter((node) => matchesSearch(node, query)).sort(byPriority).slice(0, 7);
  }, [model, query]);

  const listNodes = useMemo(() => {
    if (!model) return [];
    return model.nodes
      .filter((node) => visibleRefs.has(node.bomRef) && (!searchRefs || searchRefs.has(node.bomRef)))
      .sort(byPriority);
  }, [model, visibleRefs, searchRefs]);

  const camera = useMemo(
    () => ({
      focusNode: (bomRef) => (cameraApi ? cameraApi.focusSelected(bomRef) : mapRef.current?.focusNode(bomRef)),
      fitAll: () => (cameraApi ? cameraApi.fitAll() : mapRef.current?.fitAll()),
      resetView: () => (cameraApi ? cameraApi.resetView() : mapRef.current?.resetView()),
      focusRegion: (key) => (cameraApi ? cameraApi.focusRegion(key) : mapRef.current?.focusRegion(key)),
    }),
    [cameraApi],
  );

  // ---- focus (App-owned bom_ref) + camera follow-up
  const focusFinding = useCallback(
    (bomRef, { moveCamera = true } = {}) => {
      // A new focus moves the camera through the effect below; re-choosing
      // the finding already in focus re-centres it directly.
      if (bomRef && moveCamera && bomRef === focusedRef) camera.focusNode(bomRef);
      onFocus(bomRef || null);
    },
    [camera, focusedRef, onFocus],
  );

  // The map follows the workspace: whichever surface changes the focused
  // bom_ref (map, search, Asset Explorer, Migrate First, command search),
  // the camera centres that finding and its recorded relationships.
  useEffect(() => {
    if (!dock && focusedRef && relatedRefs) mapRef.current?.focusNode(focusedRef);
  }, [dock, focusedRef, relatedRefs, model]);

  // Explicit "locate" requests (e.g. the focus bar) re-centre even when
  // the focused finding has not changed.
  useEffect(() => {
    if (locateRequest?.bomRef) mapRef.current?.focusNode(locateRequest.bomRef);
  }, [locateRequest]);


  const handleSceneSelect = useCallback((bomRef) => focusFinding(bomRef), [focusFinding]);
  const handleContextLost = useCallback(() => setContextLost(true), []);

  function selectSearchResult(node) {
    if (!node) return;
    setSearchOpen(false);
    // The chosen finding now drives the highlight (it and its recorded
    // relationships), so the search dimming is cleared.
    setQuery("");
    focusFinding(node.bomRef);
  }

  function handleSearchKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSearchOpen(true);
      setActiveIndex((index) => Math.min(index + 1, Math.max(searchResults.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectSearchResult(searchResults[activeIndex] || searchResults[0]);
    } else if (event.key === "Escape") {
      event.stopPropagation();
      setSearchOpen(false);
    }
  }

  function setFilterList(key, value) {
    onFiltersChange({ ...filters, [key]: toggleValue(filters[key], value) });
  }

  const filtersActive =
    filters.severities.length + filters.strategies.length + filters.priorities.length > 0 || filters.family !== "ALL";

  function explore() {
    const next = !expanded;
    setExpanded(next);
    if (next) {
      sectionRef.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    }
    window.setTimeout(() => mapRef.current?.fitAll(), 320);
  }

  const summaryText = stats
    ? `${stats.total} cryptographic findings: ${stats.severity.CRITICAL} critical, ${stats.severity.HIGH} high, ${stats.severity.MEDIUM} medium and ${stats.severity.LOW} low risk. Strategies: ${stats.strategy.DIRECT_PQC} direct PQC, ${stats.strategy.HYBRID} hybrid, ${stats.strategy.KEEP} keep, ${stats.strategy.NEEDS_REVIEW} need review. ${stats.edges} recorded dependency relationships.`
    : "";

  return (
    <section
      id="security-map-section"
      ref={sectionRef}
      className={`panel security-map-panel${expanded ? " is-expanded" : ""}${dock ? " is-dock" : ""}`}
      aria-labelledby="security-map-heading"
      // Not in the tab order, but focusable programmatically: opening the
      // security space after a scan moves focus here, so keyboard and
      // screen-reader users land on the view that just changed.
      tabIndex={-1}
    >
      <header className="security-map-header">
        <div className="section-heading">
          <span className="section-eyebrow">Cryptographic Security Map</span>
          <h2 id="security-map-heading">Attack surface &amp; migration landscape</h2>
          <p>
            Every finding by cryptographic role, risk and migration priority — shaped by migration strategy, linked by
            recorded dependencies.
          </p>
        </div>

        {!dock && (
        <div className="security-map-header-actions">
          <div className="map-segmented" role="group" aria-label="Map view">
            <button
              type="button"
              className={activeView === "3d" ? "is-active" : ""}
              aria-pressed={activeView === "3d"}
              disabled={!webglAvailable || contextLost || webglLost}
              onClick={() => setPreferredView("3d")}
            >
              <Box size={14} aria-hidden="true" /> 3D
            </button>
            <button
              type="button"
              className={activeView === "2d" ? "is-active" : ""}
              aria-pressed={activeView === "2d"}
              onClick={() => setPreferredView("2d")}
            >
              <Network size={14} aria-hidden="true" /> 2D
            </button>
          </div>
          <button type="button" className="btn btn-primary btn-sm security-map-explore" onClick={explore} aria-expanded={expanded}>
            {expanded ? <Minimize2 size={14} aria-hidden="true" /> : <Maximize2 size={14} aria-hidden="true" />}
            {expanded ? "Compact view" : "Explore Security Map"}
          </button>
        </div>
        )}
      </header>

      {stats && (
        <div className="security-map-stats" aria-live="polite">
          <span>
            <strong>{visibleRefs.size}</strong> of {stats.total} findings shown
          </span>
          <span className="map-stat-sev map-stat-critical">{stats.severity.CRITICAL} critical</span>
          <span className="map-stat-sev map-stat-high">{stats.severity.HIGH} high</span>
          <span>{stats.strategy.NEEDS_REVIEW} need review</span>
          <span>{stats.strategy.DIRECT_PQC + stats.strategy.HYBRID} selected PQC paths</span>
          <span>{stats.edges} dependency links</span>
        </div>
      )}

      <div className="security-map-toolbar">
        <div className="map-search" role="combobox" aria-expanded={searchOpen && searchResults.length > 0} aria-haspopup="listbox" aria-owns="security-map-search-results">
          <Search size={14} aria-hidden="true" />
          <input
            type="search"
            id="security-map-search"
            name="security-map-search"
            value={query}
            placeholder="Search algorithm, bom_ref, family, source file…"
            aria-label="Search findings in the security map"
            aria-autocomplete="list"
            aria-controls="security-map-search-results"
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveIndex(0);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            onBlur={() => window.setTimeout(() => setSearchOpen(false), 150)}
            onKeyDown={handleSearchKeyDown}
          />
          {query && (
            <button type="button" className="map-icon-button" aria-label="Clear search" onClick={() => setQuery("")}>
              <X size={13} />
            </button>
          )}
          {searchOpen && query.trim() && (
            <ul id="security-map-search-results" className="map-search-results" role="listbox">
              {searchResults.length === 0 && <li className="map-search-empty">No matching findings</li>}
              {searchResults.map((node, index) => (
                <li key={node.bomRef} role="option" aria-selected={index === activeIndex}>
                  <button
                    type="button"
                    className={index === activeIndex ? "is-active" : ""}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectSearchResult(node)}
                  >
                    <StrategyGlyph strategy={node.strategy} size={16} />
                    <span className="map-result-name">{displayName(node)}</span>
                    <code>{shortRef(node.bomRef)}</code>
                    <SeverityBadge value={node.riskSeverity} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          type="button"
          className="btn btn-outline btn-sm map-filters-toggle"
          aria-expanded={filtersOpen}
          aria-controls="security-map-filters"
          onClick={() => setFiltersOpen((open) => !open)}
        >
          <SlidersHorizontal size={14} aria-hidden="true" />
          Filters{filtersActive ? " · on" : ""}
        </button>

        <div id="security-map-filters" className={`map-filters${filtersOpen ? " is-open" : ""}`}>
          <div className="map-filter-group" role="group" aria-label="Risk severity">
            <span>Severity</span>
            {SEVERITIES.map((severity) => (
              <FilterChip
                key={severity}
                active={filters.severities.includes(severity)}
                onClick={() => setFilterList("severities", severity)}
                label={`Risk severity ${severity}`}
              >
                <i className={`map-dot map-dot-${severity.toLowerCase()}`} aria-hidden="true" />
                {severity}
              </FilterChip>
            ))}
          </div>

          <div className="map-filter-group" role="group" aria-label="Migration strategy">
            <span>Strategy</span>
            {STRATEGIES.map((strategy) => (
              <FilterChip
                key={strategy}
                active={filters.strategies.includes(strategy)}
                onClick={() => setFilterList("strategies", strategy)}
                label={`Strategy ${STRATEGY_META[strategy].label}`}
              >
                <StrategyGlyph strategy={strategy} size={14} />
                {STRATEGY_META[strategy].label}
              </FilterChip>
            ))}
          </div>

          <div className="map-filter-group" role="group" aria-label="Migration priority">
            <span>Priority</span>
            {PRIORITY_LEVELS.map((level) => (
              <FilterChip
                key={level}
                active={filters.priorities.includes(level)}
                onClick={() => setFilterList("priorities", level)}
                label={`Migration priority ${level}`}
              >
                {level}
              </FilterChip>
            ))}
          </div>

          <div className="map-filter-group">
            <label htmlFor="security-map-family">Family</label>
            <select
              id="security-map-family"
              name="security-map-family"
              value={filters.family}
              onChange={(event) => onFiltersChange({ ...filters, family: event.target.value })}
            >
              <option value="ALL">All families</option>
              {families.map((family) => (
                <option key={family} value={family}>
                  {family}
                </option>
              ))}
            </select>
            {filtersActive && (
              <button type="button" className="map-reset-filters" onClick={() => onFiltersChange(DEFAULT_FILTERS)}>
                Reset filters
              </button>
            )}
          </div>
        </div>
      </div>

      {(!webglAvailable || contextLost) && (
        <p className="security-map-fallback-note" role="status">
          3D rendering isn’t available here, so the same findings, risk, dependencies and filters are shown as a 2D map.
        </p>
      )}

      <div className="security-map-body">
        {dock ? (
          <div className="security-map-dock-camera">
            {loading && <span className="security-map-dock-status" role="status">Loading security map…</span>}
            {!loading && dataError && (
              <span className="security-map-dock-status" role="alert">
                Security map data could not be loaded: {dataError}
              </span>
            )}
          </div>
        ) : (
        <div className={`security-map-stage view-${activeView}`}>
          {loading && (
            <div className="security-map-state" role="status">
              <div className="loading-spinner" />
              <span>Loading security map…</span>
            </div>
          )}

          {!loading && dataError && (
            <div className="security-map-state" role="alert">
              <span>Security map data could not be loaded: {dataError}</span>
            </div>
          )}

          {model && !dataError && activeView === "3d" && (
            <Suspense
              fallback={
                <div className="security-map-state" role="status">
                  <div className="loading-spinner" />
                  <span>Preparing 3D scene…</span>
                </div>
              }
            >
              <SecurityMap3D
                ref={mapRef}
                model={model}
                visibleRefs={visibleRefs}
                searchRefs={searchRefs}
                focusedRef={focusedNode ? focusedRef : null}
                relatedRefs={relatedRefs}
                reducedMotion={reducedMotion}
                onSelect={handleSceneSelect}
                onContextLost={handleContextLost}
              />
            </Suspense>
          )}

          {model && !dataError && activeView === "2d" && (
            <SecurityMap2D
              model={model}
              visibleRefs={visibleRefs}
              searchRefs={searchRefs}
              focusedRef={focusedNode ? focusedRef : null}
              relatedRefs={relatedRefs}
              onSelect={(bomRef) => focusFinding(bomRef, { moveCamera: false })}
            />
          )}

          {model && visibleRefs.size === 0 && (
            <div className="security-map-empty" role="status">
              No findings match the current filters.
            </div>
          )}

          {model && activeView === "3d" && (
            <div className="security-map-camera" role="group" aria-label="Map camera controls">
              <button type="button" className="map-icon-button" onClick={() => camera.resetView()} aria-label="Reset view">
                <RotateCcw size={14} /> <span>Reset</span>
              </button>
              <button type="button" className="map-icon-button" onClick={() => camera.fitAll()} aria-label="Fit all findings">
                <Scan size={14} /> <span>Fit all</span>
              </button>
              <button
                type="button"
                className="map-icon-button"
                onClick={() => focusedNode && mapRef.current?.focusNode(focusedNode.bomRef)}
                disabled={!focusedNode}
                aria-label="Focus selected finding"
              >
                <Crosshair size={14} /> <span>Focus selected</span>
              </button>
              <label className="map-region-select">
                <Layers size={14} aria-hidden="true" />
                <span className="sr-only">Focus a cryptographic role region</span>
                <select
                  name="security-map-region"
                  value=""
                  onChange={(event) => {
                    if (event.target.value) mapRef.current?.focusRegion(event.target.value);
                  }}
                >
                  <option value="">Focus region…</option>
                  {model.regions.map((region) => (
                    <option key={region.key} value={region.key}>
                      {region.label} ({region.count})
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {model && <SecurityMapLegend open={legendOpen} onToggle={() => setLegendOpen((open) => !open)} is3d={activeView === "3d"} />}
        </div>
        )}
        <aside className="security-map-side" aria-label="Security map details">
          {focusedNode ? (
            <SecurityMapFocusPanel
              node={focusedNode}
              model={model}
              hiddenByFilters={!visibleRefs.has(focusedNode.bomRef)}
              onOpen={onOpen}
              onFocusRef={(bomRef) => focusFinding(bomRef)}
              onCenter={dock || activeView === "3d" ? (bomRef) => camera.focusNode(bomRef) : null}
              onClear={() => onFocus(null)}
            />
          ) : (
            <div className="map-findings">
              <div className="map-findings-head">
                <span>Findings by migration priority</span>
                <small>Select one to investigate</small>
              </div>
              {model ? (
                <ul>
                  {listNodes.map((node) => (
                    <li key={node.bomRef}>
                      <button type="button" onClick={() => focusFinding(node.bomRef)} data-bom-ref={node.bomRef}>
                        <StrategyGlyph strategy={node.strategy} size={16} />
                        <span className="map-finding-name">
                          {displayName(node)}
                          <code>{shortRef(node.bomRef)}</code>
                        </span>
                        <span className="map-finding-meta">
                          <SeverityBadge value={node.riskSeverity} />
                          <small>P {typeof node.priorityScore === "number" ? node.priorityScore.toFixed(0) : "—"}</small>
                        </span>
                      </button>
                    </li>
                  ))}
                  {listNodes.length === 0 && <li className="map-search-empty">No findings match.</li>}
                </ul>
              ) : (
                <p className="map-search-empty">Loading findings…</p>
              )}
            </div>
          )}
        </aside>
      </div>

      <p className="sr-only" aria-live="polite">
        {summaryText}
      </p>
    </section>
  );
}

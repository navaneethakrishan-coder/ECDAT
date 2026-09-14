export function AssetFilters({
  search,
  onSearchChange,
  riskFilter,
  onRiskFilterChange,
  migrationFilter,
  onMigrationFilterChange,
  pqcFilter,
  onPqcFilterChange,
  sourceImpactFilter,
  onSourceImpactFilterChange,
}) {
  return (
    <div className="asset-toolbar">
      <div className="asset-search">
        <span className="search-icon" aria-hidden="true">
          🔎
        </span>

        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search assets, types or primitives..."
          aria-label="Search assets, types or primitives"
        />

        {search && (
          <button
            type="button"
            className="clear-search"
            onClick={() => onSearchChange("")}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      <div className="asset-filters">
        <select
          value={riskFilter}
          onChange={(event) => onRiskFilterChange(event.target.value)}
          className="asset-filter"
          aria-label="Filter by risk level"
        >
          <option value="ALL">All Risk Levels</option>
          <option value="CRITICAL">Critical Risk</option>
          <option value="HIGH">High Risk</option>
          <option value="MEDIUM">Medium Risk</option>
          <option value="LOW">Low Risk</option>
        </select>

        <select
          value={migrationFilter}
          onChange={(event) => onMigrationFilterChange(event.target.value)}
          className="asset-filter"
          aria-label="Filter by migration type"
        >
          <option value="ALL">All Migration Types</option>
          <option value="pqc-candidate">PQC Candidate</option>
          <option value="architectural-migration">Architectural Migration</option>
          <option value="no-direct-pqc-replacement">No Direct PQC Replacement</option>
        </select>

        <select
          value={pqcFilter}
          onChange={(event) => onPqcFilterChange(event.target.value)}
          className="asset-filter"
          aria-label="Filter by PQC applicability"
        >
          <option value="ALL">All PQC Status</option>
          <option value="APPLICABLE">PQC Applicable</option>
          <option value="NOT_APPLICABLE">No Direct PQC</option>
        </select>

        <select
          value={sourceImpactFilter}
          onChange={(event) => onSourceImpactFilterChange(event.target.value)}
          className="asset-filter"
          aria-label="Filter by source impact"
        >
          <option value="ALL">All Source Impact</option>
          <option value="HIGH">High Impact</option>
          <option value="MEDIUM">Medium Impact</option>
          <option value="LOW">Low Impact</option>
        </select>
      </div>
    </div>
  );
}

const API_BASE_URL = "http://127.0.0.1:8000";

async function request(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;

    try {
      const error = await response.json();
      if (error.detail) {
        detail = error.detail;
      }
    } catch {
      // Keep the default error message.
    }

    throw new Error(detail);
  }

  return response.json();
}

// ------------------------------------------------------------
// System
// ------------------------------------------------------------

export function getHealth() {
  return request("/health");
}

export function getStatus() {
  return request("/api/status");
}

export function getSummary() {
  return request("/api/summary");
}

// ------------------------------------------------------------
// Asset Inventory
// ------------------------------------------------------------

export function getAssets() {
  return request("/api/assets");
}
export function getMigrationReportAssets() {
  return request("/api/migration-report/assets");
}
export function getAsset(assetName) {
  return request(
    `/api/asset/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Risk
// ------------------------------------------------------------

export function getRisk() {
  return request("/api/risk");
}

export function getAssetRisk(assetName) {
  return request(
    `/api/risk/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Migration Priority
// ------------------------------------------------------------

export function getPriority() {
  return request("/api/priority");
}

export function getAssetPriority(assetName) {
  return request(
    `/api/priority/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Migration Complexity
// ------------------------------------------------------------

export function getComplexity() {
  return request("/api/complexity");
}

export function getAssetComplexity(assetName) {
  return request(
    `/api/complexity/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Blast Radius
// ------------------------------------------------------------

export function getBlastRadius() {
  return request("/api/blast-radius");
}

export function getAssetBlastRadius(assetName) {
  return request(
    `/api/blast-radius/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// PQC Migration
// ------------------------------------------------------------

export function getPQC() {
  return request("/api/pqc");
}

export function getAssetPQC(assetName) {
  return request(
    `/api/pqc/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// PQC Candidate Ranking
// ------------------------------------------------------------

export function getPQCRanking() {
  return request("/api/pqc-ranking");
}

export function getAssetPQCRanking(assetName) {
  return request(
    `/api/pqc-ranking/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Source Impact
// ------------------------------------------------------------

export function getSourceImpact() {
  return request("/api/source-impact");
}

export function getAssetSourceImpact(assetName) {
  return request(
    `/api/source-impact/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Migration Actions
// ------------------------------------------------------------

export function getMigrationActions() {
  return request("/api/actions");
}

export function getAssetMigrationActions(assetName) {
  return request(
    `/api/actions/${encodeURIComponent(assetName)}`
  );
}

// ------------------------------------------------------------
// Migration Report
// ------------------------------------------------------------



export function getAssetMigrationReport(assetName) {
  return request(
    `/api/migration-report/assets/${encodeURIComponent(assetName)}`
  );
}
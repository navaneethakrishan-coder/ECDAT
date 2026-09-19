const API_BASE_URL = "http://127.0.0.1:8000";

async function request(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;

    try {
      const error = await response.json();
      if (typeof error.detail === "string") {
        detail = error.detail;
      } else if (error.detail?.reason) {
        // Structured errors ({reason_code, reason}) from bom_ref endpoints.
        detail = error.detail.reason;
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
// ------------------------------------------------------------
// Automated Repository Analysis
// ------------------------------------------------------------

export async function startAnalysis(repository, branch = "main") {
  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repository,
      branch,
    }),
  });

  if (!response.ok) {
    let detail = `Scan request failed: ${response.status}`;
    let reasonCode = null;

    try {
      const error = await response.json();

      // Target validation rejections carry {reason_code, reason}.
      if (error.detail?.reason) {
        detail = error.detail.reason;
        reasonCode = error.detail.reason_code || null;
      } else if (typeof error.detail === "string") {
        detail = error.detail;
      }
    } catch {
      // Keep default error message.
    }

    const failure = new Error(detail);
    failure.reasonCode = reasonCode;
    throw failure;
  }

  return response.json();
}

export function getAnalysisStatus() {
  return request("/api/analyze/status");
}

// ------------------------------------------------------------
// Repository scanning (scan lifecycle, capabilities, history)
// ------------------------------------------------------------

export function getScanCapabilities() {
  return request("/api/scan/capabilities");
}

export function getScanHistory() {
  return request("/api/scan/history");
}
// ------------------------------------------------------------
// AI Migration Advisor
// ------------------------------------------------------------

export async function getAIAdvice(assetName) {
  const response = await fetch(`${API_BASE_URL}/api/ai/advice`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      asset: assetName,
    }),
  });

  if (!response.ok) {
    let detail = `AI advice request failed: ${response.status}`;

    try {
      const error = await response.json();

      if (error.detail) {
        detail = error.detail;
      }
    } catch {
      // Keep default error message.
    }

    throw new Error(detail);
  }

  return response.json();
}
// ------------------------------------------------------------
// AI Migration Advisor
// ------------------------------------------------------------

// ------------------------------------------------------------
// PQC migration plan (per-finding strategy, classification, evidence)
// ------------------------------------------------------------

export function getPQCMigrationPlan() {
  return request("/api/pqc-migration-plan");
}

// ------------------------------------------------------------
// Blast-radius relationships (findings addressed by bom_ref only)
// ------------------------------------------------------------

export function getBlastRadiusGraph(bomRef) {
  return request(`/api/blast-radius/${encodeURIComponent(bomRef)}/graph`);
}

// ------------------------------------------------------------
// Evidence Explorer (findings addressed by bom_ref only)
// ------------------------------------------------------------

export function getFindingEvidence(bomRef) {
  return request(`/api/evidence/${encodeURIComponent(bomRef)}`);
}

// ------------------------------------------------------------
// What-If Migration Simulator (findings addressed by bom_ref only)
// ------------------------------------------------------------

async function whatIfRequest(endpoint, body) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let message = `What-if request failed: ${response.status}`;
    let reasonCode = null;

    try {
      const error = await response.json();

      // The scenario engine's rejections carry {reason_code, reason}.
      if (error.detail?.reason) {
        message = error.detail.reason;
        reasonCode = error.detail.reason_code || null;
      } else if (typeof error.detail === "string") {
        message = error.detail;
      }
    } catch {
      // Keep default error message.
    }

    const failure = new Error(message);
    failure.reasonCode = reasonCode;
    throw failure;
  }

  return response.json();
}

export function getWhatIfFinding(bomRef) {
  return whatIfRequest(`/api/what-if/findings/${encodeURIComponent(bomRef)}`);
}

export function simulateWhatIf(bomRef, pqcOption) {
  return whatIfRequest("/api/what-if/simulate", {
    bom_ref: bomRef,
    pqc_option: pqcOption,
  });
}


/**
 * Asks the ECDAT assistant about the current analysis.
 *
 * `bomRef` attaches the selected finding as the primary context; the
 * conversation is the current session's turns, kept in the browser only.
 * Rejections carry {reason_code, reason} like the other ECDAT endpoints,
 * so the chat UI can offer a retry with a real explanation.
 */
export async function sendChatMessage({ message, bomRef = null, conversation = [] }) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      bom_ref: bomRef,
      conversation: conversation.map(({ role, content }) => ({ role, content })),
    }),
  });

  if (!response.ok) {
    let detail = `The ECDAT assistant is unavailable (${response.status}).`;
    let reasonCode = null;

    try {
      const error = await response.json();
      if (error.detail?.reason) {
        detail = error.detail.reason;
        reasonCode = error.detail.reason_code || null;
      } else if (typeof error.detail === "string") {
        detail = error.detail;
      }
    } catch {
      // Keep the default message.
    }

    const failure = new Error(detail);
    failure.reasonCode = reasonCode;
    throw failure;
  }

  return response.json();
}

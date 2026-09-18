// Data + layout model for the Cryptographic Security Map.
//
// Pure functions only: no three.js, no React, no business logic. Every
// value comes from existing ECDAT API data, joined by bom_ref (the only
// canonical finding identity):
//
//   assets     App.jsx's enriched finding list
//              (GET /api/migration-report/assets + GET /api/priority)
//   plan       GET /api/pqc-migration-plan  -> classification, strategy,
//              reconciled recommendation (incl. ranking_model), evidence
//   blast      GET /api/blast-radius         -> recorded CycloneDX
//              dependency refs + blast-radius score/severity
//
// Nothing is scored, classified or inferred here. Positions are a
// deterministic *display* layout of recorded values.

export const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const SEVERITY_COLORS = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#22c55e",
  UNKNOWN: "#64748b",
};

export const STRATEGIES = ["DIRECT_PQC", "HYBRID", "KEEP", "NEEDS_REVIEW"];

export const STRATEGY_META = {
  DIRECT_PQC: { label: "Direct PQC", shape: "sphere", description: "Selected PQC replacement path" },
  HYBRID: { label: "Hybrid", shape: "hybrid", description: "Selected PQC path run alongside the classical primitive" },
  KEEP: { label: "Keep", shape: "cube", description: "No PQC migration" },
  NEEDS_REVIEW: { label: "Needs review", shape: "diamond", description: "Unresolved — no PQC component selected" },
  UNKNOWN: { label: "No strategy", shape: "sphere", description: "No migration strategy recorded" },
};

// Display order of cryptographic-role regions (backend purpose_class).
const ROLE_ORDER = [
  "key-establishment",
  "public-key-encryption",
  "digital-signature",
  "unresolved",
  "protocol",
  "symmetric-encryption",
  "hash",
  "message-authentication",
  "key-derivation",
  "random-generation",
  "mask-generation",
  "key-material",
];

const ROLE_LABELS = {
  "key-establishment": "Key establishment",
  "public-key-encryption": "Public-key encryption",
  "digital-signature": "Digital signature",
  unresolved: "Unresolved role",
  protocol: "Protocol",
  "symmetric-encryption": "Symmetric encryption",
  hash: "Hashing",
  "message-authentication": "Message authentication",
  "key-derivation": "Key derivation",
  "random-generation": "Random generation",
  "mask-generation": "Mask generation",
  "key-material": "Key material",
  other: "Other",
};

// Layout constants (scene units).
const HEIGHT_SCALE = 12; // risk 0..100 -> y 0..12
const DEPTH_SCALE = 8; // priority 0..100 -> z -4..+4 (nearer = higher)
const NODE_WIDTH = 1.3;
const NODE_WITH_KEYS_WIDTH = 3.1;
const KEY_RING_RADIUS = 1.15;
const REGION_GAP = 1.2;

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function indexByRef(records) {
  const map = new Map();
  (records || []).forEach((record) => {
    const ref = record?.bom_ref || record?.asset_ref;
    if (ref) map.set(String(ref), record);
  });
  return map;
}

export function nodeRadius(riskScore) {
  const risk = Math.max(0, Math.min(100, riskScore ?? 0));
  return 0.28 + (risk / 100) * 0.42;
}

/**
 * Normalize one finding. Every field is copied from API data; missing
 * data stays null ("not recorded"), never guessed.
 */
function normalizeFinding(asset, planRecord, blastRecord) {
  const strategyRecord = planRecord?.migration_strategy || null;
  const recommendation = planRecord?.recommendation || {};
  const classification = planRecord?.classification || {};
  const impact = planRecord?.migration_impact || {};
  const locations = planRecord?.evidence?.locations || [];
  const strategy = asset.migrationStrategy || strategyRecord?.strategy || null;
  const migrating = strategy === "DIRECT_PQC" || strategy === "HYBRID";
  const selectedComponent = migrating ? asset.strategyPqcComponent || strategyRecord?.pqc_component || null : null;
  const rankingCandidate = recommendation?.ranking_model?.candidate || null;

  return {
    bomRef: asset.bomRef,
    name: asset.name,
    assetType: asset.type && asset.type !== "Unknown" ? asset.type : null,
    primitive: asset.primitive && asset.primitive !== "Unknown" ? asset.primitive : null,
    family: classification.category || null,
    purposes: Array.isArray(classification.purpose) ? classification.purpose : [],
    purposeConfidence: strategyRecord?.purpose_confidence || null,
    role: strategyRecord?.purpose_class || null,
    roleLabel: strategyRecord?.purpose_class_label || null,
    quantumStatus: classification.quantum_status || null,
    riskScore: toNumber(asset.riskScore),
    riskSeverity: asset.riskSeverity || "UNKNOWN",
    priorityScore: toNumber(asset.priorityScore ?? impact.migration_priority_score),
    priorityLevel: asset.priorityLevel || impact.migration_priority || "UNKNOWN",
    complexityScore: toNumber(impact.migration_complexity_score),
    complexityLevel: asset.complexityLevel || impact.migration_complexity_level || "UNKNOWN",
    blastScore: toNumber(blastRecord?.blast_radius_score),
    blastSeverity: blastRecord?.severity || asset.blastSeverity || "UNKNOWN",
    strategy,
    strategyLabel: strategyRecord?.label || (strategy ? STRATEGY_META[strategy]?.label : null),
    strategyConfidence: strategyRecord?.confidence || null,
    strategyRationale: strategyRecord?.rationale || null,
    pqcFamily: migrating ? strategyRecord?.pqc_family || null : null,
    classicalComponent: strategy === "HYBRID" ? strategyRecord?.classical_component || null : null,
    // Only DIRECT_PQC / HYBRID have a selected PQC component.
    selectedComponent,
    // Ranking-model output, shown only as "not selected" (never as a recommendation).
    rankingCandidate: !migrating ? rankingCandidate : null,
    inheritedFrom: strategyRecord?.inherited_from || null,
    dependencies: (blastRecord?.direct_dependencies?.refs || []).map(String),
    directDependents: (blastRecord?.direct_dependents?.refs || []).map(String),
    transitiveDependents: (blastRecord?.transitive_dependents?.refs || []).map(String),
    sourceLocations: locations
      .map((location) => ({ location: location?.location || null, line: location?.line ?? null }))
      .filter((location) => location.location),
    sourceImpact: asset.sourceImpact || "UNKNOWN",
  };
}

/**
 * Build nodes, recorded edges and role regions with a deterministic layout.
 *
 * Axes: x = cryptographic-role region; y = risk score (height);
 * z = migration priority (nearer the viewer = higher priority).
 * Key-material findings are placed in a small ring around the algorithm
 * they depend on (a recorded dependency edge), at their own risk height;
 * key material with no recorded governing algorithm gets its own region.
 */
export function buildSecurityMapModel(assets, planAssets, blastAssets) {
  const planByRef = indexByRef(planAssets);
  const blastByRef = indexByRef(blastAssets);

  const nodes = (assets || [])
    .filter((asset) => asset?.bomRef)
    .map((asset) => normalizeFinding(asset, planByRef.get(asset.bomRef), blastByRef.get(asset.bomRef)));

  const byRef = new Map(nodes.map((node) => [node.bomRef, node]));

  // Recorded CycloneDX edges only: node dependsOn dependency. Rendered as
  // impact flowing from the dependency to the dependent finding.
  const edgeKeys = new Set();
  const edges = [];
  nodes.forEach((node) => {
    node.dependencies.forEach((dependency) => {
      if (!byRef.has(dependency)) return;
      const key = `${dependency}->${node.bomRef}`;
      if (edgeKeys.has(key)) return;
      edgeKeys.add(key);
      edges.push({ key, from: dependency, to: node.bomRef });
    });
  });

  // Governing algorithm for key material: its first recorded dependency
  // that is not itself key material.
  const parentOf = new Map();
  nodes.forEach((node) => {
    if (node.role !== "key-material") return;
    const parent = [...node.dependencies]
      .sort()
      .find((ref) => byRef.has(ref) && byRef.get(ref).role !== "key-material");
    if (parent) parentOf.set(node.bomRef, parent);
  });

  const childrenOf = new Map();
  parentOf.forEach((parent, child) => {
    if (!childrenOf.has(parent)) childrenOf.set(parent, []);
    childrenOf.get(parent).push(child);
  });
  childrenOf.forEach((children) => children.sort());

  // Regions: every node that is not a placed key-material child.
  const regionMembers = new Map();
  nodes.forEach((node) => {
    if (parentOf.has(node.bomRef)) return;
    const role = ROLE_ORDER.includes(node.role) ? node.role : "other";
    if (!regionMembers.has(role)) regionMembers.set(role, []);
    regionMembers.get(role).push(node);
  });

  const orderedRoles = [...regionMembers.keys()].sort((a, b) => {
    const ia = ROLE_ORDER.indexOf(a) === -1 ? ROLE_ORDER.length : ROLE_ORDER.indexOf(a);
    const ib = ROLE_ORDER.indexOf(b) === -1 ? ROLE_ORDER.length : ROLE_ORDER.indexOf(b);
    return ia - ib;
  });

  const regions = [];
  let cursor = 0;

  orderedRoles.forEach((role) => {
    const members = regionMembers
      .get(role)
      .sort((a, b) => (b.riskScore ?? -1) - (a.riskScore ?? -1) || a.bomRef.localeCompare(b.bomRef));
    const widths = members.map((member) => (childrenOf.has(member.bomRef) ? NODE_WITH_KEYS_WIDTH : NODE_WIDTH));
    const regionWidth = widths.reduce((sum, width) => sum + width, 0);
    const start = cursor;
    let offset = start;

    members.forEach((member, index) => {
      member.position = {
        x: offset + widths[index] / 2,
        y: ((member.riskScore ?? 0) / 100) * HEIGHT_SCALE,
        z: ((member.priorityScore ?? 0) / 100) * DEPTH_SCALE - DEPTH_SCALE / 2,
      };
      member.regionKey = role;
      offset += widths[index];
    });

    regions.push({
      key: role,
      label: ROLE_LABELS[role] || role,
      start,
      end: start + regionWidth,
      center: start + regionWidth / 2,
      count: members.length,
    });

    cursor = start + regionWidth + REGION_GAP;
  });

  // Key material in a ring around its governing algorithm.
  childrenOf.forEach((children, parentRef) => {
    const parent = byRef.get(parentRef);
    children.forEach((childRef, index) => {
      const child = byRef.get(childRef);
      const angle = (index / children.length) * Math.PI * 2 + Math.PI / 4;
      child.position = {
        x: parent.position.x + Math.cos(angle) * KEY_RING_RADIUS,
        y: ((child.riskScore ?? 0) / 100) * HEIGHT_SCALE,
        z: parent.position.z + Math.sin(angle) * KEY_RING_RADIUS,
      };
      child.regionKey = parent.regionKey;
      child.governingRef = parentRef;
      const region = regions.find((item) => item.key === parent.regionKey);
      if (region) region.count += 1;
    });
  });

  // Center the whole layout on x = 0.
  const totalWidth = regions.length ? regions[regions.length - 1].end : 0;
  const shift = totalWidth / 2;
  nodes.forEach((node) => {
    if (node.position) node.position.x -= shift;
  });
  regions.forEach((region) => {
    region.start -= shift;
    region.end -= shift;
    region.center -= shift;
  });

  return { nodes, edges, regions, byRef, bounds: { width: totalWidth, height: HEIGHT_SCALE, depth: DEPTH_SCALE } };
}

export function relatedRefs(node) {
  if (!node) return new Set();
  return new Set([...node.dependencies, ...node.directDependents, ...node.transitiveDependents]);
}

export const DEFAULT_FILTERS = {
  severities: [],
  strategies: [],
  priorities: [],
  family: "ALL",
};

export function matchesFilters(node, filters) {
  if (filters.severities.length && !filters.severities.includes(node.riskSeverity)) return false;
  if (filters.strategies.length && !filters.strategies.includes(node.strategy)) return false;
  if (filters.priorities.length && !filters.priorities.includes(node.priorityLevel)) return false;
  if (filters.family !== "ALL" && node.family !== filters.family) return false;
  return true;
}

export function matchesSearch(node, query) {
  const text = query.trim().toLowerCase();
  if (!text) return true;
  const haystack = [
    node.name,
    node.bomRef,
    node.family,
    node.roleLabel,
    node.assetType,
    node.primitive,
    node.strategy,
    node.selectedComponent,
    ...node.purposes,
    ...node.sourceLocations.map((location) => location.location),
  ];
  return haystack.some((value) => value && String(value).toLowerCase().includes(text));
}

export function summarize(nodes, edges) {
  const severity = Object.fromEntries(SEVERITIES.map((key) => [key, 0]));
  const strategy = Object.fromEntries(STRATEGIES.map((key) => [key, 0]));
  nodes.forEach((node) => {
    if (severity[node.riskSeverity] !== undefined) severity[node.riskSeverity] += 1;
    if (strategy[node.strategy] !== undefined) strategy[node.strategy] += 1;
  });
  return { total: nodes.length, severity, strategy, edges: edges.length };
}

export function shortRef(bomRef) {
  return bomRef ? `${String(bomRef).slice(0, 8)}…` : "";
}

// "private-key@<uuid>" names repeat the bom_ref; show the kind only.
export function displayName(node) {
  if (!node?.name) return "Unknown finding";
  const at = node.name.indexOf("@");
  return at > 0 ? node.name.slice(0, at) : node.name;
}

const WIDTH = 900;
const NODE_W = 150;
const NODE_H = 46;

function shortRef(bomRef) {
  return bomRef ? `${bomRef.slice(0, 8)}…` : "";
}

function displayName(node) {
  if (!node.name) return "Unknown finding";
  const at = node.name.indexOf("@");
  return at > 0 ? node.name.slice(0, at) : node.name;
}

function spread(nodes, y) {
  const step = Math.min(NODE_W + 22, (WIDTH - 40) / Math.max(nodes.length, 1));
  return nodes.map((node, index) => ({
    node,
    x: WIDTH / 2 + (index - (nodes.length - 1) / 2) * step,
    y,
    width: Math.min(NODE_W, step - 12),
  }));
}

function trim(text, width) {
  const max = Math.max(Math.floor(width / 7.2), 4);
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function Node({ item, tier, current, onInvestigate }) {
  const { node, x, y, width } = item;
  const unknown = node.known_finding === false;
  const interactive = !current && !unknown && Boolean(onInvestigate);
  const name = displayName(node);
  const label = current
    ? `${name}, this finding`
    : unknown
    ? `${name}, not in the inventory`
    : `Investigate ${name}, bom-ref ${node.bom_ref}`;

  return (
    <g
      className={`blast3d-node blast3d-${tier}${current ? " is-current" : ""}${unknown ? " is-unknown" : ""}${
        interactive ? " is-interactive" : ""
      }`}
      transform={`translate(${x} ${y})`}
      data-bom-ref={node.bom_ref}
      role={interactive ? "button" : "img"}
      tabIndex={interactive ? 0 : undefined}
      aria-label={label}
      onClick={interactive ? () => onInvestigate(node.bom_ref) : undefined}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onInvestigate(node.bom_ref);
              }
            }
          : undefined
      }
    >
      <title>{label}</title>
      <rect className="blast3d-shadow" x={-width / 2 + 4} y={-NODE_H / 2 + 6} width={width} height={NODE_H} rx={9} />
      <rect className="blast3d-card" x={-width / 2} y={-NODE_H / 2} width={width} height={NODE_H} rx={9} />
      <text className="blast3d-name" y={-3} textAnchor="middle">
        {trim(name, width)}
      </text>
      <text className="blast3d-ref" y={13} textAnchor="middle">
        {unknown ? "not in inventory" : shortRef(node.bom_ref)}
      </text>
    </g>
  );
}

function edgePath(from, to) {
  const startY = from.y + (to.y > from.y ? NODE_H / 2 : -NODE_H / 2);
  const endY = to.y + (to.y > from.y ? -NODE_H / 2 - 6 : NODE_H / 2 + 6);
  const midY = (startY + endY) / 2;
  return `M ${from.x} ${startY} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${endY}`;
}

/**
 * Spatial blast radius: the finding at the centre, what it depends on
 * receding behind it, and the findings that depend on it (directly,
 * then indirectly) coming toward the viewer. Every node and edge comes
 * from GET /api/blast-radius/{bom_ref}/graph; indirect nodes attach to
 * the recorded `via` finding only. Selecting a node investigates that
 * finding by its bom_ref.
 */
export function BlastSpatialView({ view, onInvestigate }) {
  const { finding, dependencies, direct_dependents: direct, indirect_dependents: indirect } = view;

  const hasUpstream = dependencies.length > 0;
  const upstreamY = 50;
  const centerY = hasUpstream ? 170 : 60;
  const directY = centerY + 128;
  const indirectY = directY + 118;
  const height = (indirect.length ? indirectY : direct.length ? directY : centerY) + 50;

  const center = { node: { ...finding, known_finding: true }, x: WIDTH / 2, y: centerY, width: NODE_W + 20 };
  const upstream = spread(dependencies, upstreamY);
  const downstream = spread(direct, directY);
  const outer = spread(indirect, indirectY);

  const positions = new Map([[finding.bom_ref, center]]);
  [...upstream, ...downstream, ...outer].forEach((item) => positions.set(item.node.bom_ref, item));

  const edges = [
    ...upstream.map((item) => ({ key: `u-${item.node.bom_ref}`, from: item, to: center, tier: "upstream" })),
    ...downstream.map((item) => ({ key: `d-${item.node.bom_ref}`, from: center, to: item, tier: "direct" })),
    ...outer.flatMap((item) =>
      (item.node.via || [])
        .filter((ref) => positions.has(ref))
        .map((ref) => ({ key: `i-${ref}-${item.node.bom_ref}`, from: positions.get(ref), to: item, tier: "indirect" })),
    ),
  ];

  return (
    <div className="blast3d" aria-label="Spatial dependency view">
      <div className="blast3d-legend" aria-hidden="true">
        {hasUpstream && <span className="blast3d-key blast3d-key-upstream">Depends on</span>}
        <span className="blast3d-key blast3d-key-current">This finding</span>
        {direct.length > 0 && <span className="blast3d-key blast3d-key-direct">Direct dependents</span>}
        {indirect.length > 0 && <span className="blast3d-key blast3d-key-indirect">Indirect dependents</span>}
      </div>
      <div className="blast3d-stage">
        <svg className="blast3d-svg" viewBox={`0 0 ${WIDTH} ${height}`} role="group" aria-label="Recorded dependency relationships">
          <defs>
            <marker id="blast3d-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="blast3d-arrowhead" />
            </marker>
          </defs>

          <g className="blast3d-plates" aria-hidden="true">
            {hasUpstream && <rect x={20} y={upstreamY - 38} width={WIDTH - 40} height={76} rx={14} className="blast3d-plate blast3d-plate-back" />}
            {direct.length > 0 && <rect x={20} y={directY - 38} width={WIDTH - 40} height={76} rx={14} className="blast3d-plate" />}
            {indirect.length > 0 && <rect x={20} y={indirectY - 38} width={WIDTH - 40} height={76} rx={14} className="blast3d-plate blast3d-plate-front" />}
          </g>

          <g aria-hidden="true">
            {edges.map((edge) => (
              <path key={edge.key} d={edgePath(edge.from, edge.to)} className={`blast3d-edge blast3d-edge-${edge.tier}`} markerEnd="url(#blast3d-arrow)" />
            ))}
          </g>

          {upstream.map((item) => (
            <Node key={item.node.bom_ref} item={item} tier="upstream" onInvestigate={onInvestigate} />
          ))}
          <Node item={center} tier="center" current />
          {downstream.map((item) => (
            <Node key={item.node.bom_ref} item={item} tier="direct" onInvestigate={onInvestigate} />
          ))}
          {outer.map((item) => (
            <Node key={item.node.bom_ref} item={item} tier="indirect" onInvestigate={onInvestigate} />
          ))}
        </svg>
      </div>
    </div>
  );
}

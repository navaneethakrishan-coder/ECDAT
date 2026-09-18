/**
 * One layer of the command-center composition. The marker places the
 * section on the vertical "spine" that connects the layers (posture →
 * operations → landscape → intelligence → findings); `tier` sets how
 * much depth its surfaces get, so importance reads from elevation
 * rather than every panel looking equally raised.
 */
export function SpaceLayer({ index, label, tier = "secondary", active = false, children }) {
  return (
    <div className={`space-layer-group${active ? " is-active" : ""}`} data-tier={tier}>
      <div className="space-layer-marker" aria-hidden="true">
        <span className="space-layer-index">{index}</span>
        <span className="space-layer-label">{label}</span>
      </div>
      {children}
    </div>
  );
}

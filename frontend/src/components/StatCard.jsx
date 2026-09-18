import { useSpatialTilt } from "../spatial/useSpatialTilt";

export function StatCard({ title, value, subtitle, icon: Icon, tone, onClick, actionLabel, active = false }) {
  const tilt = useSpatialTilt(2.5);
  const className = `stat-card spatial-surface${tone ? ` stat-card-${tone}` : ""}${onClick ? " stat-card-interactive" : ""}${
    active ? " is-active" : ""
  }`;
  const content = (
    <>
      <span className="spatial-glare" aria-hidden="true" />
      <div className="stat-card-top">
        <span>{title}</span>
        <div className="stat-icon">
          <Icon size={18} />
        </div>
      </div>

      <div className="stat-value">{value}</div>
      <div className="stat-subtitle">{subtitle}</div>
    </>
  );

  // Metrics that map to a real Security Map filter become buttons (their
  // active state mirrors the map's current filters); the rest stay static
  // rather than pretending to be interactive.
  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        aria-label={actionLabel || `${title}: ${value}`}
        aria-pressed={active}
        {...tilt}
      >
        {content}
      </button>
    );
  }

  return <div className={className}>{content}</div>;
}

// Not currently rendered anywhere (kept from the original App.jsx,
// where it was also defined but unused) — left available for a future
// distribution-list view without inventing new behavior.
export function DistributionBar({ label, value, total }) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;

  return (
    <div className="distribution-row">
      <div className="distribution-header">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>

      <div className="distribution-track">
        <div className="distribution-fill" style={{ width: `${percentage}%` }} />
      </div>

      <span className="distribution-percent">{percentage}%</span>
    </div>
  );
}

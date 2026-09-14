export function StatCard({ title, value, subtitle, icon: Icon, tone }) {
  return (
    <div className={`stat-card${tone ? ` stat-card-${tone}` : ""}`}>
      <div className="stat-card-top">
        <span>{title}</span>
        <div className="stat-icon">
          <Icon size={18} />
        </div>
      </div>

      <div className="stat-value">{value}</div>
      <div className="stat-subtitle">{subtitle}</div>
    </div>
  );
}

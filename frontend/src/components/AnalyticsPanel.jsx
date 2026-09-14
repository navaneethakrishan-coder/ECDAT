import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * One analytics chart panel (icon + title + description + bar chart).
 * Replaces three near-identical, hand-duplicated chart blocks that
 * used to live directly in App.jsx. Clicking a bar still drives the
 * asset-explorer filters via `onBarClick`, exactly as before.
 */
export function AnalyticsPanel({
  id,
  icon: Icon,
  title,
  description,
  data,
  color,
  onBarClick,
}) {
  return (
    <div className="panel analytics-panel" id={id}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <Icon size={20} />
      </div>

      <div className="analytics-panel-chart">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
            <XAxis dataKey="name" stroke="var(--text-tertiary)" tick={{ fontSize: 11 }} />
            <YAxis stroke="var(--text-tertiary)" allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip
              cursor={{ fill: "rgba(148, 163, 184, 0.06)" }}
              contentStyle={{
                background: "var(--bg-surface-raised)",
                border: "1px solid var(--border-strong)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-primary)" }}
            />
            <Bar
              dataKey="value"
              name="Assets"
              fill={color}
              radius={[5, 5, 0, 0]}
              cursor="pointer"
              onClick={(entry) => onBarClick?.(entry?.name)}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

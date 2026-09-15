import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

/**
 * One analytics panel, rendered as a donut/ring chart with a
 * center total and a compact legend -- reads as a security
 * intelligence product's distribution widget rather than a generic
 * bar chart. Replaces the previous bar-chart AnalyticsPanel; the
 * data/interaction contract is unchanged (same `data` shape, same
 * click-to-filter behavior, now `onSliceClick`).
 */
export function DonutPanel({ id, icon: Icon, title, description, data, colors, onSliceClick, centerValue, centerLabel }) {
  const total = data.reduce((sum, entry) => sum + (entry.value || 0), 0);

  // Most charts show the total; a chart can instead highlight a
  // specific real subset (e.g. the risk donut highlighting its own
  // HIGH+CRITICAL count) by passing centerValue/centerLabel -- still
  // a number the caller already computed from this same `data` prop,
  // never a fabricated figure.
  const displayValue = centerValue ?? total;
  const displayLabel = centerLabel ?? "total";

  return (
    <div className="panel analytics-panel" id={id}>
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <Icon size={20} />
      </div>

      <div className="donut-panel-body">
        <div className="donut-chart-wrap">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius="64%"
                outerRadius="100%"
                paddingAngle={data.length > 1 ? 3 : 0}
                stroke="none"
                cursor="pointer"
                onClick={(entry) => onSliceClick?.(entry?.name)}
              >
                {data.map((entry, index) => (
                  <Cell key={entry.name} fill={colors[index % colors.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "var(--bg-surface-raised)",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "var(--text-primary)" }}
              />
            </PieChart>
          </ResponsiveContainer>

          <div className="donut-center-label">
            <strong>{displayValue}</strong>
            <span>{displayLabel}</span>
          </div>
        </div>

        <ul className="donut-legend">
          {data.map((entry, index) => (
            <li key={entry.name}>
              <button type="button" onClick={() => onSliceClick?.(entry.name)}>
                <span className="donut-legend-dot" style={{ background: colors[index % colors.length] }} />
                <span className="donut-legend-name">{entry.name}</span>
                <span className="donut-legend-value">{entry.value}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

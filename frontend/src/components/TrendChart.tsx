import type { ObservationTrend } from "@/api/observations";

/**
 * Single-series lab trend line — spec §33. Deliberately plain inline SVG (no charting
 * library dependency, matching the rest of this app's original-artwork approach from
 * Phase 02): 2px line, round caps, ≥8px markers with a surface ring, abnormal points
 * in the danger color, direct end-label instead of a legend (a single series needs
 * none — the card title already names it). All values shown here also exist in the
 * plain observation list below the chart, so nothing is chart-only.
 */
export function TrendChart({ trend }: { trend: ObservationTrend }) {
  const numeric = trend.points.filter((p) => p.value_numeric !== null && p.measured_at !== null);

  if (numeric.length === 0) {
    return <p className="text-sm text-muted-text">No numeric readings to chart yet.</p>;
  }

  const width = 640;
  const height = 190;
  const padLeft = 44;
  const padRight = 64;
  const padTop = 18;
  const padBottom = 28;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const times = numeric.map((p) => new Date(p.measured_at as string).getTime());
  const values = numeric.map((p) => p.value_numeric as number);

  const latest = numeric[numeric.length - 1];

  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeSpan = maxTime - minTime || 1;

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueSpan = maxValue - minValue || Math.abs(maxValue) || 1;
  const yMin = minValue - valueSpan * 0.15;
  const yMax = maxValue + valueSpan * 0.15;

  const x = (t: number) => padLeft + (numeric.length === 1 ? plotW / 2 : ((t - minTime) / timeSpan) * plotW);
  const y = (v: number) => padTop + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const linePath = numeric
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(times[i]).toFixed(1)} ${y(p.value_numeric as number).toFixed(1)}`)
    .join(" ");

  const formatDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "2-digit", month: "short" });

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={`${trend.display_name} trend`}>
        {/* Baseline + top hairline gridlines — recessive, one step off the surface. */}
        <line x1={padLeft} x2={width - padRight} y1={padTop} y2={padTop} className="stroke-border" strokeWidth={1} />
        <line
          x1={padLeft}
          x2={width - padRight}
          y1={height - padBottom}
          y2={height - padBottom}
          className="stroke-border"
          strokeWidth={1}
        />
        <text x={padLeft - 6} y={padTop + 4} textAnchor="end" className="fill-muted-text text-[10px]">
          {yMax.toFixed(1)}
        </text>
        <text x={padLeft - 6} y={height - padBottom} textAnchor="end" className="fill-muted-text text-[10px]">
          {yMin.toFixed(1)}
        </text>

        {numeric.length > 1 && <path d={linePath} fill="none" className="stroke-primary-blue" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}

        {numeric.map((p, i) => {
          const cx = x(times[i]);
          const cy = y(p.value_numeric as number);
          const abnormal = Boolean(p.abnormal_flag);
          return (
            <g key={p.observation_id}>
              <circle cx={cx} cy={cy} r={5} className={abnormal ? "fill-danger" : "fill-primary-blue"} stroke="white" strokeWidth={2}>
                <title>
                  {formatDate(p.measured_at as string)}: {p.value_numeric}
                  {p.unit ? ` ${p.unit}` : ""}
                  {abnormal ? " (abnormal)" : ""}
                </title>
              </circle>
              {(i === 0 || i === numeric.length - 1) && (
                <text x={cx} y={height - padBottom + 16} textAnchor="middle" className="fill-muted-text text-[10px]">
                  {formatDate(p.measured_at as string)}
                </text>
              )}
            </g>
          );
        })}

        {/* Direct end-label — the value at the most recent point, per mark spec
           ("lines label the value at the end") rather than labeling every point. */}
        <text
          x={x(times[times.length - 1]) + 10}
          y={y(latest.value_numeric as number) + 4}
          className={`text-xs font-semibold ${latest.abnormal_flag ? "fill-danger" : "fill-navy"}`}
        >
          {latest.value_numeric}
          {trend.unit ? ` ${trend.unit}` : ""}
        </text>
      </svg>

      {numeric.length === 1 && (
        <p className="mt-1 text-xs text-muted-text">Only one reading so far — need at least two to show a trend line.</p>
      )}
      {trend.unit_conflict && (
        <p className="mt-1 text-xs text-amber-700">
          {trend.excluded_units.length} result{trend.excluded_units.length === 1 ? "" : "s"} in a different unit (
          {trend.excluded_units.join(", ")}) — not shown on this chart since there's no verified conversion; see the
          full list below.
        </p>
      )}
    </div>
  );
}

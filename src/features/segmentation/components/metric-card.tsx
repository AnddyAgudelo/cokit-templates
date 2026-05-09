"use client";
import type { ChartSpec } from "../schemas";

export function MetricCard({ chart }: { chart: ChartSpec }) {
  const point = chart.data[0];
  const formatted = new Intl.NumberFormat().format(point.value);
  return (
    <div className="rounded-lg border border-[var(--border)] p-6 bg-[var(--background)]">
      <p className="text-xs uppercase tracking-wide text-gray-500">{chart.title}</p>
      <p className="text-4xl font-bold mt-2">{formatted}</p>
      <p className="text-xs text-gray-500 mt-1">{chart.source_query}</p>
    </div>
  );
}

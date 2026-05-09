"use client";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartSpec } from "../schemas";

export function BarChart({ chart }: { chart: ChartSpec }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-4 bg-[var(--background)]">
      <h3 className="font-semibold text-sm">{chart.title}</h3>
      <p className="text-xs text-gray-500 mb-2">{chart.source_query}</p>
      <ResponsiveContainer width="100%" height={280}>
        <RechartsBarChart data={chart.data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" label={chart.x_label ? { value: chart.x_label, position: "insideBottom", offset: -5 } : undefined} />
          <YAxis label={chart.y_label ? { value: chart.y_label, angle: -90, position: "insideLeft" } : undefined} />
          <Tooltip />
          <Legend />
          <Bar dataKey="value" fill="#3b82f6" />
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}

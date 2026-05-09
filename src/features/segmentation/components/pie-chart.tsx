"use client";
import {
  Cell,
  Legend,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { ChartSpec } from "../schemas";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export function PieChart({ chart }: { chart: ChartSpec }) {
  return (
    <div className="rounded-lg border border-[var(--border)] p-4 bg-[var(--background)]">
      <h3 className="font-semibold text-sm">{chart.title}</h3>
      <p className="text-xs text-gray-500 mb-2">{chart.source_query}</p>
      <ResponsiveContainer width="100%" height={280}>
        <RechartsPieChart>
          <Pie
            data={chart.data}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="50%"
            outerRadius={90}
            label
          >
            {chart.data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </RechartsPieChart>
      </ResponsiveContainer>
    </div>
  );
}

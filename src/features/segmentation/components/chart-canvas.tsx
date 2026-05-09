"use client";
import { useAgent } from "@copilotkit/react-core/v2";

import { ChartSpecSchema, type ChartSpec } from "../schemas";
import { BarChart } from "./bar-chart";
import { MetricCard } from "./metric-card";
import { PieChart } from "./pie-chart";

export function ChartCanvas() {
  const { agent } = useAgent();
  const rawCharts = (agent.state?.charts ?? []) as unknown[];

  const charts: ChartSpec[] = rawCharts
    .map((c) => {
      const result = ChartSpecSchema.safeParse(c);
      if (!result.success) {
        console.warn("Skipping invalid chart spec:", result.error.flatten());
        return null;
      }
      return result.data;
    })
    .filter((c): c is ChartSpec => c !== null);

  if (charts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <p className="text-lg font-medium">Ask me about your customers</p>
        <p className="text-sm text-gray-500 mt-2">
          Try: "Show me distribution by city for premium customers"
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {charts.map((chart) => {
        switch (chart.type) {
          case "pie":
            return <PieChart key={chart.id} chart={chart} />;
          case "bar":
            return <BarChart key={chart.id} chart={chart} />;
          case "metric":
            return <MetricCard key={chart.id} chart={chart} />;
        }
      })}
    </div>
  );
}

"use client";
import { CopilotChat } from "@copilotkit/react-core/v2";

import { ChartCanvas } from "@/features/segmentation/components/chart-canvas";
import { useSegmentationCharts } from "@/hooks/use-segmentation-charts";

export default function HomePage() {
  useSegmentationCharts();

  return (
    <div className="flex h-screen">
      <aside className="w-1/3 border-r border-[var(--border)] flex flex-col">
        <div className="p-4 border-b border-[var(--border)]">
          <h1 className="font-bold">Segmentation Explorer</h1>
          <p className="text-xs text-gray-500">Read-only Zoho CRM</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          <CopilotChat input={{ disclaimer: () => null }} />
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <ChartCanvas />
      </main>
    </div>
  );
}

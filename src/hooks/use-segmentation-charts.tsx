"use client";
import { useDefaultRenderTool } from "@copilotkit/react-core/v2";

const HIDDEN_TOOL_RENDERS = new Set(["render_chart"]);

export function useSegmentationCharts() {
  // Render data tool calls inline as small text indicators; hide render_chart
  // because it has its own canvas display.
  useDefaultRenderTool({
    render: ({ name, status }) => {
      if (HIDDEN_TOOL_RENDERS.has(name)) return <></>;
      const label = name.replaceAll("_", " ");
      const dot = status === "complete" ? "✓" : "…";
      return (
        <div className="text-xs text-gray-500 italic">
          {dot} {label}
        </div>
      );
    },
  });
}

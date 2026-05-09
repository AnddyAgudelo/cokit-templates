import { z } from "zod";

export const ChartTypeSchema = z.enum(["pie", "bar", "metric"]);

export const ChartDataPointSchema = z.object({
  label: z.string(),
  value: z.number(),
});

export const ChartSpecSchema = z.object({
  id: z.string(),
  type: ChartTypeSchema,
  title: z.string(),
  data: z.array(ChartDataPointSchema).min(1),
  x_label: z.string().nullable(),
  y_label: z.string().nullable(),
  source_query: z.string(),
});

export type ChartType = z.infer<typeof ChartTypeSchema>;
export type ChartDataPoint = z.infer<typeof ChartDataPointSchema>;
export type ChartSpec = z.infer<typeof ChartSpecSchema>;

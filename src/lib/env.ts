import { z } from "zod";

const envSchema = z.object({
  AGENT_URL: z.string().url().default("http://localhost:8124"),
});

export const env = envSchema.parse({
  AGENT_URL: process.env.AGENT_URL,
});

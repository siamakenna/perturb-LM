import { z } from "zod";

export const searchRequestSchema = z.object({
  query: z
    .string({
      error: (issue) => (issue.input === undefined ? "Query is required." : undefined),
    })
    .trim()
    .min(1, "Enter a biological phenotype query.")
    .max(240, "Queries must be 240 characters or fewer."),
});

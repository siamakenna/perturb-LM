import { z } from "zod";

export const searchRequestSchema = z.object({
  query: z
    .string({ required_error: "Query is required." })
    .trim()
    .min(1, "Enter a biological phenotype query.")
    .max(240, "Queries must be 240 characters or fewer."),
});

import { DEMO_DISCLAIMER, type SearchProvider, type SearchResponse } from "./types";

const syntheticResults = [
  {
    id: "perturbation-a",
    label: "Perturbation A",
    description: "An anonymized synthetic profile with mitochondrial organization language.",
    evidenceTags: ["organelle pattern", "texture shift", "profile-space demo"],
    morphologySummary: "Compact perinuclear signal with altered organelle distribution.",
    keywords: ["mitochondrial", "mitochondria", "organization", "organelle", "energy"],
  },
  {
    id: "perturbation-b",
    label: "Perturbation B",
    description: "An anonymized synthetic profile with lysosomal stress language.",
    evidenceTags: ["vesicle signal", "stress morphology", "profile-space demo"],
    morphologySummary: "Increased punctate granularity with vesicle-like texture.",
    keywords: ["lysosomal", "lysosome", "stress", "granularity", "punctate"],
  },
  {
    id: "perturbation-c",
    label: "Perturbation C",
    description: "An anonymized synthetic profile with cytoskeletal organization language.",
    evidenceTags: ["shape change", "cytoskeletal cue", "profile-space demo"],
    morphologySummary: "Elongated cell-shape features with disrupted structural organization.",
    keywords: ["cytoskeletal", "cytoskeleton", "actin", "shape", "organization"],
  },
  {
    id: "perturbation-d",
    label: "Perturbation D",
    description: "An anonymized synthetic profile with nuclear texture language.",
    evidenceTags: ["nuclear texture", "intensity shift", "profile-space demo"],
    morphologySummary: "Reduced nuclear texture contrast with smoother compartment signal.",
    keywords: ["nuclear", "nucleus", "texture", "chromatin", "reduced"],
  },
];

export class MockSearchProvider implements SearchProvider {
  async search(query: string): Promise<SearchResponse> {
    const normalized = query.toLowerCase();
    const results = syntheticResults
      .map((result, index) => {
        const matches = result.keywords.filter((keyword) => normalized.includes(keyword)).length;
        const score = Math.min(0.94, 0.48 + matches * 0.12 + (syntheticResults.length - index) * 0.025);
        return {
          id: result.id,
          label: result.label,
          description: result.description,
          score: Number(score.toFixed(3)),
          evidenceTags: result.evidenceTags,
          morphologySummary: result.morphologySummary,
          explanation:
            matches > 0
              ? "Ranked higher because the synthetic tags overlap with the submitted concept."
              : "Included as a lower-ranked illustrative contrast result.",
          synthetic: true as const,
        };
      })
      .sort((a, b) => b.score - a.score || a.label.localeCompare(b.label));

    return {
      mode: "illustrative_demo",
      results,
      disclaimer: DEMO_DISCLAIMER,
      leakageStatus: {
        treatmentIdentifiers: "not_used",
        targetSequences: "not_used",
        plateWellLabels: "not_used",
        modelStatus: "pending",
      },
    };
  }
}

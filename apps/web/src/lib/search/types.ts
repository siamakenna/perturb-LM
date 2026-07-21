export const DEMO_DISCLAIMER = "Illustrative interface demo — not real model output";

export interface SearchResult {
  id: string;
  label: string;
  description: string;
  score: number;
  evidenceTags: string[];
  morphologySummary: string;
  explanation: string;
  synthetic: true;
}

export interface SearchResponse {
  mode: "illustrative_demo";
  results: SearchResult[];
  disclaimer: typeof DEMO_DISCLAIMER;
  leakageStatus: {
    treatmentIdentifiers: "not_used";
    targetSequences: "not_used";
    plateWellLabels: "not_used";
    modelStatus: "pending";
  };
}

export interface SearchProvider {
  search(query: string): Promise<SearchResponse>;
}

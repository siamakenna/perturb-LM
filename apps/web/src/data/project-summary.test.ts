import { describe, expect, it } from "vitest";
import summary from "./project-summary.json";

describe("project summary", () => {
  it("keeps headline numbers public and consistent", () => {
    expect(summary.profileCount).toBe(4524);
    expect(summary.featureCount).toBe(904);
    expect(summary.queryCount).toBe(641);
    expect(summary.lexicalBaselineMap).toBe(0.2513);
    expect(summary.confidenceInterval.low).toBe(0.2445);
    expect(summary.confidenceInterval.high).toBe(0.2582);
  });

  it("does not present a completed learned model result", () => {
    expect(summary.phase3cImplementationStatus).toBe("ready");
    expect(summary.selectedEncoder.model).toBe(
      "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
    );
    expect(summary.selectedEncoder.pinnedRevision).toBe(
      "e1354b7a3a09615f6aba48dfad4b7a613eef7062",
    );
    expect(summary.selectedEncoder.runStatus).toBe("pending");
    expect(summary.projectedModelStatus).toBe("pending");
    expect(summary.learnedModelStatus).toBe("pending");
    expect(summary.heldOutBatchStatus).toBe("unavailable");
    expect(summary.syntheticDisclaimer).toBe("Illustrative interface demo — not real model output");
    expect(summary.currentClaimStatus.toLowerCase()).not.toContain("learned model outperforms");
  });

  it("gates pending learned methods from numeric dashboard scores", () => {
    const pendingRows = summary.methodComparison.filter((row) => !row.hasResult);

    expect(pendingRows.length).toBeGreaterThan(0);
    for (const row of pendingRows) {
      expect(row.map).toBeNull();
      expect(row.ciLow).toBeNull();
      expect(row.ciHigh).toBeNull();
      expect(row.note.toLowerCase()).toMatch(/pending|planned|unavailable/);
    }
  });
});

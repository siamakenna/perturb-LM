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
    expect(summary.learnedModelStatus).toBe("pending");
    expect(summary.currentClaimStatus.toLowerCase()).not.toContain("learned model outperforms");
  });
});

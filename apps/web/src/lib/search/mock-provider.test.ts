import { describe, expect, it } from "vitest";
import { DEMO_DISCLAIMER, MockSearchProvider, type SearchProvider } from "@/lib/search";

describe("MockSearchProvider", () => {
  it("returns deterministic ranked synthetic results", async () => {
    const provider = new MockSearchProvider();
    const first = await provider.search("altered mitochondrial organization");
    const second = await provider.search("altered mitochondrial organization");

    expect(first).toEqual(second);
    expect(first.mode).toBe("illustrative_demo");
    expect(first.disclaimer).toBe(DEMO_DISCLAIMER);
    expect(first.results[0]?.label).toBe("Perturbation A");
    expect(first.results.every((result) => result.synthetic)).toBe(true);
  });

  it("can be consumed through the provider interface", async () => {
    const provider: SearchProvider = new MockSearchProvider();
    const response = await provider.search("lysosomal stress phenotype");

    expect(response.results[0]?.label).toBe("Perturbation B");
    expect(response.leakageStatus.modelStatus).toBe("pending");
  });
});

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("RootLayout", () => {
  it("includes dashboard navigation and a mobile menu control", () => {
    const source = readFileSync(join(process.cwd(), "src/app/layout.tsx"), "utf8");

    expect(source).toContain('["Dashboard", "/dashboard"]');
    expect(source).toContain("<details");
    expect(source).toContain("Skip to content");
  });
});

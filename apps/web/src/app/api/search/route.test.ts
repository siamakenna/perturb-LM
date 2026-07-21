import { describe, expect, it } from "vitest";
import { POST } from "./route";
import { DEMO_DISCLAIMER } from "@/lib/search";

function request(body: unknown) {
  return new Request("http://localhost/api/search", {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/search", () => {
  it("rejects empty queries", async () => {
    const response = await POST(request({ query: "" }));
    expect(response.status).toBe(400);
  });

  it("rejects long queries", async () => {
    const response = await POST(request({ query: "x".repeat(241) }));
    expect(response.status).toBe(400);
  });

  it("rejects malformed JSON", async () => {
    const response = await POST(request("{"));
    expect(response.status).toBe(400);
  });

  it("always includes the demo disclaimer", async () => {
    const response = await POST(request({ query: "reduced nuclear texture" }));
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.disclaimer).toBe(DEMO_DISCLAIMER);
    expect(payload.results.every((result: { synthetic: boolean }) => result.synthetic)).toBe(true);
  });
});

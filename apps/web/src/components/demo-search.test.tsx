import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DemoSearch } from "./demo-search";
import { DEMO_DISCLAIMER } from "@/lib/search";

describe("DemoSearch", () => {
  it("renders the disclaimer and does not claim real model output", () => {
    render(<DemoSearch />);

    expect(screen.getByText(DEMO_DISCLAIMER)).toBeInTheDocument();
    expect(screen.getByText(/mock provider/i)).toBeInTheDocument();
    expect(screen.getByText(/No treatment identifiers/i)).toBeInTheDocument();
    expect(screen.getByText(/No live model is running/i)).toBeInTheDocument();
  });
});

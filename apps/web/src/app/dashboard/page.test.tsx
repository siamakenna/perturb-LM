import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DashboardPage from "./page";
import summary from "@/data/project-summary.json";

describe("DashboardPage", () => {
  it("renders canonical metric values and the synthetic disclaimer", () => {
    render(<DashboardPage />);

    expect(screen.getAllByText(summary.profileCount.toLocaleString())[0]).toBeInTheDocument();
    expect(screen.getAllByText(summary.featureCount.toLocaleString())[0]).toBeInTheDocument();
    expect(screen.getAllByText(summary.queryCount.toLocaleString())[0]).toBeInTheDocument();
    expect(screen.getAllByText(summary.lexicalBaselineMap.toFixed(4))[0]).toBeInTheDocument();
    expect(screen.getAllByText(summary.syntheticDisclaimer)[0]).toBeInTheDocument();
  });

  it("keeps pending learned-model rows score-free", () => {
    render(<DashboardPage />);

    for (const row of summary.methodComparison.filter((item) => !item.hasResult)) {
      const label = screen.getByRole("rowheader", { name: row.label });
      const tableRow = label.closest("tr");
      expect(tableRow).not.toBeNull();
      expect(within(tableRow as HTMLTableRowElement).getByText("Pending")).toBeInTheDocument();
      expect(within(tableRow as HTMLTableRowElement).queryByText(/\d+\.\d{4}/)).toBeNull();
    }
  });

  it("provides an accessible text equivalent for the method chart", () => {
    render(<DashboardPage />);

    expect(
      screen.getByRole("region", { name: "Method comparison table" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Text equivalent: identifier-stripped TF-IDF/i),
    ).toBeInTheDocument();
  });
});

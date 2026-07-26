import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  getSearch: vi.fn(), createRisk: vi.fn(), getRisk: vi.fn(), createDocument: vi.fn(),
  savedDocument: vi.fn().mockRejectedValue(new Error("no saved report")),
}));

vi.mock("./api", async importOriginal => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, api: { ...actual.api, ...apiMock } };
});

import { RiskPage, SearchPage } from "./App";

function renderAt(path: string, page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/projects/:projectId/searches/:searchId" element={page} /><Route path="/projects/:projectId/risks/:analysisId" element={page} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("result page loading transitions", () => {
  it("renders a search result after its loading render without a Hook-order crash", async () => {
    apiMock.getSearch.mockResolvedValueOnce({ query: { trademark_name: "星航" }, hits: [] });
    renderAt("/projects/project-1/searches/search-1", <SearchPage />);
    expect(await screen.findByText("“星航”的相似线索")).not.toBeNull();
  });

  it("renders a risk result after its loading render without a Hook-order crash", async () => {
    apiMock.getRisk.mockResolvedValueOnce({ risk_level: "low", risk_score: 0.2, risk_factors: [], suggestions: [], uncertainties: [], evidence_quality: "demo_only" });
    renderAt("/projects/project-1/risks/risk-1", <RiskPage />);
    expect(await screen.findByText("较低")).not.toBeNull();
  });
});

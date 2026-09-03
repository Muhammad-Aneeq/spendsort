/**
 * Render tests for all five screens (spec 11 section 9).
 *
 * These stand in for the visual walkthrough that this environment cannot perform
 * (BLOCKERS.md B7). They verify the things a demo actually dies on — a screen that throws on
 * mount, a chart handed a shape it cannot render, an empty state that renders as a blank box —
 * and they assert the product's *claims* appear on screen: the confidence gate, the "learned"
 * marker, and the memory bend.
 *
 * They cannot judge layout. Nothing here knows whether an axis label collides with a bar.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import Import from "../pages/Import";
import MemoryScreen from "../pages/Memory";
import Metrics from "../pages/Metrics";
import Queue from "../pages/Queue";
import Run from "../pages/Run";
import * as fx from "./fixtures";

const ALL_ROUTES = {
  "/api/health": fx.health,
  "/api/coa/yaml": { yaml: "accounts:\n  - code: '6060'\n    name: Office Supplies\n" },
  "/api/coa": fx.coa,
  "/api/metrics": fx.metrics,
  "/api/queue/transactions": fx.queue,
  "/api/queue": fx.queue,
  "/api/memory": fx.memory,
  "/api/runs": fx.runs,
  "/api/export": "",
};

function mount(ui: React.ReactNode, routes: Record<string, unknown> = ALL_ROUTES) {
  vi.stubGlobal("fetch", vi.fn(fx.stubFetch(routes)));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// --- the shell ---------------------------------------------------------------

describe("app shell", () => {
  it("always shows the synthetic-data banner", async () => {
    mount(<App />);
    // spec 00 A1/E and spec 11 section 11: this must be on every screenshot. Scoped to the
    // banner because the footer repeats the disclaimer — two mentions, not an ambiguity.
    const banner = screen.getByRole("note");
    expect(within(banner).getByText(/All data synthetic/i)).toBeTruthy();
  });

  it("publishes the gate and the cost cap in the header", async () => {
    mount(<App />);
    // The two numbers that decide what the agent may do unattended.
    await waitFor(() => expect(screen.getByText("0.85")).toBeTruthy());
    expect(screen.getByText("$0.25")).toBeTruthy();
  });

  it("says the model is mocked rather than implying real calls", async () => {
    mount(<App />);
    await waitFor(() => expect(screen.getByText(/mock model/i)).toBeTruthy());
  });

  it("offers all five screens", () => {
    mount(<App />);
    for (const label of ["Import", "Run", "Review queue", "Memory", "Metrics"]) {
      expect(screen.getByRole("link", { name: new RegExp(label, "i") })).toBeTruthy();
    }
  });
});

// --- screen 1 ----------------------------------------------------------------

describe("screen 1 · Import + CoA editor", () => {
  it("renders the upload target and the chart of accounts", async () => {
    mount(<Import />);
    expect(screen.getByText(/Choose a CSV file/i)).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Office Supplies")).toBeTruthy());
    expect(screen.getByText("6060")).toBeTruthy();
  });

  it("shows the em-dash account name intact", async () => {
    // The cp1252 trap from PLAN.md D15, checked at the far end of the pipe.
    mount(<Import />);
    await waitFor(() => expect(screen.getByText("Travel — Airfare")).toBeTruthy());
  });
});

// --- screen 2 ----------------------------------------------------------------

describe("screen 2 · Run view", () => {
  it("renders the latest run's numbers and the histogram", async () => {
    mount(<Run />);
    // Wait on data-dependent content — the card titles render before the queries resolve, so
    // waiting on those would race. The run history table only exists once runs load.
    await waitFor(() => expect(screen.getByText("#2")).toBeTruthy());

    expect(screen.getByText("#1")).toBeTruthy();
    expect(screen.getByText(/Confidence distribution/i)).toBeTruthy();
    expect(screen.getByText("From memory")).toBeTruthy();
    // "Auto-applied" appears twice by design: the metric tile and the histogram legend.
    expect(screen.getAllByText("Auto-applied").length).toBeGreaterThanOrEqual(1);
  });

  it("shows an empty state rather than a blank box before any run", async () => {
    mount(<Run />, { ...ALL_ROUTES, "/api/metrics": fx.emptyMetrics, "/api/runs": [] });
    await waitFor(() => expect(screen.getByText(/No runs yet/i)).toBeTruthy());
  });
});

// --- screen 3 ----------------------------------------------------------------

describe("screen 3 · Review queue", () => {
  it("renders vendor, amount, suggested account, confidence and reason", async () => {
    // spec 11 section 9: the row contract.
    mount(<Queue />);
    await waitFor(() => expect(screen.getByText("AMZN Mktp US*Y7D8K6")).toBeTruthy());

    expect(screen.getByText("$120.00")).toBeTruthy();
    expect(screen.getByText(/Office Supplies/)).toBeTruthy();
    expect(screen.getByText(/mock: matched AMAZON MARKETPLACE/)).toBeTruthy();
    // The ConfidencePill shows the number, not just a colour.
    expect(screen.getByText("0.61")).toBeTruthy();
  });

  it("labels a rejected account as invalid instead of merely low-confidence", async () => {
    mount(<Queue />);
    await waitFor(() => expect(screen.getByText(/invalid account/i)).toBeTruthy());
    expect(screen.getByText(/not a real account/i)).toBeTruthy();
  });

  it("refuses one-click accept when the suggested account does not exist", async () => {
    mount(<Queue />);
    await waitFor(() => expect(screen.getByText("BRIGHTLINE CLEANING")).toBeTruthy());

    const rows = screen.getAllByRole("listitem");
    const invalidRow = rows.find((row) => row.textContent?.includes("BRIGHTLINE"));
    expect(invalidRow).toBeTruthy();
    const accept = within(invalidRow!).getByRole("button", { name: /accept/i });
    expect((accept as HTMLButtonElement).disabled).toBe(true);
  });

  it("advertises the keyboard flow", async () => {
    mount(<Queue />);
    await waitFor(() => expect(screen.getByText("AMZN Mktp US*Y7D8K6")).toBeTruthy());
    // spec 11 section 9 asks for a keyboard flow; a hidden one is not a flow.
    expect(screen.getByText("j")).toBeTruthy();
    expect(screen.getByText("a")).toBeTruthy();
    expect(screen.getByText("o")).toBeTruthy();
  });

  it("shows a real empty state when nothing needs review", async () => {
    mount(<Queue />, { ...ALL_ROUTES, "/api/queue": fx.emptyQueue });
    await waitFor(() => expect(screen.getByText(/Nothing to review/i)).toBeTruthy());
  });
});

// --- screen 4 ----------------------------------------------------------------

describe("screen 4 · Memory", () => {
  it("renders learned mappings with hit counts and their source", async () => {
    mount(<MemoryScreen />);
    await waitFor(() => expect(screen.getByText("AMAZON MARKETPLACE")).toBeTruthy());

    expect(screen.getByText("human")).toBeTruthy();
    expect(screen.getByText("llm-confirmed")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
    // The count of model calls that never happened: 7 + 3.
    expect(screen.getByText("10")).toBeTruthy();
  });

  it("explains how memory fills when it is empty", async () => {
    mount(<MemoryScreen />, { ...ALL_ROUTES, "/api/memory": fx.emptyMemory });
    await waitFor(() => expect(screen.getByText(/Memory is empty/i)).toBeTruthy());
  });
});

// --- screen 5 ----------------------------------------------------------------

describe("screen 5 · Metrics", () => {
  it("renders the memory bend as two panels, not one dual-axis plot", async () => {
    mount(<Metrics />);
    await waitFor(() => expect(screen.getByText("The memory bend")).toBeTruthy());

    // Two separate charts sharing an x-axis; a dual-axis plot would invent a crossing point.
    expect(screen.getByText(/Memory-hit rate, per run/i)).toBeTruthy();
    expect(screen.getByText(/Cost per transaction, per run/i)).toBeTruthy();
  });

  it("states the bend in words as well as in the chart", async () => {
    mount(<Metrics />);
    // 0.013206 -> 0.00837 is a 37% drop.
    await waitFor(() => expect(screen.getByText(/cheaper/i)).toBeTruthy());
    expect(screen.getByText(/41% → 63%|41% → 62%|40% → 63%|40% → 62%/)).toBeTruthy();
  });

  it("renders the histogram and the category breakdown", async () => {
    mount(<Metrics />);
    await waitFor(() => expect(screen.getByText(/Spend by account/i)).toBeTruthy());
    expect(screen.getByText("Cloud Hosting")).toBeTruthy();
    expect(screen.getAllByText(/Confidence distribution/i).length).toBeGreaterThan(0);
  });

  it("offers the CSV export", async () => {
    mount(<Metrics />);
    await waitFor(() => expect(screen.getByText(/Export CSV/i)).toBeTruthy());
  });

  it("every chart has a numbers view, so a tooltip is never the only way to read a value", async () => {
    mount(<Metrics />);
    await waitFor(() => expect(screen.getByText("The memory bend")).toBeTruthy());
    // One toggle per chart: two bend panels + auto-rate + histogram.
    expect(screen.getAllByRole("button", { name: /Show numbers/i }).length).toBeGreaterThanOrEqual(4);
  });

  it("asks for a second run rather than drawing a bend from one point", async () => {
    const oneRun = { ...fx.metrics, runs: [fx.runs[0]!] };
    mount(<Metrics />, { ...ALL_ROUTES, "/api/metrics": oneRun });
    await waitFor(() => expect(screen.getByText(/One run so far/i)).toBeTruthy());
  });

  it("shows an empty state before any data", async () => {
    mount(<Metrics />, { ...ALL_ROUTES, "/api/metrics": fx.emptyMetrics });
    await waitFor(() => expect(screen.getByText(/No data yet/i)).toBeTruthy());
  });
});

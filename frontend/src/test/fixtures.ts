/**
 * Fixture API responses, shaped like the real backend.
 *
 * The two-run metrics fixture deliberately encodes a real bend (memory-hit rate up, cost per
 * run down) using the numbers actually measured on the shipped example files, so the tests
 * assert against the story the dashboard is supposed to tell.
 */

import type { Coa, Health, MemoryPage, Metrics, QueuePage, Run } from "../lib/types";

export const health: Health = {
  status: "ok",
  version: "0.1.0",
  auto_threshold: 0.85,
  cost_cap_usd_per_run: 0.25,
  model: "gpt-4o-mini",
  llm_mode: "mock",
  synthetic_data: true,
};

export const coa: Coa = {
  count: 3,
  accounts: [
    { code: "6020", name: "Computer Equipment", kind: "expense", description: "Laptops, monitors" },
    { code: "6060", name: "Office Supplies", kind: "expense", description: "Stationery" },
    { code: "6130", name: "Travel — Airfare", kind: "expense", description: "Flights" },
  ],
};

export const runs: Run[] = [
  {
    id: 1,
    started: "2026-09-03T10:00:00Z",
    finished: "2026-09-03T10:00:12Z",
    txn_count: 120,
    auto_rate: 0.758,
    memory_hit_rate: 0.408,
    cost_usd: 0.013206,
    auto_threshold: 0.85,
    cost_cap_usd: 0.25,
    model: "gpt-4o-mini",
    llm_mode: "mock",
    cost_capped: false,
    capped_txn_count: 0,
    llm_calls: 71,
    memory_hits: 49,
  },
  {
    id: 2,
    started: "2026-09-03T10:05:00Z",
    finished: "2026-09-03T10:05:09Z",
    txn_count: 120,
    auto_rate: 0.817,
    memory_hit_rate: 0.625,
    cost_usd: 0.00837,
    auto_threshold: 0.85,
    cost_cap_usd: 0.25,
    model: "gpt-4o-mini",
    llm_mode: "mock",
    cost_capped: false,
    capped_txn_count: 0,
    llm_calls: 45,
    memory_hits: 75,
  },
];

export const metrics: Metrics = {
  total_transactions: 240,
  pending: 0,
  auto: 189,
  queued: 51,
  resolved: 0,
  auto_rate: 0.7875,
  memory_hit_rate: 0.5167,
  total_cost_usd: 0.021576,
  auto_threshold: 0.85,
  confidence_histogram: [
    { lower: 0.0, upper: 0.1, count: 6, auto: false },
    { lower: 0.1, upper: 0.2, count: 2, auto: false },
    { lower: 0.2, upper: 0.3, count: 0, auto: false },
    { lower: 0.3, upper: 0.4, count: 0, auto: false },
    { lower: 0.4, upper: 0.5, count: 12, auto: false },
    { lower: 0.5, upper: 0.6, count: 14, auto: false },
    { lower: 0.6, upper: 0.7, count: 11, auto: false },
    { lower: 0.7, upper: 0.8, count: 6, auto: false },
    { lower: 0.8, upper: 0.9, count: 34, auto: false },
    { lower: 0.9, upper: 1.0, count: 155, auto: true },
  ],
  category_breakdown: [
    { account_code: "6190", account_name: "Cloud Hosting", count: 18, total_amount: 24310.55 },
    { account_code: "6030", account_name: "Dues & Subscriptions", count: 42, total_amount: 8120.4 },
  ],
  runs,
};

export const emptyMetrics: Metrics = {
  ...metrics,
  total_transactions: 0,
  auto: 0,
  queued: 0,
  resolved: 0,
  auto_rate: 0,
  memory_hit_rate: 0,
  total_cost_usd: 0,
  category_breakdown: [],
  confidence_histogram: metrics.confidence_histogram.map((b) => ({ ...b, count: 0 })),
  runs: [],
};

export const queue: QueuePage = {
  total: 2,
  auto_threshold: 0.85,
  items: [
    {
      id: 11,
      date: "2026-01-04",
      amount: 3610.4,
      currency: "USD",
      vendor_raw: "BRIGHTLINE CLEANING",
      vendor_norm: "BRIGHTLINE CLEANING",
      status: "queued",
      memo: null,
      suggestion: {
        account_code: "",
        account_name: "",
        confidence: 0.08,
        reason: "mock: does not recognise BRIGHTLINE CLEANING",
        source: "llm",
        coa_valid: false,
        cost_usd: 0.000186,
        created_at: "2026-09-03T10:00:01Z",
      },
      final_account: null,
      final_account_name: null,
      learned: false,
    },
    {
      id: 12,
      date: "2026-01-07",
      amount: 120.0,
      currency: "USD",
      vendor_raw: "AMZN Mktp US*Y7D8K6",
      vendor_norm: "AMAZON MARKETPLACE",
      status: "queued",
      memo: "INV-9",
      suggestion: {
        account_code: "6060",
        account_name: "Office Supplies",
        confidence: 0.61,
        reason: "mock: matched AMAZON MARKETPLACE",
        source: "llm",
        coa_valid: true,
        cost_usd: 0.000186,
        created_at: "2026-09-03T10:00:02Z",
      },
      final_account: null,
      final_account_name: null,
      learned: false,
    },
  ],
};

export const emptyQueue: QueuePage = { total: 0, auto_threshold: 0.85, items: [] };

export const memory: MemoryPage = {
  total: 2,
  entries: [
    {
      vendor_norm: "AMAZON MARKETPLACE",
      account_code: "6020",
      account_name: "Computer Equipment",
      source: "human",
      hit_count: 7,
      updated_at: "2026-09-03T10:04:00Z",
      example_vendor_raw: "AMZN Mktp US*Y7D8K6",
    },
    {
      vendor_norm: "SLACK",
      account_code: "6030",
      account_name: "Dues & Subscriptions",
      source: "llm-confirmed",
      hit_count: 3,
      updated_at: "2026-09-03T10:04:00Z",
      example_vendor_raw: "Slack.com",
    },
  ],
};

export const emptyMemory: MemoryPage = { total: 0, entries: [] };

/** Route table for the stubbed fetch. Longest path first so /api/coa/yaml beats /api/coa. */
export type Routes = Record<string, unknown>;

export function stubFetch(routes: Routes) {
  return async (input: RequestInfo | URL): Promise<Response> => {
    const url = typeof input === "string" ? input : input.toString();
    const match = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((path) => url.startsWith(path));

    if (!match) {
      return new Response(JSON.stringify({ detail: `no stub for ${url}` }), { status: 404 });
    }
    return new Response(JSON.stringify(routes[match]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
}

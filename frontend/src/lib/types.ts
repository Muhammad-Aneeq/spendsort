/**
 * Wire types, mirroring `backend/app/schemas.py`.
 *
 * Hand-written rather than generated: the API is small and stable, and a generator would be
 * one more thing to keep running. If these drift from the backend, `npm run typecheck` will
 * not catch it — the API smoke tests will.
 */

export type TxnStatus = "pending" | "auto" | "queued" | "resolved";
export type DecisionSource = "memory" | "llm";
export type MemorySource = "human" | "llm-confirmed";
export type VerdictAction = "accept" | "override";

export type Health = {
  status: string;
  version: string;
  auto_threshold: number;
  cost_cap_usd_per_run: number;
  model: string;
  llm_mode: "mock" | "live";
  synthetic_data: boolean;
};

export type Account = {
  code: string;
  name: string;
  kind: string;
  description: string;
};

export type Coa = {
  accounts: Account[];
  count: number;
};

export type RowError = {
  line: number;
  reason: string;
  raw: string;
};

export type IngestResult = {
  accepted: number;
  rejected: number;
  truncated: boolean;
  encoding: string;
  source_file: string | null;
  errors: RowError[];
  pending_total: number;
};

export type Categorization = {
  account_code: string;
  account_name: string;
  confidence: number;
  reason: string;
  source: DecisionSource;
  coa_valid: boolean;
  cost_usd: number;
  created_at: string | null;
};

export type Transaction = {
  id: number;
  date: string;
  amount: number;
  currency: string;
  vendor_raw: string;
  vendor_norm: string;
  status: TxnStatus;
  memo: string | null;
  suggestion: Categorization | null;
  final_account: string | null;
  final_account_name: string | null;
  /** True when this row was answered from a mapping a human taught us (spec 11 US3). */
  learned: boolean;
};

export type QueuePage = {
  items: Transaction[];
  total: number;
  auto_threshold: number;
};

export type VerdictResult = {
  txn_id: number;
  action: VerdictAction;
  final_account: string;
  final_account_name: string;
  memory_written: boolean;
  at: string | null;
};

export type MemoryEntry = {
  vendor_norm: string;
  account_code: string;
  account_name: string;
  source: MemorySource;
  hit_count: number;
  updated_at: string | null;
  example_vendor_raw: string | null;
};

export type MemoryPage = {
  entries: MemoryEntry[];
  total: number;
};

export type Run = {
  id: number;
  started: string;
  finished: string | null;
  txn_count: number;
  auto_rate: number;
  memory_hit_rate: number;
  cost_usd: number;
  auto_threshold: number;
  cost_cap_usd: number;
  model: string;
  llm_mode: string;
  cost_capped: boolean;
  capped_txn_count: number;
  llm_calls: number;
  memory_hits: number;
};

export type HistogramBin = {
  lower: number;
  upper: number;
  count: number;
  /** Whether decisions in this bin clear the auto-apply threshold. */
  auto: boolean;
};

export type CategoryBreakdownItem = {
  account_code: string;
  account_name: string;
  count: number;
  total_amount: number;
};

export type Metrics = {
  total_transactions: number;
  pending: number;
  auto: number;
  queued: number;
  resolved: number;
  auto_rate: number;
  memory_hit_rate: number;
  total_cost_usd: number;
  auto_threshold: number;
  confidence_histogram: HistogramBin[];
  category_breakdown: CategoryBreakdownItem[];
  /** One point per run, oldest first — this is the memory-bend chart. */
  runs: Run[];
};

/** Typed API client. One place that knows about HTTP, so the screens stay about the product. */

import type {
  Coa,
  Health,
  IngestResult,
  MemoryPage,
  Metrics,
  QueuePage,
  Run,
  TxnStatus,
  VerdictAction,
  VerdictResult,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
  });

  if (!response.ok) {
    // FastAPI puts the useful message in `detail`. Surfacing it verbatim matters here: the
    // intake errors are written to tell someone exactly which column to fix.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: never) => JSON.stringify(d)).join("; ");
    } catch {
      /* not JSON; keep the status line */
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),

  // --- chart of accounts -----------------------------------------------
  coa: () => request<Coa>("/api/coa"),
  coaYaml: () => request<{ yaml: string }>("/api/coa/yaml"),
  saveCoa: (yaml: string) =>
    request<Coa>("/api/coa", { method: "PUT", body: JSON.stringify({ yaml }) }),

  // --- intake -----------------------------------------------------------
  uploadCsv: async (file: File): Promise<IngestResult> => {
    const form = new FormData();
    form.append("file", file);
    // No Content-Type header: the browser must set the multipart boundary itself.
    const response = await fetch("/api/ingest/csv", { method: "POST", body: form });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* keep the status line */
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as IngestResult;
  },

  // --- runs -------------------------------------------------------------
  startRun: () => request<Run>("/api/runs", { method: "POST" }),
  runs: () => request<Run[]>("/api/runs"),

  // --- queue & verdicts --------------------------------------------------
  queue: () => request<QueuePage>("/api/queue"),
  transactions: (status?: TxnStatus) =>
    request<QueuePage>(`/api/queue/transactions${status ? `?status=${status}` : ""}`),
  verdict: (txnId: number, action: VerdictAction, finalAccount?: string) =>
    request<VerdictResult>(`/api/txns/${txnId}/verdict`, {
      method: "POST",
      body: JSON.stringify({ action, final_account: finalAccount ?? null }),
    }),

  // --- memory & metrics --------------------------------------------------
  memory: () => request<MemoryPage>("/api/memory"),
  metrics: () => request<Metrics>("/api/metrics"),

  // --- export ------------------------------------------------------------
  exportUrl: (onlyDecided = false) => `/api/export${onlyDecided ? "?only_decided=true" : ""}`,
};

/**
 * App shell: the five screens of spec 11 section 9, plus the always-visible synthetic-data
 * banner and a header that states the trust settings the agent is being held to.
 *
 * Putting the threshold and the cost cap in the header is deliberate. They are the two numbers
 * that decide what the agent is allowed to do on its own, and a demo that hides them is asking
 * to be trusted rather than showing why it can be.
 */
import { NavLink, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { SyntheticDataBanner } from "./components/aurora";
import { api } from "./lib/api";
import { usd } from "./lib/format";
import Import from "./pages/Import";
import MemoryPage from "./pages/Memory";
import Metrics from "./pages/Metrics";
import Queue from "./pages/Queue";
import Run from "./pages/Run";

const NAV = [
  { to: "/", label: "Import", end: true },
  { to: "/run", label: "Run" },
  { to: "/queue", label: "Review queue" },
  { to: "/memory", label: "Memory" },
  { to: "/metrics", label: "Metrics" },
];

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const queue = useQuery({ queryKey: ["queue"], queryFn: api.queue });

  const queued = queue.data?.total ?? 0;

  return (
    <div className="min-h-screen">
      <SyntheticDataBanner llmMode={health.data?.llm_mode} model={health.data?.model} />

      <header className="border-b border-hairline">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4">
          <div>
            <h1 className="font-display text-lg font-semibold text-ink">SpendSort</h1>
            <p className="text-xs text-ink-faint">
              Expense categorization with confidence gates and a learning vendor memory
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive ? "bg-emerald/15 text-emerald-glow" : "text-ink-muted hover:bg-glass hover:text-ink"
                  }`
                }
              >
                {item.label}
                {item.label === "Review queue" && queued > 0 && (
                  <span className="tabular ml-1.5 rounded-full bg-conf-mid/20 px-1.5 py-0.5 text-[11px] text-conf-mid">
                    {queued}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {health.data && (
            <div className="ml-auto flex items-center gap-4 text-xs text-ink-faint">
              <span title="Decisions at or above this confidence are applied without a human">
                gate <span className="tabular font-semibold text-ink">{health.data.auto_threshold.toFixed(2)}</span>
              </span>
              <span title="Maximum model spend for a single run">
                cap{" "}
                <span className="tabular font-semibold text-ink">
                  {usd(health.data.cost_cap_usd_per_run)}
                </span>
              </span>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {health.isError && (
          <div className="mb-6 rounded-lg border border-conf-low/40 bg-conf-low/10 p-4 text-sm text-conf-low">
            <strong className="font-semibold">API unreachable.</strong> Start it with{" "}
            <code className="font-mono">make dev</code> (or{" "}
            <code className="font-mono">./make.ps1 dev -Port 8123</code> on Windows).
          </div>
        )}

        <Routes>
          <Route path="/" element={<Import />} />
          <Route path="/run" element={<Run />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/metrics" element={<Metrics />} />
        </Routes>
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 pt-4 text-xs text-ink-faint">
        Built by an ex-accountant turned AI engineer · Finance AI Lab, episode 1 ·{" "}
        <span className="opacity-70">all data synthetic</span>
      </footer>
    </div>
  );
}

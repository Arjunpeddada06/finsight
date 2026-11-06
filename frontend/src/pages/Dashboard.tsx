import { useHealth } from "../hooks/useHealth";

export default function Dashboard() {
  const { health, unreachable } = useHealth();
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-2 text-muted">
        Upload a financial report in Documents and its key figures will appear here.
      </p>
      <section className="mt-8 rounded-lg border border-line bg-surface p-5">
        <h2 className="text-sm font-medium">Backend connection</h2>
        <dl className="mt-3 grid grid-cols-3 gap-4 text-sm">
          <div><dt className="text-muted">API</dt><dd>{unreachable ? "Unreachable" : health ? "Connected" : "…"}</dd></div>
          <div><dt className="text-muted">PostgreSQL</dt><dd>{health ? (health.database ? "Connected" : "Down") : "…"}</dd></div>
          <div><dt className="text-muted">pgvector</dt><dd>{health ? (health.pgvector ? "Enabled" : "Missing") : "…"}</dd></div>
        </dl>
      </section>
    </div>
  );
}

import { NavLink, Outlet } from "react-router-dom";
import {
  BarChart3, FileText, GitCompare, History, LayoutDashboard, MessageSquareText, Settings, Sigma,
} from "lucide-react";
import { useHealth } from "../hooks/useHealth";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/analyst", label: "AI Analyst", icon: MessageSquareText },
  { to: "/metrics", label: "Financial Metrics", icon: Sigma },
  { to: "/comparisons", label: "Comparisons", icon: GitCompare },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/history", label: "Chat History", icon: History },
  { to: "/settings", label: "Settings", icon: Settings },
];

function StatusDot() {
  const { health, unreachable } = useHealth();
  const ok = health?.status === "ok";
  const label = unreachable ? "API unreachable" : !health ? "Checking…" : ok ? "All systems ready" : "Database not ready";
  return (
    <div className="flex items-center gap-2 text-xs text-muted" role="status">
      <span className={`size-2 rounded-full ${ok ? "bg-gain" : unreachable || health ? "bg-loss" : "bg-line"}`} />
      {label}
    </div>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <aside className="border-b border-line bg-surface md:min-h-screen md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-5 py-4 md:block">
          <div>
            <div className="text-lg font-semibold tracking-tight text-brand">FinSight AI</div>
            <div className="text-xs text-muted">Financial report analyst</div>
          </div>
          <div className="md:mt-6 md:hidden"><StatusDot /></div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-brand-soft font-medium text-brand" : "text-muted hover:bg-paper hover:text-ink"
                }`
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden px-5 py-6 md:block"><StatusDot /></div>
      </aside>
      <main className="px-5 py-6 md:px-10 md:py-8">
        <Outlet />
      </main>
    </div>
  );
}

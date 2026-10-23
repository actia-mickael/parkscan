import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { ROLE_LABELS } from "@/lib/format";
import { useAuthStore } from "@/stores/authStore";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";

const NAV = [
  { to: "/", label: "Tableau de bord", end: true },
  { to: "/cameras", label: "Caméras" },
  { to: "/passages", label: "Passages" },
  { to: "/mismatches", label: "Écarts de marque" },
  { to: "/residents", label: "Résidents" },
  { to: "/vehicles", label: "Véhicules" },
  { to: "/sites", label: "Sites" },
  { to: "/models", label: "Modèles" },
  { to: "/users", label: "Utilisateurs", adminOnly: true },
];

export default function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { sites, currentSiteId, loaded, load, setCurrent } = useSiteStore();
  const toasts = useUiStore((s) => s.toasts);
  const dismiss = useUiStore((s) => s.dismiss);
  const navigate = useNavigate();

  useEffect(() => {
    if (!loaded) void load();
  }, [loaded, load]);

  const isAdmin = user?.role === "operator_admin";

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 p-4 md:flex">
        <div className="mb-6 px-2">
          <p className="text-lg font-semibold tracking-tight">ParkScan AI</p>
          <p className="truncate text-xs text-slate-400">{user?.tenant.name}</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.filter((n) => !n.adminOnly || isAdmin).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-sky-600/20 text-sky-200" : "text-slate-300 hover:bg-slate-800"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-4 border-t border-slate-800 pt-4 text-xs text-slate-400">
          <p className="truncate text-slate-200">{user?.full_name ?? user?.email}</p>
          <p>{user ? ROLE_LABELS[user.role] : ""}</p>
          <button
            type="button"
            className="mt-2 text-sky-300 hover:underline"
            onClick={() => {
              void logout().then(() => navigate("/login"));
            }}
          >
            Se déconnecter
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-800 bg-slate-900/40 px-4 py-3 md:px-6">
          <p className="text-sm text-slate-400 md:hidden">ParkScan AI</p>
          <label className="ml-auto flex items-center gap-2 text-sm text-slate-400">
            Site
            <select
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100"
              value={currentSiteId ?? ""}
              onChange={(e) => setCurrent(e.target.value || null)}
            >
              <option value="">Tous les sites</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </header>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => dismiss(t.id)}
            className={`rounded-lg border px-3 py-2 text-left text-sm shadow-lg ${
              t.kind === "error"
                ? "border-red-900 bg-red-950 text-red-200"
                : t.kind === "success"
                  ? "border-emerald-900 bg-emerald-950 text-emerald-200"
                  : "border-slate-700 bg-slate-800 text-slate-100"
            }`}
          >
            {t.message}
          </button>
        ))}
      </div>
    </div>
  );
}

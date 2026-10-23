import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { dashboardApi, healthApi } from "@/api/endpoints";
import { Card, ErrorBanner, PageTitle, StatTile } from "@/components/ui";
import { formatHour } from "@/lib/format";
import { useSiteStore } from "@/stores/siteStore";
import type { DashboardSummary, HealthResponse } from "@/types/api";

const PERIODS = [
  { hours: 24, label: "24 h" },
  { hours: 24 * 7, label: "7 jours" },
  { hours: 24 * 30, label: "30 jours" },
];

export default function DashboardPage() {
  const currentSiteId = useSiteStore((s) => s.currentSiteId);
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    dashboardApi
      .summary({ site_id: currentSiteId ?? undefined, hours })
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorMessage(err));
      });
    healthApi
      .get()
      .then((res) => {
        if (!cancelled) setHealth(res.data);
      })
      .catch((err: unknown) => {
        // Le backend répond 503 avec le détail des sondes quand un composant est dégradé.
        const payload = (err as { response?: { data?: HealthResponse } }).response?.data;
        if (!cancelled && payload?.checks) setHealth(payload);
      });
    return () => {
      cancelled = true;
    };
  }, [currentSiteId, hours]);

  const maxHour = Math.max(1, ...(data?.hourly.map((h) => h.allowed + h.denied) ?? [1]));
  const rate = (n: number) => (data && data.passages ? `${Math.round((100 * n) / data.passages)} %` : "—");

  return (
    <>
      <PageTitle
        title="Tableau de bord"
        subtitle="Activité des barrières et état de la plateforme"
        actions={
          <div className="flex gap-1 rounded-lg border border-slate-800 p-1">
            {PERIODS.map((p) => (
              <button
                key={p.hours}
                type="button"
                onClick={() => setHours(p.hours)}
                className={`rounded-md px-3 py-1 text-sm ${hours === p.hours ? "bg-sky-600/30 text-sky-200" : "text-slate-400 hover:text-slate-200"}`}
              >
                {p.label}
              </button>
            ))}
          </div>
        }
      />
      <ErrorBanner message={error} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Passages" value={data?.passages ?? "—"} hint={`sur ${hours} h`} />
        <StatTile label="Autorisés" value={data?.allowed ?? "—"} hint={rate(data?.allowed ?? 0)} />
        <StatTile label="Refusés" value={data?.denied ?? "—"} hint={rate(data?.denied ?? 0)} />
        <StatTile
          label="Écarts à valider"
          value={
            <Link to="/mismatches" className="text-amber-300 hover:underline">
              {data?.pending_reviews ?? "—"}
            </Link>
          }
          hint={`${data?.mismatches ?? 0} écart(s) sur la période`}
        />
        <StatTile label="Captures en échec" value={data?.failed ?? "—"} hint={rate(data?.failed ?? 0)} />
        <StatTile label="Latence moyenne" value={data?.latency_avg_ms != null ? `${data.latency_avg_ms} ms` : "—"} />
        <StatTile label="Latence p95" value={data?.latency_p95_ms != null ? `${data.latency_p95_ms} ms` : "—"} hint="budget : 1 000 ms" />
        <StatTile
          label="Plateforme"
          value={
            health ? (
              <span className={health.status === "ok" ? "text-emerald-300" : "text-amber-300"}>
                {health.status === "ok" ? "Opérationnelle" : "Dégradée"}
              </span>
            ) : (
              "—"
            )
          }
          hint={health ? Object.entries(health.checks).map(([k, v]) => `${k} ${v === "ok" ? "✓" : "✗"}`).join(" · ") : undefined}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-4 text-sm font-medium text-slate-300">Passages par heure</h2>
          {data && data.hourly.length > 0 ? (
            <div className="flex h-40 items-end gap-1">
              {data.hourly.map((h) => {
                const total = h.allowed + h.denied;
                return (
                  <div key={h.hour} className="group flex flex-1 flex-col justify-end" title={`${formatHour(h.hour)} : ${h.allowed} autorisés, ${h.denied} refusés`}>
                    <div className="w-full rounded-t bg-red-500/60" style={{ height: `${(100 * h.denied) / maxHour}%` }} />
                    <div className="w-full bg-emerald-500/70" style={{ height: `${(100 * h.allowed) / maxHour}%` }} />
                    <span className="mt-1 hidden truncate text-center text-[10px] text-slate-500 sm:block">{total}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Aucun passage sur la période.</p>
          )}
        </Card>
        <Card>
          <h2 className="mb-4 text-sm font-medium text-slate-300">Marques les plus vues</h2>
          {data && data.top_brands.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {data.top_brands.map((b) => (
                <li key={b.brand} className="flex items-center gap-2">
                  <span className="w-24 truncate capitalize text-slate-300">{b.brand}</span>
                  <span className="h-2 flex-1 rounded bg-slate-800">
                    <span className="block h-2 rounded bg-sky-500/70" style={{ width: `${(100 * b.count) / data.top_brands[0].count}%` }} />
                  </span>
                  <span className="w-8 text-right text-slate-400">{b.count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Aucune marque reconnue sur la période.</p>
          )}
        </Card>
      </div>
    </>
  );
}

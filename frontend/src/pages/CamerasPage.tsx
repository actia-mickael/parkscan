import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { passagesApi } from "@/api/endpoints";
import CaptureFrame from "@/components/CaptureFrame";
import PassageImage from "@/components/PassageImage";
import { Button, Card, DecisionBadge, EmptyState, ErrorBanner, PageTitle, StatusBadge, inputClass } from "@/components/ui";
import { formatDateTime, percent, plateLabel, reasonLabel } from "@/lib/format";
import { useSiteStore } from "@/stores/siteStore";
import type { PassageRead } from "@/types/api";

const SIZES = [6, 12, 24];
const REFRESH_MS = 3000;
const FRESH_MS = 15_000; // une capture reçue il y a moins de 15 s est signalée « nouveau »
const clock = new Intl.DateTimeFormat("fr-FR", { timeStyle: "medium" });

function isFresh(passage: PassageRead, now: number): boolean {
  return now - new Date(passage.received_at).getTime() < FRESH_MS;
}

export default function CamerasPage() {
  const currentSiteId = useSiteStore((s) => s.currentSiteId);
  const sites = useSiteStore((s) => s.sites);
  const [size, setSize] = useState(12);
  const [decision, setDecision] = useState("");
  const [live, setLive] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [items, setItems] = useState<PassageRead[] | null>(null);
  const [total, setTotal] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const siteNames = useMemo(() => new Map(sites.map((s) => [s.id, s.name])), [sites]);

  const load = useCallback(() => {
    passagesApi
      .list({ site_id: currentSiteId ?? undefined, decision: decision || undefined, page: 1, size })
      .then((res) => {
        setItems(res.data.items);
        setTotal(res.data.total);
        setUpdatedAt(new Date());
        setError(null);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [currentSiteId, decision, size]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!live) return;
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [live, load]);

  const now = updatedAt?.getTime() ?? Date.now();
  const latest = items?.[0] ?? null;

  return (
    <>
      <PageTitle
        title="Caméras"
        subtitle="Images des barrières et lecture des plaques, en direct"
        actions={
          <>
            {updatedAt && <span className="text-xs text-slate-500">actualisé à {clock.format(updatedAt)}</span>}
            <Button variant={showBoxes ? "secondary" : "ghost"} onClick={() => setShowBoxes((v) => !v)}>
              {showBoxes ? "Cadres affichés" : "Cadres masqués"}
            </Button>
            <Button variant={live ? "primary" : "secondary"} onClick={() => setLive((v) => !v)}>
              {live ? "● Direct" : "Direct en pause"}
            </Button>
          </>
        }
      />
      <ErrorBanner message={error} />

      {latest && (
        <Card className="mb-6">
          <p className="mb-3 text-xs uppercase tracking-wide text-slate-400">Dernière lecture</p>
          <div className="flex flex-wrap items-center gap-6">
            {latest.plate_crop_key ? (
              <PassageImage passageId={latest.id} kind="plate" fit="contain" className="h-20 w-56 shrink-0 rounded-lg bg-slate-950" alt="dernière plaque" />
            ) : (
              <div className="flex h-20 w-56 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-xs text-slate-500">
                plaque non détectée
              </div>
            )}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <Link to={`/passages/${latest.id}`} className="font-mono text-4xl font-semibold tracking-wider text-slate-100 hover:text-sky-300">
                  {plateLabel(latest.plate_text)}
                </Link>
                <DecisionBadge decision={latest.decision} />
                {latest.status !== "ok" && <StatusBadge status={latest.status} />}
              </div>
              <p className="mt-1 text-sm text-slate-300">
                {reasonLabel(latest.decision_reason)} · lecture {percent(latest.ocr_conf)} · détection {percent(latest.det_conf)}
              </p>
              <p className="text-sm text-slate-400">
                {siteNames.get(latest.site_id) ?? "Site"} · {formatDateTime(latest.received_at)}
                {latest.brand_pred && (
                  <>
                    {" · "}
                    <span className="capitalize">{latest.brand_pred}</span> {percent(latest.brand_conf)}
                    {latest.is_mismatch && <span className="ml-1 text-amber-300">écart de marque</span>}
                  </>
                )}
              </p>
            </div>
          </div>
        </Card>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select className={`${inputClass} max-w-[12rem]`} value={decision} onChange={(e) => setDecision(e.target.value)}>
          <option value="">Toutes décisions</option>
          <option value="allowed">Autorisés</option>
          <option value="denied">Refusés</option>
        </select>
        <select className={`${inputClass} max-w-[14rem]`} value={size} onChange={(e) => setSize(Number(e.target.value))}>
          {SIZES.map((n) => (
            <option key={n} value={n}>
              {n} dernières captures
            </option>
          ))}
        </select>
        <span className="text-sm text-slate-500">{total} passage(s) au total</span>
      </div>

      {items && items.length === 0 ? (
        <EmptyState>Aucune capture pour l'instant. Lancez le simulateur ou un agent de bord.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items?.map((p) => {
            const fresh = isFresh(p, now);
            return (
              <article
                key={p.id}
                className={`overflow-hidden rounded-xl border bg-slate-900 transition ${fresh ? "border-sky-500/70 ring-1 ring-sky-500/40" : "border-slate-800"}`}
              >
                <CaptureFrame passage={p} showBoxes={showBoxes} className="" />
                <div className="flex items-center gap-3 p-3">
                  {p.plate_crop_key ? (
                    <PassageImage passageId={p.id} kind="plate" fit="contain" className="h-10 w-28 shrink-0 rounded bg-slate-950" alt="plaque" />
                  ) : (
                    <div className="h-10 w-28 shrink-0 rounded bg-slate-800" />
                  )}
                  <div className="min-w-0 flex-1 text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      <Link to={`/passages/${p.id}`} className="truncate font-mono text-lg font-semibold text-slate-100 hover:text-sky-300">
                        {plateLabel(p.plate_text)}
                      </Link>
                      <DecisionBadge decision={p.decision} />
                      {fresh && <span className="text-sky-300">nouveau</span>}
                    </div>
                    <p className="truncate">
                      {reasonLabel(p.decision_reason)} · lecture {percent(p.ocr_conf)}
                      {p.brand_pred && (
                        <>
                          {" · "}
                          <span className="capitalize">{p.brand_pred}</span> {percent(p.brand_conf)}
                        </>
                      )}
                      {p.is_mismatch && <span className="ml-1 text-amber-300">écart</span>}
                    </p>
                    <p className="truncate text-slate-500">
                      {siteNames.get(p.site_id) ?? "Site"} · {formatDateTime(p.received_at)}
                      {p.status !== "ok" && (
                        <>
                          {" · "}
                          <StatusBadge status={p.status} />
                        </>
                      )}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}

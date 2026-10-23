import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { passagesApi } from "@/api/endpoints";
import { Button, DecisionBadge, EmptyState, ErrorBanner, PageTitle, Pagination, StatusBadge, Table, inputClass } from "@/components/ui";
import { formatDateTime, percent, reasonLabel } from "@/lib/format";
import { useSiteStore } from "@/stores/siteStore";
import type { Page, PassageRead } from "@/types/api";

const SIZE = 25;

export default function PassagesPage() {
  const currentSiteId = useSiteStore((s) => s.currentSiteId);
  const [page, setPage] = useState(1);
  const [plate, setPlate] = useState("");
  const [decision, setDecision] = useState("");
  const [onlyMismatch, setOnlyMismatch] = useState(false);
  const [live, setLive] = useState(true);
  const [data, setData] = useState<Page<PassageRead> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    passagesApi
      .list({
        site_id: currentSiteId ?? undefined,
        plate: plate || undefined,
        decision: decision || undefined,
        is_mismatch: onlyMismatch ? true : undefined,
        page,
        size: SIZE,
      })
      .then((res) => {
        setData(res.data);
        setError(null);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [currentSiteId, plate, decision, onlyMismatch, page]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!live) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [live, load]);

  return (
    <>
      <PageTitle
        title="Passages"
        subtitle="Chaque capture à la barrière, avec la décision rendue"
        actions={
          <Button variant={live ? "primary" : "secondary"} onClick={() => setLive((v) => !v)}>
            {live ? "● Direct" : "Direct en pause"}
          </Button>
        }
      />
      <ErrorBanner message={error} />

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className={`${inputClass} max-w-xs`}
          placeholder="Plaque (ex. AB-123-CD)"
          value={plate}
          onChange={(e) => {
            setPlate(e.target.value);
            setPage(1);
          }}
        />
        <select
          className={`${inputClass} max-w-[12rem]`}
          value={decision}
          onChange={(e) => {
            setDecision(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Toutes décisions</option>
          <option value="allowed">Autorisés</option>
          <option value="denied">Refusés</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={onlyMismatch} onChange={(e) => setOnlyMismatch(e.target.checked)} />
          Écarts de marque seulement
        </label>
      </div>

      {data && data.items.length === 0 ? (
        <EmptyState>Aucun passage ne correspond.</EmptyState>
      ) : (
        <Table head={["Reçu", "Plaque", "Décision", "Motif", "Marque prédite", "Déclarée", "Statut", "Latence"]}>
          {data?.items.map((p) => (
            <tr key={p.id} className={p.is_mismatch ? "bg-amber-500/5" : ""}>
              <td className="px-3 py-2 text-slate-400">
                <Link to={`/passages/${p.id}`} className="text-sky-300 hover:underline">
                  {formatDateTime(p.received_at)}
                </Link>
              </td>
              <td className="px-3 py-2 font-mono text-slate-100">{p.plate_text ?? "—"}</td>
              <td className="px-3 py-2">
                <DecisionBadge decision={p.decision} />
              </td>
              <td className="px-3 py-2 text-slate-300">{reasonLabel(p.decision_reason)}</td>
              <td className="px-3 py-2 capitalize text-slate-300">
                {p.brand_pred ? `${p.brand_pred} (${percent(p.brand_conf)})` : "—"}
                {p.is_mismatch && <span className="ml-2 text-xs text-amber-300">écart</span>}
              </td>
              <td className="px-3 py-2 capitalize text-slate-400">{p.declared_brand_snapshot ?? "—"}</td>
              <td className="px-3 py-2">
                <StatusBadge status={p.status} />
              </td>
              <td className="px-3 py-2 text-slate-400">{p.latency_ms != null ? `${p.latency_ms} ms` : "—"}</td>
            </tr>
          ))}
        </Table>
      )}
      {data && <Pagination page={data.page} size={data.size} total={data.total} onChange={setPage} />}
    </>
  );
}

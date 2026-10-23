import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { mismatchesApi } from "@/api/endpoints";
import PassageImage from "@/components/PassageImage";
import { Button, Card, EmptyState, ErrorBanner, PageTitle, Pagination, ReviewBadge, StatTile, inputClass } from "@/components/ui";
import { OUTCOME_LABELS, formatDateTime, percent } from "@/lib/format";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";
import type { MismatchRead, MismatchStats, Page, ReviewStatus } from "@/types/api";

const SIZE = 10;

export default function MismatchesPage() {
  const currentSiteId = useSiteStore((s) => s.currentSiteId);
  const notify = useUiStore((s) => s.notify);
  const [status, setStatus] = useState<ReviewStatus>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<MismatchRead> | null>(null);
  const [stats, setStats] = useState<MismatchStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    mismatchesApi
      .list({ status, site_id: currentSiteId ?? undefined, page, size: SIZE })
      .then((res) => setData(res.data))
      .catch((err: unknown) => setError(errorMessage(err)));
    mismatchesApi
      .stats()
      .then((res) => setStats(res.data))
      .catch(() => undefined);
  }, [status, currentSiteId, page]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (item: MismatchRead, action: () => Promise<unknown>, message: string) => {
    setBusy(item.id);
    try {
      await action();
      notify("success", message);
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const progress = stats ? Math.min(100, Math.round((100 * stats.validated) / Math.max(1, stats.min_dataset_size))) : 0;

  return (
    <>
      <PageTitle title="Écarts de marque" subtitle="Marque reconnue différente de la marque déclarée : votre validation alimente le réentraînement" />
      <ErrorBanner message={error} />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="À valider" value={stats?.pending ?? "—"} />
        <StatTile label="Validés" value={stats?.validated ?? "—"} />
        <StatTile label="Rejetés" value={stats?.rejected ?? "—"} />
        <StatTile
          label="Prêt pour réentraînement"
          value={stats ? (stats.ready_for_retraining ? "Oui" : `${progress} %`) : "—"}
          hint={stats ? `${stats.validated} / ${stats.min_dataset_size} images validées` : undefined}
        />
      </div>

      <div className="mb-4 flex gap-1 rounded-lg border border-slate-800 p-1 w-fit">
        {(["pending", "validated", "rejected"] as ReviewStatus[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setStatus(s);
              setPage(1);
            }}
            className={`rounded-md px-3 py-1 text-sm ${status === s ? "bg-sky-600/30 text-sky-200" : "text-slate-400 hover:text-slate-200"}`}
          >
            {s === "pending" ? "À valider" : s === "validated" ? "Validés" : "Rejetés"}
          </button>
        ))}
      </div>

      {data && data.items.length === 0 ? (
        <EmptyState>Aucun écart dans cette catégorie.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data?.items.map((item) => (
            <Card key={item.id}>
              <div className="flex gap-4">
                <PassageImage passageId={item.passage_id} kind="vehicle" available={!!item.source_crop_key} className="h-32 w-44 shrink-0 rounded-lg" alt="véhicule" />
                <div className="min-w-0 flex-1 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Link to={`/passages/${item.passage_id}`} className="font-mono text-sky-300 hover:underline">
                      {item.plate_norm ?? "—"}
                    </Link>
                    <ReviewBadge status={item.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{formatDateTime(item.received_at)}</p>
                  <p className="mt-2">
                    Reconnue : <span className="capitalize text-amber-300">{item.predicted_brand}</span>{" "}
                    <span className="text-slate-400">({percent(item.predicted_conf)})</span>
                  </p>
                  <p>
                    Déclarée : <span className="capitalize text-slate-100">{item.declared_brand ?? "—"}</span>
                  </p>
                  {item.status !== "pending" && (
                    <p className="mt-1 text-xs text-slate-400">
                      {item.outcome ? OUTCOME_LABELS[item.outcome] : ""}
                      {item.final_brand ? ` → ${item.final_brand}` : ""}
                      {item.comment ? ` · ${item.comment}` : ""}
                    </p>
                  )}
                </div>
              </div>
              {item.status === "pending" && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Button
                    disabled={busy === item.id}
                    onClick={() => act(item, () => mismatchesApi.validate(item.id, { outcome: "predicted_correct" }), `Marque ${item.predicted_brand} confirmée, véhicule mis à jour`)}
                  >
                    C'est bien {item.predicted_brand}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busy === item.id || !item.declared_brand}
                    onClick={() => act(item, () => mismatchesApi.validate(item.id, { outcome: "declared_correct" }), `Marque déclarée ${item.declared_brand} confirmée`)}
                  >
                    C'est bien {item.declared_brand ?? "la déclarée"}
                  </Button>
                  <div className="flex items-center gap-1">
                    <input
                      className={`${inputClass} w-32`}
                      placeholder="Autre marque"
                      value={custom[item.id] ?? ""}
                      onChange={(e) => setCustom((c) => ({ ...c, [item.id]: e.target.value }))}
                    />
                    <Button
                      variant="secondary"
                      disabled={busy === item.id || !(custom[item.id] ?? "").trim()}
                      onClick={() => act(item, () => mismatchesApi.validate(item.id, { outcome: "custom", final_brand: custom[item.id] }), "Marque enregistrée")}
                    >
                      Valider
                    </Button>
                  </div>
                  <Button variant="danger" disabled={busy === item.id} onClick={() => act(item, () => mismatchesApi.reject(item.id, "non exploitable"), "Écart rejeté")}>
                    Rejeter
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
      {data && <Pagination page={data.page} size={data.size} total={data.total} onChange={setPage} />}
    </>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { passagesApi } from "@/api/endpoints";
import PassageImage from "@/components/PassageImage";
import { Card, DecisionBadge, ErrorBanner, PageTitle, StatusBadge } from "@/components/ui";
import { formatDateTime, percent, reasonLabel } from "@/lib/format";
import type { PassageDetail } from "@/types/api";

export default function PassageDetailPage() {
  const { id = "" } = useParams();
  const [passage, setPassage] = useState<PassageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    passagesApi
      .get(id)
      .then((res) => setPassage(res.data))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [id]);

  if (error) return <ErrorBanner message={error} />;
  if (!passage) return <p className="text-sm text-slate-400">Chargement…</p>;

  const rows: [string, React.ReactNode][] = [
    ["Reçu le", formatDateTime(passage.received_at)],
    ["Capturé le", formatDateTime(passage.captured_at)],
    ["Plaque lue", <span className="font-mono">{passage.plate_text ?? "—"}</span>],
    ["Confiance lecture", percent(passage.ocr_conf)],
    ["Confiance détection", percent(passage.det_conf)],
    ["Décision", <DecisionBadge decision={passage.decision} />],
    ["Motif", reasonLabel(passage.decision_reason)],
    ["Statut", <StatusBadge status={passage.status} />],
    ["Véhicule détecté", passage.vehicle_class ?? "—"],
    ["Marque prédite", passage.brand_pred ? `${passage.brand_pred} (${percent(passage.brand_conf)})` : "—"],
    ["Marque déclarée", passage.declared_brand_snapshot ?? "—"],
    ["Écart de marque", passage.is_mismatch ? "oui" : "non"],
    ["Latence totale", passage.latency_ms != null ? `${passage.latency_ms} ms` : "—"],
    ["Latence ML", passage.ml_latency_ms != null ? `${passage.ml_latency_ms} ms` : "—"],
    ["Conditions", passage.conditions ? `${String(passage.conditions.lighting)} · ${String(passage.conditions.blur)}` : "—"],
    ["Modèles", passage.model_versions ? Object.values(passage.model_versions).join(" · ") : "—"],
  ];

  return (
    <>
      <PageTitle title={`Passage ${passage.plate_text ?? ""}`} subtitle={formatDateTime(passage.received_at)} actions={<Link to="/passages" className="text-sm text-sky-300 hover:underline">← Passages</Link>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <PassageImage passageId={passage.id} kind="full" className="w-full rounded-lg" alt="capture complète" />
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <p className="mb-1 text-xs text-slate-400">Plaque</p>
              <PassageImage passageId={passage.id} kind="plate" className="h-20 w-full rounded-lg" />
            </div>
            <div>
              <p className="mb-1 text-xs text-slate-400">Véhicule</p>
              <PassageImage passageId={passage.id} kind="vehicle" className="h-20 w-full rounded-lg" />
            </div>
          </div>
        </Card>
        <Card>
          <dl className="space-y-2 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 border-b border-slate-800/60 pb-2">
                <dt className="text-slate-400">{label}</dt>
                <dd className="text-right capitalize text-slate-100">{value}</dd>
              </div>
            ))}
          </dl>
          {passage.brand_top3 && (
            <p className="mt-3 text-xs text-slate-400">
              Top 3 : {passage.brand_top3.map(([b, p]) => `${b} ${percent(p)}`).join(" · ")}
            </p>
          )}
          <button type="button" className="mt-4 text-xs text-sky-300 hover:underline" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "Masquer" : "Afficher"} le résultat brut
          </button>
          {showRaw && <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">{JSON.stringify(passage.raw_result, null, 2)}</pre>}
        </Card>
      </div>
    </>
  );
}

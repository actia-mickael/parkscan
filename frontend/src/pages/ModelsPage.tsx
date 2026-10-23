import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/api/client";
import { modelsApi } from "@/api/endpoints";
import { Button, Card, EmptyState, ErrorBanner, PageTitle, StatTile, Table } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";
import { useUiStore } from "@/stores/uiStore";
import { formatDateTime, percent } from "@/lib/format";
import type { ModelVersionRead, ModelVersionStatus, PromotionRead, ServedModels } from "@/types/api";

const MODEL_LABELS: Record<string, string> = {
  plate_detector: "Détecteur de plaque",
  ocr: "Lecture de plaque (OCR)",
  vehicle_detector: "Détecteur de véhicule",
  brand_classifier: "Classifieur de marques",
};
const ORDER = ["plate_detector", "ocr", "vehicle_detector", "brand_classifier"];

function sourceLabel(source: string): string {
  if (source === "mlflow") return "Registre MLflow";
  if (source === "local") return "Poids locaux";
  if (source === "image") return "Intégré à l'image";
  return source;
}

const VERSION_STATUS: Record<ModelVersionStatus, { label: string; cls: string }> = {
  candidate: { label: "Candidat", cls: "bg-sky-500/15 text-sky-300" },
  production: { label: "Production", cls: "bg-emerald-500/15 text-emerald-300" },
  previous: { label: "Précédente", cls: "bg-slate-700 text-slate-200" },
  rejected: { label: "Rejetée", cls: "bg-red-500/15 text-red-300" },
  archived: { label: "Archivée", cls: "bg-slate-800 text-slate-400" },
};

function metricCell(metrics: Record<string, number> | null, baseline: Record<string, number> | null, key: string): string {
  const value = metrics?.[key];
  if (value === undefined) return "—";
  const ref = baseline?.[key];
  return ref === undefined ? percent(value) : `${percent(value)} (réf. ${percent(ref)})`;
}

function formatDetail(value: string | number | null): string {
  if (value === null) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return value;
}

export default function ModelsPage() {
  const user = useAuthStore((s) => s.user);
  const notify = useUiStore((s) => s.notify);
  const [data, setData] = useState<ServedModels | null>(null);
  const [versions, setVersions] = useState<ModelVersionRead[]>([]);
  const [promotions, setPromotions] = useState<PromotionRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    modelsApi
      .get()
      .then((res) => {
        setData(res.data);
        setError(null);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
    modelsApi
      .versions()
      .then((res) => setVersions(res.data))
      .catch(() => undefined);
    modelsApi
      .promotions()
      .then((res) => setPromotions(res.data))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const reload = async () => {
    setBusy(true);
    try {
      const res = await modelsApi.reload();
      setData(res.data);
      notify("success", "Modèles rechargés sans interruption de service");
    } catch (err) {
      notify("error", errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const names = data
    ? [...ORDER.filter((n) => n in data.models), ...Object.keys(data.models).filter((n) => !ORDER.includes(n))]
    : [];
  const fromRegistry = data ? Object.values(data.models).some((m) => m.source === "mlflow") : false;

  return (
    <>
      <PageTitle
        title="Modèles"
        subtitle="Modèles servis par le service d'inférence et leur provenance"
        actions={
          user?.role === "operator_admin" && (
            <Button disabled={busy || !data} onClick={() => void reload()}>
              {busy ? "Rechargement…" : "Recharger les modèles"}
            </Button>
          )
        }
      />
      <ErrorBanner message={error} />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatTile
          label="Provenance"
          value={data ? (fromRegistry ? "Registre MLflow" : "Poids locaux") : "—"}
          hint={data ? (fromRegistry ? "alias production" : "dossier ml/weights, sans registre") : undefined}
        />
        <StatTile label="Matériel d'inférence" value={data?.device ?? "—"} />
        <StatTile label="Marques reconnues" value={data?.labels.length ?? "—"} />
      </div>

      {data &&
        (names.length === 0 ? (
          <EmptyState>Aucun modèle chargé.</EmptyState>
        ) : (
          <Table head={["Modèle", "Provenance", "Version", "Détails"]}>
            {names.map((name) => {
              const model = data.models[name];
              const details = Object.entries(model.details)
                .filter(([key]) => !["registry", "name", "source"].includes(key))
                .map(([key, value]) => `${key} : ${formatDetail(value)}`);
              return (
                <tr key={name}>
                  <td className="px-3 py-2 text-slate-100">{MODEL_LABELS[name] ?? name}</td>
                  <td className="px-3 py-2">
                    <span className={model.source === "mlflow" ? "text-emerald-300" : "text-slate-300"}>{sourceLabel(model.source)}</span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-300">{model.version}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{details.length ? details.join(" · ") : "—"}</td>
                </tr>
              );
            })}
          </Table>
        ))}

      <Card className="mt-6">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Versions issues du réentraînement</h2>
        {versions.length === 0 ? (
          <EmptyState>Aucune version entraînée pour l'instant : le DAG d'entraînement n'a pas encore produit de candidat.</EmptyState>
        ) : (
          <Table head={["Modèle", "Version", "Statut", "Jeu de données", "Exactitude", "Top 3", "F1 macro", "Marques", "Créée"]}>
            {versions.map((v) => (
              <tr key={v.id}>
                <td className="px-3 py-2 text-slate-100">{MODEL_LABELS[v.name] ?? v.name}</td>
                <td className="px-3 py-2 font-mono text-slate-100">v{v.version}</td>
                <td className="px-3 py-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${VERSION_STATUS[v.status].cls}`}>
                    {VERSION_STATUS[v.status].label}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-400">{v.dataset_version ?? "—"}</td>
                <td className="px-3 py-2 text-slate-300">{metricCell(v.metrics, v.baseline_metrics, "accuracy")}</td>
                <td className="px-3 py-2 text-slate-300">{metricCell(v.metrics, v.baseline_metrics, "top3_accuracy")}</td>
                <td className="px-3 py-2 text-slate-300">{metricCell(v.metrics, v.baseline_metrics, "f1_macro")}</td>
                <td className="px-3 py-2 text-slate-400">{v.labels_count ?? "—"}</td>
                <td className="px-3 py-2 text-slate-400">{formatDateTime(v.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card className="mt-6">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Décisions de promotion</h2>
        {promotions.length === 0 ? (
          <EmptyState>Aucune décision enregistrée.</EmptyState>
        ) : (
          <Table head={["Date", "Version", "Décision", "Motif", "Remplace", "Par"]}>
            {promotions.map((p) => (
              <tr key={p.id}>
                <td className="px-3 py-2 text-slate-400">{formatDateTime(p.created_at)}</td>
                <td className="px-3 py-2 font-mono text-slate-100">
                  {MODEL_LABELS[p.name] ?? p.name} v{p.version}
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${p.decision === "promoted" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>
                    {p.decision === "promoted" ? "Promue" : "Rejetée"}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-300">{p.reason ?? "—"}</td>
                <td className="px-3 py-2 text-slate-400">{p.previous_version != null ? `v${p.previous_version}` : "—"}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{p.decided_by}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {data && data.labels.length > 0 && (
        <Card className="mt-6">
          <h2 className="mb-3 text-sm font-medium text-slate-300">Marques que le classifieur sait reconnaître</h2>
          <div className="flex flex-wrap gap-2">
            {data.labels.map((label) => (
              <span key={label} className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs capitalize text-slate-200">
                {label}
              </span>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

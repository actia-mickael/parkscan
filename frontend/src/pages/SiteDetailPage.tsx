import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { sitesApi } from "@/api/endpoints";
import { Button, Card, EmptyState, ErrorBanner, Field, PageTitle, Table, inputClass } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useAuthStore } from "@/stores/authStore";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";
import type { ApiKeyRead, SiteRead } from "@/types/api";

const THRESHOLDS: { key: string; label: string }[] = [
  { key: "detection_threshold", label: "Seuil détection plaque" },
  { key: "ocr_threshold", label: "Seuil lecture OCR" },
  { key: "brand_threshold", label: "Seuil marque (écart)" },
];

export default function SiteDetailPage() {
  const { id = "" } = useParams();
  const role = useAuthStore((s) => s.user?.role);
  const reloadSites = useSiteStore((s) => s.load);
  const notify = useUiStore((s) => s.notify);
  const isAdmin = role === "operator_admin";
  const canKeys = isAdmin || role === "site_manager";
  const [site, setSite] = useState<SiteRead | null>(null);
  const [keys, setKeys] = useState<ApiKeyRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", address: "", timezone: "" });
  const [thresholds, setThresholds] = useState<Record<string, string>>({});
  const [keyName, setKeyName] = useState("");
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const load = useCallback(() => {
    sitesApi
      .get(id)
      .then((res) => {
        setSite(res.data);
        setForm({ name: res.data.name, address: res.data.address ?? "", timezone: res.data.timezone });
        const t: Record<string, string> = {};
        for (const { key } of THRESHOLDS) {
          const v = res.data.settings[key];
          t[key] = v === undefined || v === null ? "" : String(v);
        }
        setThresholds(t);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
    if (canKeys) {
      sitesApi
        .keys(id)
        .then((res) => setKeys(res.data))
        .catch(() => undefined);
    }
  }, [id, canKeys]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!site) return;
    const settings: Record<string, unknown> = { ...site.settings };
    for (const { key } of THRESHOLDS) {
      const raw = thresholds[key]?.trim();
      if (raw) settings[key] = Number(raw);
      else delete settings[key];
    }
    try {
      await sitesApi.update(site.id, { name: form.name, address: form.address || null, timezone: form.timezone, settings });
      notify("success", "Site enregistré");
      await reloadSites();
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const createKey = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const res = await sitesApi.createKey(id, keyName || "Agent de bord");
      setNewSecret(res.data.secret);
      setKeyName("");
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const revoke = async (key: ApiKeyRead) => {
    if (!window.confirm(`Révoquer la clé ${key.key_prefix}… ? L'agent qui l'utilise ne pourra plus envoyer de captures.`)) return;
    try {
      await sitesApi.revokeKey(key.id);
      notify("success", "Clé révoquée");
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  if (error) return <ErrorBanner message={error} />;
  if (!site) return <p className="text-sm text-slate-400">Chargement…</p>;

  return (
    <>
      <PageTitle title={site.name} subtitle={site.address ?? undefined} actions={<Link to="/sites" className="text-sm text-sky-300 hover:underline">← Sites</Link>} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-medium text-slate-300">Réglages</h2>
          <form onSubmit={save} className="space-y-3">
            <Field label="Nom">
              <input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={!isAdmin} />
            </Field>
            <Field label="Adresse">
              <input className={inputClass} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} disabled={!isAdmin} />
            </Field>
            <Field label="Fuseau horaire">
              <input className={inputClass} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} disabled={!isAdmin} />
            </Field>
            <div className="grid grid-cols-3 gap-3">
              {THRESHOLDS.map(({ key, label }) => (
                <Field key={key} label={label}>
                  <input
                    className={inputClass}
                    type="number"
                    step="0.05"
                    min="0.05"
                    max="0.95"
                    placeholder="défaut"
                    value={thresholds[key] ?? ""}
                    onChange={(e) => setThresholds({ ...thresholds, [key]: e.target.value })}
                    disabled={!isAdmin}
                  />
                </Field>
              ))}
            </div>
            <p className="text-xs text-slate-500">Vide : valeur du locataire (0,5 / 0,6 / 0,7 par défaut).</p>
            {isAdmin && <Button type="submit">Enregistrer</Button>}
          </form>
        </Card>

        {canKeys && (
          <Card>
            <h2 className="mb-3 text-sm font-medium text-slate-300">Clés API des agents de bord</h2>
            {newSecret && (
              <div className="mb-4 rounded-lg border border-amber-700 bg-amber-950/50 p-3 text-sm">
                <p className="text-amber-200">Nouvelle clé. Copiez-la maintenant : elle ne sera plus jamais affichée.</p>
                <code className="mt-2 block break-all rounded bg-slate-950 p-2 font-mono text-xs text-slate-100">{newSecret}</code>
                <Button variant="ghost" className="mt-2" onClick={() => setNewSecret(null)}>
                  J'ai copié la clé
                </Button>
              </div>
            )}
            <form onSubmit={createKey} className="mb-4 flex gap-2">
              <input className={inputClass} placeholder="Nom de la clé (ex. Barrière entrée)" value={keyName} onChange={(e) => setKeyName(e.target.value)} />
              <Button type="submit">Créer</Button>
            </form>
            {keys.length === 0 ? (
              <EmptyState>Aucune clé.</EmptyState>
            ) : (
              <Table head={["Nom", "Préfixe", "Dernier usage", "État", ""]}>
                {keys.map((k) => (
                  <tr key={k.id}>
                    <td className="px-3 py-2 text-slate-100">{k.name}</td>
                    <td className="px-3 py-2 font-mono text-slate-400">{k.key_prefix}…</td>
                    <td className="px-3 py-2 text-slate-400">{formatDateTime(k.last_used_at)}</td>
                    <td className="px-3 py-2">
                      <span className={k.revoked_at ? "text-red-300" : "text-emerald-300"}>{k.revoked_at ? "révoquée" : "active"}</span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      {!k.revoked_at && (
                        <Button variant="ghost" onClick={() => revoke(k)}>
                          Révoquer
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
        )}
      </div>
    </>
  );
}

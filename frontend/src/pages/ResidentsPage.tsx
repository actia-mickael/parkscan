import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { residentsApi } from "@/api/endpoints";
import { Button, Card, EmptyState, ErrorBanner, Field, PageTitle, Pagination, Table, inputClass } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";
import type { Page, ResidentRead } from "@/types/api";

const SIZE = 25;

export default function ResidentsPage() {
  const { sites, currentSiteId } = useSiteStore();
  const role = useAuthStore((s) => s.user?.role);
  const notify = useUiStore((s) => s.notify);
  const canWrite = role === "operator_admin" || role === "site_manager";
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<ResidentRead> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ site_id: "", last_name: "", first_name: "", email: "", phone: "", subscription: true });

  const load = useCallback(() => {
    residentsApi
      .list({ site_id: currentSiteId ?? undefined, q: q || undefined, page, size: SIZE })
      .then((res) => setData(res.data))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [currentSiteId, q, page]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await residentsApi.create({
        site_id: form.site_id || currentSiteId || sites[0]?.id || "",
        last_name: form.last_name,
        first_name: form.first_name,
        email: form.email || null,
        phone: form.phone || null,
        subscription: form.subscription,
      });
      notify("success", "Résident créé");
      setShowForm(false);
      setForm({ site_id: "", last_name: "", first_name: "", email: "", phone: "", subscription: true });
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const siteName = (id: string) => sites.find((s) => s.id === id)?.name ?? "—";

  return (
    <>
      <PageTitle
        title="Résidents"
        subtitle="Personnes rattachées à un site, propriétaires d'un ou plusieurs véhicules"
        actions={canWrite && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Fermer" : "+ Résident"}</Button>}
      />
      <ErrorBanner message={error} />

      {showForm && (
        <Card className="mb-4">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Site">
              <select className={inputClass} value={form.site_id || currentSiteId || ""} onChange={(e) => setForm({ ...form, site_id: e.target.value })} required>
                <option value="">Choisir…</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Nom">
              <input className={inputClass} value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
            </Field>
            <Field label="Prénom">
              <input className={inputClass} value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
            </Field>
            <Field label="E-mail">
              <input className={inputClass} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Téléphone">
              <input className={inputClass} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.subscription} onChange={(e) => setForm({ ...form, subscription: e.target.checked })} />
              Abonné
            </label>
            <div className="sm:col-span-2 lg:col-span-3">
              <Button type="submit">Créer</Button>
            </div>
          </form>
        </Card>
      )}

      <input
        className={`${inputClass} mb-4 max-w-sm`}
        placeholder="Rechercher par nom ou plaque"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
      />

      {data && data.items.length === 0 ? (
        <EmptyState>Aucun résident.</EmptyState>
      ) : (
        <Table head={["Nom", "Site", "E-mail", "Téléphone", "Abonné", "Actif"]}>
          {data?.items.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-2">
                <Link to={`/residents/${r.id}`} className="text-sky-300 hover:underline">
                  {r.last_name.toUpperCase()} {r.first_name}
                </Link>
              </td>
              <td className="px-3 py-2 text-slate-300">{siteName(r.site_id)}</td>
              <td className="px-3 py-2 text-slate-400">{r.email ?? "—"}</td>
              <td className="px-3 py-2 text-slate-400">{r.phone ?? "—"}</td>
              <td className="px-3 py-2 text-slate-300">{r.subscription ? "oui" : "non"}</td>
              <td className="px-3 py-2 text-slate-300">{r.is_active ? "oui" : "non"}</td>
            </tr>
          ))}
        </Table>
      )}
      {data && <Pagination page={data.page} size={data.size} total={data.total} onChange={setPage} />}
    </>
  );
}

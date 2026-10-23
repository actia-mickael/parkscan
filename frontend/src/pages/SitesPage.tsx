import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { sitesApi } from "@/api/endpoints";
import { Button, Card, EmptyState, Field, PageTitle, Table, inputClass } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";

export default function SitesPage() {
  const { sites, load } = useSiteStore();
  const role = useAuthStore((s) => s.user?.role);
  const notify = useUiStore((s) => s.notify);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", address: "" });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await sitesApi.create({ name: form.name, address: form.address || null });
      notify("success", "Site créé");
      setShowForm(false);
      setForm({ name: "", address: "" });
      await load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  return (
    <>
      <PageTitle
        title="Sites"
        subtitle="Vos parkings, leurs réglages et les clés de leurs agents de bord"
        actions={role === "operator_admin" && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Fermer" : "+ Site"}</Button>}
      />
      {showForm && (
        <Card className="mb-4">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
            <Field label="Nom">
              <input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Adresse">
              <input className={inputClass} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </Field>
            <div className="flex items-end">
              <Button type="submit">Créer</Button>
            </div>
          </form>
        </Card>
      )}
      {sites.length === 0 ? (
        <EmptyState>Aucun site dans votre périmètre.</EmptyState>
      ) : (
        <Table head={["Nom", "Identifiant", "Adresse", "Fuseau", "Actif"]}>
          {sites.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2">
                <Link to={`/sites/${s.id}`} className="text-sky-300 hover:underline">
                  {s.name}
                </Link>
              </td>
              <td className="px-3 py-2 font-mono text-slate-400">{s.slug}</td>
              <td className="px-3 py-2 text-slate-300">{s.address ?? "—"}</td>
              <td className="px-3 py-2 text-slate-400">{s.timezone}</td>
              <td className="px-3 py-2 text-slate-300">{s.is_active ? "oui" : "non"}</td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

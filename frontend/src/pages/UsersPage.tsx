import { type FormEvent, useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/api/client";
import { usersApi } from "@/api/endpoints";
import { Button, Card, EmptyState, ErrorBanner, Field, PageTitle, Table, inputClass } from "@/components/ui";
import { ROLE_LABELS, formatDateTime } from "@/lib/format";
import { useAuthStore } from "@/stores/authStore";
import { useSiteStore } from "@/stores/siteStore";
import { useUiStore } from "@/stores/uiStore";
import type { UserRead, UserRole } from "@/types/api";

export default function UsersPage() {
  const me = useAuthStore((s) => s.user);
  const sites = useSiteStore((s) => s.sites);
  const notify = useUiStore((s) => s.notify);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<{ email: string; password: string; full_name: string; role: UserRole; site_ids: string[] }>({
    email: "",
    password: "",
    full_name: "",
    role: "agent",
    site_ids: [],
  });

  const load = useCallback(() => {
    usersApi
      .list()
      .then((res) => setUsers(res.data))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await usersApi.create({ ...form, full_name: form.full_name || null });
      notify("success", "Utilisateur créé");
      setShowForm(false);
      setForm({ email: "", password: "", full_name: "", role: "agent", site_ids: [] });
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const toggleActive = async (u: UserRead) => {
    try {
      await usersApi.update(u.id, { is_active: !u.is_active });
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const siteNames = (ids: string[]) => (ids.length ? ids.map((id) => sites.find((s) => s.id === id)?.name ?? "?").join(", ") : "tous");

  return (
    <>
      <PageTitle title="Utilisateurs" subtitle="Comptes du back-office et sites autorisés" actions={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Fermer" : "+ Utilisateur"}</Button>} />
      <ErrorBanner message={error} />

      {showForm && (
        <Card className="mb-4">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="E-mail">
              <input className={inputClass} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </Field>
            <Field label="Mot de passe (8 caractères min.)">
              <input className={inputClass} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} />
            </Field>
            <Field label="Nom complet">
              <input className={inputClass} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </Field>
            <Field label="Rôle">
              <select className={inputClass} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
                {(Object.keys(ROLE_LABELS) as UserRole[]).map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </Field>
            {form.role !== "operator_admin" && (
              <div className="sm:col-span-2 lg:col-span-4">
                <p className="mb-1 text-sm text-slate-400">Sites autorisés</p>
                <div className="flex flex-wrap gap-3">
                  {sites.map((s) => (
                    <label key={s.id} className="flex items-center gap-1 text-sm text-slate-300">
                      <input
                        type="checkbox"
                        checked={form.site_ids.includes(s.id)}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            site_ids: e.target.checked ? [...form.site_ids, s.id] : form.site_ids.filter((x) => x !== s.id),
                          })
                        }
                      />
                      {s.name}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div className="sm:col-span-2 lg:col-span-4">
              <Button type="submit">Créer</Button>
            </div>
          </form>
        </Card>
      )}

      {users.length === 0 ? (
        <EmptyState>Aucun utilisateur.</EmptyState>
      ) : (
        <Table head={["E-mail", "Nom", "Rôle", "Sites", "Dernière connexion", "Actif", ""]}>
          {users.map((u) => (
            <tr key={u.id}>
              <td className="px-3 py-2 text-slate-100">{u.email}</td>
              <td className="px-3 py-2 text-slate-300">{u.full_name ?? "—"}</td>
              <td className="px-3 py-2 text-slate-300">{ROLE_LABELS[u.role]}</td>
              <td className="px-3 py-2 text-slate-400">{u.role === "operator_admin" ? "tous" : siteNames(u.site_ids)}</td>
              <td className="px-3 py-2 text-slate-400">{formatDateTime(u.last_login_at)}</td>
              <td className="px-3 py-2 text-slate-300">{u.is_active ? "oui" : "non"}</td>
              <td className="px-3 py-2 text-right">
                {u.id !== me?.id && (
                  <Button variant="ghost" onClick={() => toggleActive(u)}>
                    {u.is_active ? "Désactiver" : "Réactiver"}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

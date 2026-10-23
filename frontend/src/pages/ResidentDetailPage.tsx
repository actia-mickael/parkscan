import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { residentsApi, vehiclesApi } from "@/api/endpoints";
import { Button, Card, EmptyState, ErrorBanner, Field, PageTitle, Table, inputClass } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";
import { useUiStore } from "@/stores/uiStore";
import type { ResidentRead, VehicleRead } from "@/types/api";

export default function ResidentDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const role = useAuthStore((s) => s.user?.role);
  const notify = useUiStore((s) => s.notify);
  const canWrite = role === "operator_admin" || role === "site_manager";
  const [resident, setResident] = useState<ResidentRead | null>(null);
  const [vehicles, setVehicles] = useState<VehicleRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ plate: "", declared_brand: "", declared_model: "", color: "" });

  const load = useCallback(() => {
    Promise.all([residentsApi.get(id), residentsApi.vehicles(id)])
      .then(([r, v]) => {
        setResident(r.data);
        setVehicles(v.data);
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const addVehicle = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await vehiclesApi.create({
        resident_id: id,
        plate: form.plate,
        declared_brand: form.declared_brand.trim().toLowerCase() || null,
        declared_model: form.declared_model || null,
        color: form.color || null,
      });
      notify("success", "Véhicule ajouté");
      setForm({ plate: "", declared_brand: "", declared_model: "", color: "" });
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const toggle = async (v: VehicleRead) => {
    try {
      await vehiclesApi.toggleAccess(v.id, !v.access_enabled);
      notify("success", v.access_enabled ? "Accès désactivé" : "Accès activé");
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const removeVehicle = async (v: VehicleRead) => {
    if (!window.confirm(`Supprimer le véhicule ${v.plate_raw} ?`)) return;
    try {
      await vehiclesApi.remove(v.id);
      notify("success", "Véhicule supprimé");
      load();
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  const removeResident = async () => {
    if (!resident || !window.confirm("Supprimer ce résident et tous ses véhicules ?")) return;
    try {
      await residentsApi.remove(resident.id);
      notify("success", "Résident supprimé");
      navigate("/residents");
    } catch (err) {
      notify("error", errorMessage(err));
    }
  };

  if (error) return <ErrorBanner message={error} />;
  if (!resident) return <p className="text-sm text-slate-400">Chargement…</p>;

  return (
    <>
      <PageTitle
        title={`${resident.last_name.toUpperCase()} ${resident.first_name}`}
        subtitle={[resident.email, resident.phone, resident.city].filter(Boolean).join(" · ") || undefined}
        actions={
          <>
            <Link to="/residents" className="text-sm text-sky-300 hover:underline">
              ← Résidents
            </Link>
            {canWrite && (
              <Button variant="danger" onClick={removeResident}>
                Supprimer
              </Button>
            )}
          </>
        }
      />

      <Card className="mb-4">
        <h2 className="mb-3 text-sm font-medium text-slate-300">Véhicules</h2>
        {vehicles.length === 0 ? (
          <EmptyState>Aucun véhicule.</EmptyState>
        ) : (
          <Table head={["Plaque", "Marque déclarée", "Modèle", "Couleur", "Accès", ""]}>
            {vehicles.map((v) => (
              <tr key={v.id}>
                <td className="px-3 py-2 font-mono text-slate-100">{v.plate_raw}</td>
                <td className="px-3 py-2 capitalize text-slate-300">{v.declared_brand ?? "—"}</td>
                <td className="px-3 py-2 text-slate-300">{v.declared_model ?? "—"}</td>
                <td className="px-3 py-2 text-slate-300">{v.color ?? "—"}</td>
                <td className="px-3 py-2">
                  <span className={v.access_enabled ? "text-emerald-300" : "text-red-300"}>{v.access_enabled ? "autorisé" : "désactivé"}</span>
                </td>
                <td className="px-3 py-2 text-right">
                  {canWrite && (
                    <div className="flex justify-end gap-2">
                      <Button variant="secondary" onClick={() => toggle(v)}>
                        {v.access_enabled ? "Désactiver" : "Activer"}
                      </Button>
                      <Button variant="ghost" onClick={() => removeVehicle(v)}>
                        Supprimer
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {canWrite && (
        <Card>
          <h2 className="mb-3 text-sm font-medium text-slate-300">Ajouter un véhicule</h2>
          <form onSubmit={addVehicle} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Plaque">
              <input className={inputClass} placeholder="AB-123-CD" value={form.plate} onChange={(e) => setForm({ ...form, plate: e.target.value })} required />
            </Field>
            <Field label="Marque déclarée">
              <input className={inputClass} placeholder="renault" value={form.declared_brand} onChange={(e) => setForm({ ...form, declared_brand: e.target.value })} />
            </Field>
            <Field label="Modèle">
              <input className={inputClass} value={form.declared_model} onChange={(e) => setForm({ ...form, declared_model: e.target.value })} />
            </Field>
            <Field label="Couleur">
              <input className={inputClass} value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
            </Field>
            <div className="flex items-end">
              <Button type="submit">Ajouter</Button>
            </div>
          </form>
        </Card>
      )}
    </>
  );
}

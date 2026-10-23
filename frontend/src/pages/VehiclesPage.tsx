import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { vehiclesApi } from "@/api/endpoints";
import { EmptyState, ErrorBanner, PageTitle, Pagination, Table, inputClass } from "@/components/ui";
import { useSiteStore } from "@/stores/siteStore";
import type { Page, VehicleRead } from "@/types/api";

const SIZE = 25;

export default function VehiclesPage() {
  const currentSiteId = useSiteStore((s) => s.currentSiteId);
  const [plate, setPlate] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<VehicleRead> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    vehiclesApi
      .list({ site_id: currentSiteId ?? undefined, plate: plate || undefined, page, size: SIZE })
      .then((res) => setData(res.data))
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [currentSiteId, plate, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageTitle title="Véhicules" subtitle="Recherche par plaque ; la gestion se fait depuis la fiche du résident" />
      <ErrorBanner message={error} />
      <input
        className={`${inputClass} mb-4 max-w-sm`}
        placeholder="Plaque (ex. AB-123-CD)"
        value={plate}
        onChange={(e) => {
          setPlate(e.target.value);
          setPage(1);
        }}
      />
      {data && data.items.length === 0 ? (
        <EmptyState>Aucun véhicule.</EmptyState>
      ) : (
        <Table head={["Plaque", "Marque déclarée", "Modèle", "Couleur", "Accès", "Résident"]}>
          {data?.items.map((v) => (
            <tr key={v.id}>
              <td className="px-3 py-2 font-mono text-slate-100">{v.plate_raw}</td>
              <td className="px-3 py-2 capitalize text-slate-300">{v.declared_brand ?? "—"}</td>
              <td className="px-3 py-2 text-slate-300">{v.declared_model ?? "—"}</td>
              <td className="px-3 py-2 text-slate-300">{v.color ?? "—"}</td>
              <td className="px-3 py-2">
                <span className={v.access_enabled ? "text-emerald-300" : "text-red-300"}>{v.access_enabled ? "autorisé" : "désactivé"}</span>
              </td>
              <td className="px-3 py-2">
                <Link to={`/residents/${v.resident_id}`} className="text-sky-300 hover:underline">
                  fiche
                </Link>
              </td>
            </tr>
          ))}
        </Table>
      )}
      {data && <Pagination page={data.page} size={data.size} total={data.total} onChange={setPage} />}
    </>
  );
}
